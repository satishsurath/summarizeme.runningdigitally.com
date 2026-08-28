"""Worker process CLI for executing pipeline stages.

Supports stage-specific execution or combined all-in-one mode, graceful SIGTERM drain,
lease renewal, and scale-to-zero idle exit.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from app_config import SessionLocal
from services.job_queue import JobQueue
from services.resource_admission import ResourceAdmission

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker")

# Global stop event for graceful termination — set() wakes any waiting sleep
_SHUTDOWN_EVENT = threading.Event()


def _signal_handler(signum: int, frame: Any) -> None:
    sig_name = signal.Signals(signum).name
    logger.info("Received %s signal. Initiating graceful worker drain...", sig_name)
    _SHUTDOWN_EVENT.set()


# Stage handler registry (populated by stage modules in Phase 2-4)
STAGE_HANDLERS: dict[str, Callable[[dict[str, Any], Any], dict[str, Any]]] = {}


def register_stage_handler(
    stage: str,
    handler: Callable[[dict[str, Any], Any], dict[str, Any]],
) -> None:
    """Register a handler function for a specific pipeline stage."""
    STAGE_HANDLERS[stage] = handler


# Register default built-in stage handlers
from workers.stages.discovery import handle_discovery  # noqa: E402
from workers.stages.embedding import (  # noqa: E402
    handle_embed_summary,
    handle_embed_transcript,
)
from workers.stages.finalize import handle_finalize  # noqa: E402
from workers.stages.summary import handle_summary  # noqa: E402
from workers.stages.transcript import handle_transcript  # noqa: E402

register_stage_handler("discover", handle_discovery)
register_stage_handler("transcript", handle_transcript)
register_stage_handler("summarize", handle_summary)
register_stage_handler("embed_transcript", handle_embed_transcript)
register_stage_handler("embed_summary", handle_embed_summary)
register_stage_handler("finalize", handle_finalize)


def execute_work_item(work_item: Any, session: Any, lease_seconds: int = 600) -> None:
    """Execute the handler for a given work item with background lease heartbeats and fencing."""
    stage = work_item.stage
    worker_id = work_item.lease_owner or "unknown"
    handler = STAGE_HANDLERS.get(stage)

    if not handler:
        logger.warning("No handler registered for stage '%s'. Marking item completed (stub).", stage)
        JobQueue.complete(
            session=session,
            work_item_id=work_item.id,
            worker_id=worker_id,
            result={"status": "stub_completed", "stage": stage},
        )
        return

    # Start heartbeat renewal thread
    heartbeat_stop = threading.Event()
    lease_lost = threading.Event()
    hb_interval = max(5.0, float(lease_seconds) / 3.0)

    def _heartbeat_worker():
        while not heartbeat_stop.wait(timeout=hb_interval):
            try:
                with SessionLocal() as hb_session:
                    renewed = JobQueue.renew(
                        session=hb_session,
                        work_item_id=work_item.id,
                        worker_id=worker_id,
                        lease_seconds=lease_seconds,
                    )
                    if not renewed:
                        logger.warning(
                            "Lease lost for work_item %d (owner=%s) during heartbeat. Fencing execution.",
                            work_item.id,
                            worker_id,
                        )
                        lease_lost.set()
                        break
            except Exception as hb_exc:
                logger.warning("Heartbeat renewal error for work_item %d: %s", work_item.id, hb_exc)

    hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True, name=f"hb-{work_item.id}")
    hb_thread.start()

    try:
        outcome = handler(work_item.payload, session)

        if lease_lost.is_set():
            logger.error(
                "Work item %d finished after lease was lost. Refusing to commit fenced outcome.",
                work_item.id,
            )
            return

        downstream = outcome.get("downstream_items")
        result = outcome.get("result", {})
        JobQueue.complete(
            session=session,
            work_item_id=work_item.id,
            worker_id=worker_id,
            result=result,
            downstream_items=downstream,
        )
    except Exception as exc:
        logger.exception("Error executing work_item %d (stage=%s): %s", work_item.id, stage, exc)
        if not lease_lost.is_set():
            try:
                JobQueue.retry(
                    session=session,
                    work_item_id=work_item.id,
                    worker_id=worker_id,
                    delay_seconds=60,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
            except Exception as retry_exc:
                logger.warning("Failed to mark work_item %d for retry: %s", work_item.id, retry_exc)
    finally:
        heartbeat_stop.set()
        hb_thread.join(timeout=1.0)


def run_worker_loop(
    resource_classes: list[str],
    worker_id: str,
    poll_interval_seconds: float = 2.0,
    idle_exit_seconds: int = 300,
    lease_seconds: int = 600,
) -> None:
    """Main worker poll loop."""
    logger.info(
        "Starting worker %s (resource_classes=%s, idle_exit=%ds, poll_interval=%.1fs)",
        worker_id,
        resource_classes,
        idle_exit_seconds,
        poll_interval_seconds,
    )

    last_active_time = time.time()
    last_recovery_time = 0.0

    while not _SHUTDOWN_EVENT.is_set():
        work_processed = False

        with SessionLocal() as session:
            # Seed resource limits if missing
            ResourceAdmission.ensure_default_limits(session)

            # Periodically recover expired leases every 60s
            now_time = time.time()
            if now_time - last_recovery_time > 60.0:
                recovered = JobQueue.recover_expired_leases(session)
                if recovered > 0:
                    logger.info("Recovered %d expired leases", recovered)
                last_recovery_time = now_time

            # Attempt to claim work from any assigned resource class
            for r_class in resource_classes:
                if _SHUTDOWN_EVENT.is_set():
                    break

                work_item = JobQueue.claim(
                    session=session,
                    resource_class=r_class,
                    worker_id=worker_id,
                    lease_seconds=lease_seconds,
                )

                if work_item:
                    work_processed = True
                    last_active_time = time.time()
                    execute_work_item(work_item, session, lease_seconds=lease_seconds)
                    break  # loop to next iteration to claim next available item

        if not work_processed:
            # Check scale-to-zero idle timeout
            elapsed_idle = time.time() - last_active_time
            if idle_exit_seconds > 0 and elapsed_idle >= idle_exit_seconds:
                logger.info(
                    "Worker %s reached idle timeout (%.1fs >= %ds). Exiting for scale-to-zero.",
                    worker_id,
                    elapsed_idle,
                    idle_exit_seconds,
                )
                break

            _SHUTDOWN_EVENT.wait(timeout=poll_interval_seconds)

    logger.info("Worker %s shut down cleanly.", worker_id)


def main() -> None:
    """CLI entrypoint."""
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    parser = argparse.ArgumentParser(description="SummarizeMe Pipeline Worker")
    parser.add_argument(
        "--resource-class",
        choices=["control", "youtube", "generation", "embedding", "all"],
        default="all",
        help="Resource class to process (default: all)",
    )
    parser.add_argument(
        "--idle-exit-seconds",
        type=int,
        default=300,
        help="Seconds of idle time before worker exits (default: 300, 0 to disable)",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Polling sleep interval in seconds when idle (default: 2.0)",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=600,
        help="Work item lease timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="Custom worker identity (default: auto-generated)",
    )

    args = parser.parse_args()

    if args.resource_class == "all":
        resource_classes = ["control", "youtube", "generation", "embedding"]
    else:
        resource_classes = [args.resource_class]

    worker_id = args.worker_id or f"{args.resource_class}-{str(uuid.uuid4())[:8]}"

    try:
        run_worker_loop(
            resource_classes=resource_classes,
            worker_id=worker_id,
            poll_interval_seconds=args.poll_interval_seconds,
            idle_exit_seconds=args.idle_exit_seconds,
            lease_seconds=args.lease_seconds,
        )
    except Exception as exc:
        logger.exception("Worker %s terminated with unexpected exception: %s", worker_id, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
