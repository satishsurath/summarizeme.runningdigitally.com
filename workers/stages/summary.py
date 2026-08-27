"""Summary worker stage handler with Nemo generation admission control.

Acquires a batch generation lease (max 2 concurrent, preserving 1 interactive chat slot),
invokes SummaryService to generate the 9-section summary, persists SummaryRun and legacy SummariesV2,
releases the lease, and enqueues downstream embed_summary stage.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app_config import DEFAULT_GEN_MODEL
from services.resource_admission import ResourceAdmission
from services.summary_service import SummaryService

logger = logging.getLogger(__name__)


def handle_summary(payload: dict[str, Any], session: Session) -> dict[str, Any]:
    """Execute batch summary generation with generation lease acquisition and downstream scheduling."""
    video_id = payload.get("video_id")
    if not video_id:
        raise ValueError("Payload missing required 'video_id'")

    model_name = payload.get("model_name", DEFAULT_GEN_MODEL)
    reasoning_effort = payload.get("reasoning_effort", "medium")
    worker_owner = f"worker-summary-{video_id}"

    # 1. Acquire batch generation lease (max 2 batch in-flight)
    lease_id = ResourceAdmission.acquire_lease(
        session=session,
        resource_class="generation_batch",
        owner=worker_owner,
        lease_seconds=300,
    )
    if not lease_id:
        logger.info("Batch generation capacity full. Yielding summary stage for %s for retry.", video_id)
        raise RuntimeError("Generation capacity at limit (2 batch in-flight); retrying shortly")

    try:
        # 2. Generate and persist structured summary
        summary_run, _structured_summary = SummaryService.generate_and_persist_summary(
            session=session,
            video_id=video_id,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
        )
    finally:
        # 3. Always release generation lease
        ResourceAdmission.release_lease(session=session, lease_id=lease_id, owner=worker_owner)

    # 4. Schedule downstream embed_summary stage
    downstream_items = [
        {
            "stage": "embed_summary",
            "resource_class": "embedding",
            "item_key": video_id,
            "priority": payload.get("priority", 0),
            "payload": {
                "video_id": video_id,
                "model_name": model_name,
                "summary_run_id": summary_run.id,
            },
        }
    ]

    logger.info(
        "Summary stage completed for video %s (run_id=%s). Scheduled embed_summary.",
        video_id,
        summary_run.id,
    )

    return {
        "result": {
            "video_id": video_id,
            "summary_run_id": summary_run.id,
            "model_name": model_name,
            "reasoning_effort": reasoning_effort,
            "status": "completed",
        },
        "downstream_items": downstream_items,
    }
