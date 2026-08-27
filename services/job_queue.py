"""PostgreSQL-backed durable work queue service for SummarizeMe.

Provides atomic work claims with FOR UPDATE SKIP LOCKED, lease heartbeats,
crash recovery, retry backoff, and idempotent pipeline stage orchestration.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import Job, WorkItem, ensure_utc, utcnow

logger = logging.getLogger(__name__)


class JobQueue:
    """Manages lifecycle of durable jobs and work items."""

    @staticmethod
    def create_job(
        session: Session,
        job_type: str,
        requested_by: str | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        initial_work_items: list[dict[str, Any]] | None = None,
        priority: int = 0,
    ) -> Job:
        """Create a new top-level Job and its initial work items in one transaction."""
        now = utcnow()
        payload = payload or {}

        # Check idempotency key if provided
        if idempotency_key:
            existing = session.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing:
                logger.info("Found existing job %s for idempotency_key %s", existing.id, idempotency_key)
                return existing

        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            job_type=job_type,
            status="pending",
            priority=priority,
            requested_by=requested_by,
            request_payload=payload,
            idempotency_key=idempotency_key,
            total_items=len(initial_work_items or []),
            completed_items=0,
            failed_items=0,
            created_at=now,
            updated_at=now,
        )
        session.add(job)

        if initial_work_items:
            for item in initial_work_items:
                wi = WorkItem(
                    job_id=job_id,
                    stage=item["stage"],
                    resource_class=item["resource_class"],
                    item_key=str(item["item_key"]),
                    status="pending",
                    priority=item.get("priority", priority),
                    payload=item.get("payload", {}),
                    attempt_count=0,
                    max_attempts=item.get("max_attempts", 3),
                    available_at=item.get("available_at", now),
                    created_at=now,
                    updated_at=now,
                )
                session.add(wi)

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if not idempotency_key:
                raise
            # A concurrent request inserted this key after the initial lookup.
            # Return the canonical job rather than surfacing a 500 to a retried
            # client request.
            existing = session.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing:
                return existing
            raise
        logger.info("Created job %s (%s) with %d work items", job_id, job_type, len(initial_work_items or []))
        return job

    @staticmethod
    def claim(
        session: Session,
        resource_class: str,
        worker_id: str,
        lease_seconds: int = 600,
    ) -> WorkItem | None:
        """Atomically claim the highest priority runnable work item for a resource class.

        Uses FOR UPDATE SKIP LOCKED on PostgreSQL.
        """
        now = utcnow()
        bind = session.get_bind()
        dialect_name = bind.dialect.name if bind else "postgresql"

        # Build candidate query
        stmt = (
            select(WorkItem)
            .where(
                WorkItem.status.in_(["pending", "retry"]),
                WorkItem.available_at <= now,
                WorkItem.resource_class == resource_class,
            )
            .order_by(WorkItem.priority.desc(), WorkItem.available_at.asc(), WorkItem.id.asc())
            .limit(1)
        )

        if dialect_name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        candidate = session.scalar(stmt)
        if not candidate:
            return None

        # Lock and transition to leased
        candidate.status = "leased"
        candidate.lease_owner = worker_id
        candidate.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
        candidate.attempt_count += 1
        candidate.updated_at = now

        # Update parent job to running if still pending
        job = candidate.job
        if job and job.status == "pending":
            job.status = "running"
            job.started_at = job.started_at or now
            job.updated_at = now

        session.commit()
        logger.info(
            "Worker %s leased work_item %d (stage=%s, item_key=%s, attempt=%d)",
            worker_id,
            candidate.id,
            candidate.stage,
            candidate.item_key,
            candidate.attempt_count,
        )
        return candidate

    @staticmethod
    def renew(
        session: Session,
        work_item_id: int,
        worker_id: str,
        lease_seconds: int = 600,
    ) -> bool:
        """Renew the lease on an active work item (heartbeat)."""
        now = utcnow()
        item = session.get(WorkItem, work_item_id)
        lease_expiry = ensure_utc(item.lease_expires_at) if item and item.lease_expires_at else None
        if (
            not item
            or item.status != "leased"
            or item.lease_owner != worker_id
            or not lease_expiry
            or lease_expiry <= now
        ):
            return False

        item.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
        item.updated_at = now
        session.commit()
        return True

    @staticmethod
    def complete(
        session: Session,
        work_item_id: int,
        worker_id: str,
        result: dict[str, Any] | None = None,
        downstream_items: list[dict[str, Any]] | None = None,
    ) -> None:
        """Mark work item completed and insert any downstream items in one transaction."""
        now = utcnow()
        item = session.get(WorkItem, work_item_id)
        if not item:
            raise ValueError(f"Work item {work_item_id} not found")
        lease_expiry = ensure_utc(item.lease_expires_at) if item.lease_expires_at else None
        if item.status != "leased" or item.lease_owner != worker_id or not lease_expiry or lease_expiry <= now:
            raise ValueError(
                f"Work item {work_item_id} is no longer leased by {worker_id} "
                f"(status={item.status}, owner={item.lease_owner})"
            )

        item.status = "completed"
        item.result = result or {}
        item.lease_expires_at = None
        item.completed_at = now
        item.updated_at = now

        job = item.job
        if job:
            job.completed_items += 1
            job.updated_at = now

            if downstream_items:
                for d_item in downstream_items:
                    # Atomic idempotent insert — ON CONFLICT DO NOTHING prevents
                    # TOCTOU races when concurrent workers complete upstream deps.
                    stmt = (
                        pg_insert(WorkItem)
                        .values(
                            job_id=job.id,
                            stage=d_item["stage"],
                            resource_class=d_item["resource_class"],
                            item_key=str(d_item["item_key"]),
                            status="pending",
                            priority=d_item.get("priority", item.priority),
                            payload=d_item.get("payload", {}),
                            attempt_count=0,
                            max_attempts=d_item.get("max_attempts", 3),
                            available_at=d_item.get("available_at", now),
                            created_at=now,
                            updated_at=now,
                        )
                        .on_conflict_do_nothing(index_elements=["job_id", "stage", "item_key"])
                    )
                    insert_result = session.execute(stmt)
                    if insert_result.rowcount:
                        job.total_items += 1

            JobQueue._evaluate_job_completion(session, job)

        session.commit()
        logger.info("Work item %d (stage=%s) completed by worker %s", work_item_id, item.stage, worker_id)

    @staticmethod
    def retry(
        session: Session,
        work_item_id: int,
        worker_id: str,
        delay_seconds: int = 60,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> bool:
        """Schedule a retry for a work item with exponential/custom backoff.

        If max_attempts reached, transitions item to failed. Returns True if retrying, False if failed.
        """
        now = utcnow()
        item = session.get(WorkItem, work_item_id)
        if not item:
            raise ValueError(f"Work item {work_item_id} not found")
        lease_expiry = ensure_utc(item.lease_expires_at) if item.lease_expires_at else None
        if item.status != "leased" or item.lease_owner != worker_id or not lease_expiry or lease_expiry <= now:
            raise ValueError(f"Work item {work_item_id} is no longer leased by {worker_id}")

        item.last_error_code = error_code
        item.last_error_message = error_message
        item.lease_expires_at = None
        item.updated_at = now

        if item.attempt_count >= item.max_attempts:
            item.status = "failed"
            item.completed_at = now
            job = item.job
            if job:
                job.failed_items += 1
                job.updated_at = now
                JobQueue._evaluate_job_completion(session, job)
            session.commit()
            logger.warning(
                "Work item %d (stage=%s) permanently failed after %d attempts",
                work_item_id,
                item.stage,
                item.attempt_count,
            )
            return False

        item.status = "retry"
        item.available_at = now + datetime.timedelta(seconds=delay_seconds)
        session.commit()
        logger.info(
            "Work item %d scheduled for retry in %ds (attempt %d/%d)",
            work_item_id,
            delay_seconds,
            item.attempt_count,
            item.max_attempts,
        )
        return True

    @staticmethod
    def fail(
        session: Session,
        work_item_id: int,
        worker_id: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Mark a work item as permanently failed immediately (e.g. video has no captions)."""
        now = utcnow()
        item = session.get(WorkItem, work_item_id)
        if not item:
            raise ValueError(f"Work item {work_item_id} not found")
        lease_expiry = ensure_utc(item.lease_expires_at) if item.lease_expires_at else None
        if item.status != "leased" or item.lease_owner != worker_id or not lease_expiry or lease_expiry <= now:
            raise ValueError(f"Work item {work_item_id} is no longer leased by {worker_id}")

        item.status = "failed"
        item.last_error_code = error_code
        item.last_error_message = error_message
        item.lease_expires_at = None
        item.completed_at = now
        item.updated_at = now

        job = item.job
        if job:
            job.failed_items += 1
            job.updated_at = now
            JobQueue._evaluate_job_completion(session, job)

        session.commit()
        logger.warning(
            "Work item %d (stage=%s) marked failed by %s: [%s] %s",
            work_item_id,
            item.stage,
            worker_id,
            error_code,
            error_message,
        )

    @staticmethod
    def recover_expired_leases(
        session: Session,
        resource_class: str | None = None,
    ) -> int:
        """Reclaim work items whose leases have expired (e.g. worker crashed)."""
        now = utcnow()
        stmt = select(WorkItem).where(
            WorkItem.status == "leased",
            WorkItem.lease_expires_at <= now,
        )
        if resource_class:
            stmt = stmt.where(WorkItem.resource_class == resource_class)

        bind = session.get_bind()
        if bind and bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        expired_items = session.scalars(stmt).all()
        recovered_count = 0
        affected_jobs: dict[str, Job] = {}

        for item in expired_items:
            logger.warning(
                "Recovering expired lease on work_item %d (owner=%s, expired_at=%s)",
                item.id,
                item.lease_owner,
                item.lease_expires_at,
            )
            item.lease_owner = None
            item.lease_expires_at = None
            item.updated_at = now

            if item.attempt_count >= item.max_attempts:
                item.status = "failed"
                item.last_error_code = "LEASE_EXPIRED"
                item.last_error_message = "Worker lease expired and max attempts reached"
                item.completed_at = now
                if item.job:
                    item.job.failed_items += 1
                    item.job.updated_at = now
                    affected_jobs[item.job.id] = item.job
            else:
                item.status = "retry"
                item.available_at = now
                if item.job:
                    item.job.updated_at = now
                    affected_jobs[item.job.id] = item.job

            recovered_count += 1

        if recovered_count > 0:
            for job in affected_jobs.values():
                JobQueue._evaluate_job_completion(session, job)
            session.commit()

        return recovered_count

    @staticmethod
    def get_job_progress(session: Session, job_id: str) -> dict[str, Any] | None:
        """Get aggregate progress and stage breakdown for a job."""
        job = session.get(Job, job_id)
        if not job:
            return None

        # Query counts by stage and status
        counts = session.execute(
            select(WorkItem.stage, WorkItem.status, func.count(WorkItem.id))
            .where(WorkItem.job_id == job_id)
            .group_by(WorkItem.stage, WorkItem.status)
        ).all()

        stages: dict[str, dict[str, int]] = {}
        for stage, status, count in counts:
            if stage not in stages:
                stages[stage] = {}
            stages[stage][status] = count

        return {
            "job_id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "priority": job.priority,
            "requested_by": job.requested_by,
            "total_items": job.total_items,
            "completed_items": job.completed_items,
            "failed_items": job.failed_items,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "stages": stages,
        }

    @staticmethod
    def _evaluate_job_completion(session: Session, job: Job) -> None:
        """Check if all work items are terminal and update job status."""
        active_count = session.scalar(
            select(func.count(WorkItem.id)).where(
                WorkItem.job_id == job.id,
                WorkItem.status.in_(["pending", "leased", "retry"]),
            )
        )
        if active_count == 0:
            now = utcnow()
            job.completed_at = now
            if job.failed_items == 0:
                job.status = "completed"
            elif job.completed_items > 0:
                job.status = "partial"
            else:
                job.status = "failed"
            logger.info(
                "Job %s reached terminal state: %s (completed=%d, failed=%d)",
                job.id,
                job.status,
                job.completed_items,
                job.failed_items,
            )
