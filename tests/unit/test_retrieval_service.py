"""Unit tests for services/retrieval_service.py."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ContentChunk, Video, VideoFolder
from services.retrieval_service import (
    RetrievalService,
    cosine_similarity,
)
from tests.fixtures.synthetic_transcripts import (
    SYNTHETIC_768_DIM_VECTOR,
)


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestRetrievalService:
    """Test suite for hybrid vector + FTS retrieval with RRF fusion."""

    def test_cosine_similarity(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]

        assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-6
        assert abs(cosine_similarity(v1, v3) - 0.0) < 1e-6
        assert cosine_similarity([], v1) == 0.0

    @patch("services.embedding_service.EmbeddingService.embed_texts")
    def test_retrieve_context_hybrid_ranking(self, mock_embed):
        mock_embed.return_value = [SYNTHETIC_768_DIM_VECTOR]

        session = create_in_memory_session()
        video = Video(video_id="v_pg_opt", title="Postgres 16 Indexing")
        session.add(video)

        # Chunk 1: High semantic match
        chunk1 = ContentChunk(
            video_id="v_pg_opt",
            chunk_type="transcript",
            sequence_index=0,
            start_seconds=0.0,
            end_seconds=30.0,
            text="PostgreSQL 16 performance optimization with HNSW vector indexing.",
            token_count=12,
            content_hash="h1",
            embedding=SYNTHETIC_768_DIM_VECTOR,
        )
        # Chunk 2: Orthogonal vector
        chunk2 = ContentChunk(
            video_id="v_pg_opt",
            chunk_type="transcript",
            sequence_index=1,
            start_seconds=30.0,
            end_seconds=60.0,
            text="Unrelated cooking recipe about baking sourdough bread.",
            token_count=10,
            content_hash="h2",
            embedding=[-x for x in SYNTHETIC_768_DIM_VECTOR],
        )
        session.add_all([chunk1, chunk2])
        session.commit()

        results = RetrievalService.retrieve_context(
            session=session,
            query="PostgreSQL vector performance",
            scope_type="video",
            scope_id="v_pg_opt",
            top_k=5,
        )

        assert len(results) == 2
        assert results[0]["chunk_id"] == chunk1.id
        assert results[0]["score"] > results[1]["score"]
        assert results[0]["start_seconds"] == 0.0

    @patch("services.embedding_service.EmbeddingService.embed_texts")
    def test_retrieve_context_channel_scoping(self, mock_embed):
        mock_embed.return_value = [SYNTHETIC_768_DIM_VECTOR]

        session = create_in_memory_session()
        folder = VideoFolder(
            folder_name="AI Channel",
            original_playlist_id="chan_ai",
            video_id="v_ai_1",
            content_type="playlist",
        )
        session.add(folder)

        chunk_in_channel = ContentChunk(
            video_id="v_ai_1",
            chunk_type="transcript",
            sequence_index=0,
            text="AI and LLM architectures.",
            content_hash="h_ai",
            embedding=SYNTHETIC_768_DIM_VECTOR,
        )
        chunk_outside = ContentChunk(
            video_id="v_other_chan",
            chunk_type="transcript",
            sequence_index=0,
            text="Other channel video.",
            content_hash="h_other",
            embedding=SYNTHETIC_768_DIM_VECTOR,
        )
        session.add_all([chunk_in_channel, chunk_outside])
        session.commit()

        results = RetrievalService.retrieve_context(
            session=session,
            query="AI architectures",
            scope_type="channel",
            scope_id="AI Channel",
            top_k=5,
        )

        assert len(results) == 1
        assert results[0]["video_id"] == "v_ai_1"
