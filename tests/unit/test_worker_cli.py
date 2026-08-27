"""Unit tests for workers/main.py worker loop and handler execution."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base
from services.job_queue import JobQueue
from workers.main import execute_work_item, register_stage_handler


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestWorkerCLI:
    """Test suite for worker stage handler execution and error recovery."""

    def test_execute_work_item_with_registered_handler(self):
        session = create_in_memory_session()

        # Register a mock handler
        def mock_discover_handler(payload, db_session):
            return {
                "result": {"channels": 1},
                "downstream_items": [{"stage": "transcript", "resource_class": "youtube", "item_key": "vid-1"}],
            }

        register_stage_handler("discover", mock_discover_handler)

        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "discover", "resource_class": "control", "item_key": "chan-1"},
            ],
        )
        claimed = JobQueue.claim(session, resource_class="control", worker_id="worker-test")
        assert claimed is not None

        # Execute
        execute_work_item(claimed, session)

        progress = JobQueue.get_job_progress(session, job.id)
        assert progress is not None
        assert progress["completed_items"] == 1
        assert progress["total_items"] == 2  # discover + 1 downstream transcript

    def test_execute_work_item_handler_exception_triggers_retry(self):
        session = create_in_memory_session()

        def failing_handler(payload, db_session):
            raise ConnectionError("External service failed")

        register_stage_handler("failing_stage", failing_handler)

        job = JobQueue.create_job(
            session=session,
            job_type="channel_ingest",
            initial_work_items=[
                {"stage": "failing_stage", "resource_class": "control", "item_key": "fail-1"},
            ],
        )
        claimed = JobQueue.claim(session, resource_class="control", worker_id="worker-test")
        assert claimed is not None

        execute_work_item(claimed, session)

        progress = JobQueue.get_job_progress(session, job.id)
        assert progress is not None
        assert progress["stages"]["failing_stage"].get("retry") == 1
