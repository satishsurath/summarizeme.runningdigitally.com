"""Unit tests for summarize stage handler with generation lease admission."""

import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ResourceLease, ResourceLimit, SummaryRun, utcnow
from services.contracts import StructuredSummaryV3
from tests.fixtures.synthetic_transcripts import SAMPLE_STRUCTURED_SUMMARY_DICT
from workers.stages.summary import handle_summary


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestSummaryStage:
    """Test suite for workers/stages/summary.py."""

    @patch("services.summary_service.SummaryService.generate_and_persist_summary")
    def test_handle_summary_acquires_and_releases_lease(self, mock_gen):
        mock_summary = StructuredSummaryV3.model_validate(SAMPLE_STRUCTURED_SUMMARY_DICT)
        mock_run = MagicMock(spec=SummaryRun)
        mock_run.id = "run-1234"
        mock_gen.return_value = (mock_run, mock_summary)

        session = create_in_memory_session()
        # Seed limits
        session.add(
            ResourceLimit(
                resource_class="generation_batch",
                max_in_flight=2,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        session.commit()

        payload = {
            "video_id": "vid-summ-1",
            "model_name": "nemo-qwen3.8-27b-nvfp4",
            "reasoning_effort": "medium",
        }

        outcome = handle_summary(payload, session)

        assert outcome["result"]["video_id"] == "vid-summ-1"
        assert outcome["result"]["summary_run_id"] == "run-1234"
        assert len(outcome["downstream_items"]) == 1
        assert outcome["downstream_items"][0]["stage"] == "embed_summary"
        assert outcome["downstream_items"][0]["resource_class"] == "embedding"

        # Verify lease was released
        active_leases = session.query(ResourceLease).filter(ResourceLease.resource_class == "generation_batch").all()
        assert len(active_leases) == 0

    def test_handle_summary_capacity_full_raises_for_retry(self):
        session = create_in_memory_session()
        # Set max_in_flight=1 and occupy it
        session.add(
            ResourceLimit(
                resource_class="generation_batch",
                max_in_flight=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        session.add(
            ResourceLease(
                id="active-other-lease",
                resource_class="generation_batch",
                owner="other-worker",
                expires_at=utcnow() + datetime.timedelta(seconds=200),
                created_at=utcnow(),
            )
        )
        session.commit()

        payload = {"video_id": "vid-busy"}

        with pytest.raises(RuntimeError, match="Generation capacity at limit"):
            handle_summary(payload, session)
