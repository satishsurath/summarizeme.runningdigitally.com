"""Unit tests for embedding stage handlers (embed_transcript, embed_summary, finalize)."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ResourceLimit, Video, utcnow
from workers.stages.embedding import handle_embed_summary, handle_embed_transcript
from workers.stages.finalize import handle_finalize


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestEmbeddingStages:
    """Test suite for workers/stages/embedding.py and finalize.py."""

    @patch("services.embedding_service.EmbeddingService.embed_and_index_transcript")
    def test_handle_embed_transcript(self, mock_embed):
        mock_embed.return_value = 5

        session = create_in_memory_session()
        session.add(
            ResourceLimit(
                resource_class="embedding",
                max_in_flight=4,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        session.commit()

        payload = {"video_id": "v_stage_ts"}
        outcome = handle_embed_transcript(payload, session)

        assert outcome["result"]["video_id"] == "v_stage_ts"
        assert outcome["result"]["chunks_indexed"] == 5

    @patch("services.embedding_service.EmbeddingService.embed_and_index_summary")
    def test_handle_embed_summary_schedules_finalize(self, mock_embed):
        mock_embed.return_value = 4

        session = create_in_memory_session()
        session.add(
            ResourceLimit(
                resource_class="embedding",
                max_in_flight=4,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        session.commit()

        payload = {"video_id": "v_stage_sum", "summary_run_id": "run-abc"}
        outcome = handle_embed_summary(payload, session)

        assert outcome["result"]["video_id"] == "v_stage_sum"
        assert outcome["result"]["chunks_indexed"] == 4
        assert len(outcome["downstream_items"]) == 1
        assert outcome["downstream_items"][0]["stage"] == "finalize"

    def test_handle_finalize(self):
        session = create_in_memory_session()
        video = Video(video_id="v_fin", title="Finalize Video")
        session.add(video)
        session.commit()

        payload = {"video_id": "v_fin"}
        outcome = handle_finalize(payload, session)

        assert outcome["result"]["video_id"] == "v_fin"
        assert outcome["result"]["status"] == "ready"
