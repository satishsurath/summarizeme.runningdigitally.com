"""Unit tests for services/job_queue.py."""

from __future__ import annotations

import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Job, WorkItem, ensure_utc, utcnow
from services.job_queue import JobQueue


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestJobQueue:
    """Test suite for JobQueue lifecycle methods."""

    def test_create_job_with_initial_items(self):
        session = create_in_memory_session()
        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            requested_by="admin@test.com",
            payload={"channel_url": "https://youtube.com/@test"},
            idempotency_key="idemp-123",
            initial_work_items=[
                {
                    "stage": "discover",
                    "resource_class": "control",
                    "item_key": "https://youtube.com/@test",
                }
            ],
        )

        assert job.id is not None
        assert job.job_type == "channel_ingest"
        assert job.status == "pending"
        assert job.total_items == 1
        assert len(job.work_items) == 1
        assert job.work_items[0].stage == "discover"
        assert job.work_items[0].status == "pending"

    def test_create_job_idempotent_duplicate_returns_existing(self):
        session = create_in_memory_session()
        job1 = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            idempotency_key="unique-key-1",
        )
        job2 = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            idempotency_key="unique-key-1",
        )
        assert job1.id == job2.id

    def test_claim_work_item(self):
        session = create_in_memory_session()
        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "discover", "resource_class": "control", "item_key": "item-1", "priority": 10},
                {"stage": "discover", "resource_class": "control", "item_key": "item-2", "priority": 5},
            ],
        )

        # Claim highest priority item
        claimed = JobQueue.claim(session, resource_class="control", worker_id="worker-1", lease_seconds=300)
        assert claimed is not None
        assert claimed.item_key == "item-1"
        assert claimed.status == "leased"
        assert claimed.lease_owner == "worker-1"
        assert claimed.attempt_count == 1
        assert claimed.lease_expires_at is not None

        # Parent job should transition to running
        updated_job = session.get(Job, job.id)
        assert updated_job is not None
        assert updated_job.status == "running"

    def test_claim_no_matching_resource_returns_none(self):
        session = create_in_memory_session()
        JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "transcript", "resource_class": "youtube", "item_key": "vid-1"},
            ],
        )
        claimed = JobQueue.claim(session, resource_class="generation", worker_id="worker-gen")
        assert claimed is None

    def test_renew_lease(self):
        session = create_in_memory_session()
        JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "discover", "resource_class": "control", "item_key": "item-1"},
            ],
        )
        claimed = JobQueue.claim(session, resource_class="control", worker_id="worker-1", lease_seconds=100)
        assert claimed is not None
        initial_expiry = claimed.lease_expires_at

        # Renew lease with worker-1
        renewed = JobQueue.renew(session, claimed.id, worker_id="worker-1", lease_seconds=500)
        assert renewed is True
        refreshed = session.get(WorkItem, claimed.id)
        assert refreshed is not None
        assert refreshed.lease_expires_at is not None
        refreshed_exp = ensure_utc(refreshed.lease_expires_at)
        init_exp = ensure_utc(initial_expiry)
        assert refreshed_exp is not None and init_exp is not None
        assert refreshed_exp > init_exp

        # Wrong worker fails renewal
        assert JobQueue.renew(session, claimed.id, worker_id="wrong-worker") is False

    def test_complete_work_item_and_enqueue_downstream(self):
        session = create_in_memory_session()
        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "discover", "resource_class": "control", "item_key": "chan-1"},
            ],
        )
        claimed = JobQueue.claim(session, resource_class="control", worker_id="worker-1")
        assert claimed is not None

        downstream = [
            {"stage": "transcript", "resource_class": "youtube", "item_key": "vid-101"},
            {"stage": "transcript", "resource_class": "youtube", "item_key": "vid-102"},
        ]
        JobQueue.complete(
            session=session,
            work_item_id=claimed.id,
            worker_id="worker-1",
            result={"videos_found": 2},
            downstream_items=downstream,
        )

        refreshed_item = session.get(WorkItem, claimed.id)
        assert refreshed_item is not None
        assert refreshed_item.status == "completed"
        assert refreshed_item.result == {"videos_found": 2}

        refreshed_job = session.get(Job, job.id)
        assert refreshed_job is not None
        assert refreshed_job.completed_items == 1
        assert refreshed_job.total_items == 3  # 1 initial + 2 downstream

        # Verify downstream items exist in pending state
        downstream_items = (
            session.query(WorkItem).filter(WorkItem.job_id == job.id, WorkItem.stage == "transcript").all()
        )
        assert len(downstream_items) == 2
        assert all(wi.status == "pending" for wi in downstream_items)

    def test_retry_and_max_attempts_failure(self):
        session = create_in_memory_session()
        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "transcript", "resource_class": "youtube", "item_key": "vid-1", "max_attempts": 2},
            ],
        )

        # Attempt 1 -> retry
        claimed = JobQueue.claim(session, resource_class="youtube", worker_id="worker-yt")
        assert claimed is not None
        retried = JobQueue.retry(
            session=session,
            work_item_id=claimed.id,
            worker_id="worker-yt",
            delay_seconds=30,
            error_code="TIMEOUT",
            error_message="Connection timed out",
        )
        assert retried is True
        item = session.get(WorkItem, claimed.id)
        assert item is not None
        assert item.status == "retry"
        assert item.attempt_count == 1

        # Attempt 2 -> max attempts reached -> fail
        item.available_at = utcnow() - datetime.timedelta(seconds=1)
        session.commit()
        claimed2 = JobQueue.claim(session, resource_class="youtube", worker_id="worker-yt")
        assert claimed2 is not None

        retried2 = JobQueue.retry(
            session=session,
            work_item_id=claimed2.id,
            worker_id="worker-yt",
            error_code="TIMEOUT",
            error_message="Connection timed out again",
        )
        assert retried2 is False
        item = session.get(WorkItem, claimed2.id)
        assert item is not None
        assert item.status == "failed"

        refreshed_job = session.get(Job, job.id)
        assert refreshed_job is not None
        assert refreshed_job.failed_items == 1
        assert refreshed_job.status == "failed"

    def test_recover_expired_leases(self):
        session = create_in_memory_session()
        JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "summarize", "resource_class": "generation", "item_key": "vid-1"},
            ],
        )
        claimed = JobQueue.claim(session, resource_class="generation", worker_id="worker-gen", lease_seconds=10)
        assert claimed is not None

        # Manually expire the lease
        claimed.lease_expires_at = utcnow() - datetime.timedelta(seconds=1)
        session.commit()

        recovered = JobQueue.recover_expired_leases(session, resource_class="generation")
        assert recovered == 1

        refreshed_item = session.get(WorkItem, claimed.id)
        assert refreshed_item is not None
        assert refreshed_item.status == "retry"
        assert refreshed_item.lease_owner is None
        assert refreshed_item.lease_expires_at is None

    def test_get_job_progress(self):
        session = create_in_memory_session()
        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            requested_by="user@test.com",
            initial_work_items=[
                {"stage": "transcript", "resource_class": "youtube", "item_key": "vid-1"},
                {"stage": "transcript", "resource_class": "youtube", "item_key": "vid-2"},
            ],
        )

        progress = JobQueue.get_job_progress(session, job.id)
        assert progress is not None
        assert progress["job_id"] == job.id
        assert progress["total_items"] == 2
        assert progress["completed_items"] == 0
        assert progress["stages"]["transcript"]["pending"] == 2
