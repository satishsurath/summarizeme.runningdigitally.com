"""Unit tests for services/embedding_service.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.models import Base, ContentChunk, SummaryRun, TranscriptSegment, Video
from services.contracts import StructuredSummaryV3
from services.embedding_service import (
    EmbeddingService,
    compute_chunk_hash,
    estimate_token_count,
    pack_embedding_batch,
)
from tests.fixtures.synthetic_transcripts import (
    SAMPLE_STRUCTURED_SUMMARY_DICT,
    SHORT_TECH_TRANSCRIPT,
    SYNTHETIC_768_DIM_VECTOR,
)


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestEmbeddingService:
    """Test suite for batch packing, prefixing, chunking, and vector indexing."""

    def test_estimate_token_count(self):
        assert estimate_token_count("") == 0
        assert estimate_token_count("abcd") == 1
        assert estimate_token_count("a" * 400) == 100

    def test_compute_chunk_hash_deterministic(self):
        h1 = compute_chunk_hash("v1", "transcript", 0, "Hello world")
        h2 = compute_chunk_hash("v1", "transcript", 0, " Hello world ")
        assert h1 == h2

        h3 = compute_chunk_hash("v1", "transcript", 1, "Hello world")
        assert h1 != h3

    def test_pack_embedding_batch_limits(self):
        # 20 short strings with default Nemo limit of 8
        texts = [f"Text sequence number {i}" for i in range(20)]
        batches = pack_embedding_batch(texts)

        assert len(batches) == 3
        assert len(batches[0]) == 8
        assert len(batches[1]) == 8
        assert len(batches[2]) == 4

    def test_pack_embedding_batch_oversize_split(self):
        # One huge string that exceeds 8192 tokens
        huge_text = ("word " * 10000).strip()
        batches = pack_embedding_batch([huge_text], max_tokens=1000)
        assert len(batches) >= 5
        for b in batches:
            assert len(b) <= 8

    @patch("httpx.Client.post")
    def test_embed_texts_prefixing_and_validation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"embedding": SYNTHETIC_768_DIM_VECTOR},
                {"embedding": SYNTHETIC_768_DIM_VECTOR},
            ]
        }
        mock_post.return_value = mock_resp

        vectors = EmbeddingService.embed_texts(["Postgres vector search", "HNSW indexes"], is_query=False)

        assert len(vectors) == 2
        assert len(vectors[0]) == 768

        # Verify task prefix in HTTP payload
        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["input"][0].startswith("search_document: ")
        assert call_payload["input"][1].startswith("search_document: ")

    @patch("httpx.Client.post")
    def test_embed_texts_invalid_dimensions_raises(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Only 512 dimensions instead of 768
        mock_resp.json.return_value = {"data": [{"embedding": [0.1] * 512}]}
        mock_post.return_value = mock_resp

        with pytest.raises(ValueError, match="expected 768 dimensions, received 512"):
            EmbeddingService.embed_texts(["Test"])

    def test_chunk_transcript_segments(self):
        chunks = EmbeddingService.chunk_transcript_segments(SHORT_TECH_TRANSCRIPT, target_tokens=100)
        assert len(chunks) >= 1
        first_chunk = chunks[0]
        assert first_chunk["chunk_type"] == "transcript"
        assert first_chunk["start_seconds"] == 0.0
        assert first_chunk["end_seconds"] >= 5.0
        assert "Welcome" in first_chunk["text"]

    def test_chunk_structured_summary_extracts_sections_omits_reasoning(self):
        summary = StructuredSummaryV3.model_validate(SAMPLE_STRUCTURED_SUMMARY_DICT)
        chunks = EmbeddingService.chunk_structured_summary(summary)

        types = [c["chunk_type"] for c in chunks]
        assert "summary_overview" in types
        assert "summary_topic" in types
        assert "summary_chapter" in types
        assert "summary_detail" in types

        # Ensure no thinking tags or traces in chunks
        for c in chunks:
            assert "<think>" not in c["text"]
            assert "</think>" not in c["text"]

    @patch("services.embedding_service.EmbeddingService.embed_texts")
    def test_embed_and_index_transcript(self, mock_embed):
        mock_embed.return_value = [SYNTHETIC_768_DIM_VECTOR, SYNTHETIC_768_DIM_VECTOR]

        session = create_in_memory_session()
        video = Video(video_id="v_embed_test", title="Embedding Test Video")
        session.add(video)

        for i, s in enumerate(SHORT_TECH_TRANSCRIPT):
            seg = TranscriptSegment(
                video_id="v_embed_test",
                segment_index=i,
                start_seconds=s["start_seconds"],
                end_seconds=s["end_seconds"],
                speaker=s.get("speaker"),
                text=s["text"],
                normalized_text=s["text"].lower(),
                content_hash=f"hash-{i}",
            )
            session.add(seg)
        session.commit()

        count = EmbeddingService.embed_and_index_transcript(session=session, video_id="v_embed_test")
        assert count >= 1

        stored_chunks = session.scalars(
            select(ContentChunk).where(ContentChunk.video_id == "v_embed_test", ContentChunk.chunk_type == "transcript")
        ).all()
        assert len(stored_chunks) == count
        assert stored_chunks[0].embedding == SYNTHETIC_768_DIM_VECTOR

    @patch("services.embedding_service.EmbeddingService.embed_texts")
    def test_embed_and_index_summary(self, mock_embed):
        mock_embed.return_value = [SYNTHETIC_768_DIM_VECTOR] * 6

        session = create_in_memory_session()
        video = Video(video_id="v_sum_embed", title="Summary Embed Test")
        session.add(video)

        summary_run = SummaryRun(
            video_id="v_sum_embed",
            model_name="nemo-qwen3.8-27b-nvfp4",
            reasoning_effort="medium",
            structured_summary=SAMPLE_STRUCTURED_SUMMARY_DICT,
            status="completed",
        )
        session.add(summary_run)
        session.commit()

        count = EmbeddingService.embed_and_index_summary(session=session, video_id="v_sum_embed")
        assert count >= 1

        stored_summary_chunks = session.scalars(
            select(ContentChunk).where(
                ContentChunk.video_id == "v_sum_embed",
                ContentChunk.chunk_type.startswith("summary_"),
            )
        ).all()
        assert len(stored_summary_chunks) == count
