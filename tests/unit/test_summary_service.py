"""Unit tests for services/summary_service.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.models import Base, SummariesV2, SummaryRun, Video
from services.contracts import StructuredSummaryV3
from services.summary_service import (
    SummaryService,
    project_summary_to_legacy_fields,
)
from tests.fixtures.synthetic_transcripts import (
    SAMPLE_STRUCTURED_SUMMARY_DICT,
    SHORT_TECH_TEXT,
)


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestSummaryService:
    """Test suite for 9-section structured summary generation and projection."""

    def test_project_summary_to_legacy_fields(self):
        summary = StructuredSummaryV3.model_validate(SAMPLE_STRUCTURED_SUMMARY_DICT)
        legacy = project_summary_to_legacy_fields(summary)

        assert "concise_summary" in legacy
        assert "key_topics" in legacy
        assert "important_takeaways" in legacy
        assert "comprehensive_notes" in legacy

        assert legacy["concise_summary"].startswith("This video details")
        assert "### PostgreSQL Vector Optimization" in legacy["key_topics"]
        assert "**Main Thesis:**" in legacy["important_takeaways"]
        assert "### Chapters & Timeline" in legacy["comprehensive_notes"]

    @patch("httpx.Client.post")
    def test_generate_structured_summary_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(SAMPLE_STRUCTURED_SUMMARY_DICT),
                        "reasoning_content": "Detailed reasoning about pgvector HNSW vs IVFFlat...",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 1500,
                "completion_tokens": 600,
                "completion_tokens_details": {"reasoning_tokens": 200},
            },
        }
        mock_post.return_value = mock_resp

        summary, reasoning, usage, _errors = SummaryService.generate_structured_summary(
            transcript_text=SHORT_TECH_TEXT,
            video_title="PostgreSQL 16 Vector Optimization",
            model_name="nemo-qwen3.8-27b-nvfp4",
            reasoning_effort="medium",
        )

        assert summary.schema_version == "summary.v3"
        assert reasoning == "Detailed reasoning about pgvector HNSW vs IVFFlat..."
        assert usage["prompt_tokens"] == 1500
        assert usage["completion_tokens"] == 600
        assert usage["reasoning_tokens"] == 200

    @patch("httpx.Client.post")
    def test_generate_structured_summary_json_in_markdown_fences(self, mock_post):
        fenced_json = f"```json\n{json.dumps(SAMPLE_STRUCTURED_SUMMARY_DICT)}\n```"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": fenced_json}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        }
        mock_post.return_value = mock_resp

        summary, _, _, _ = SummaryService.generate_structured_summary(
            transcript_text=SHORT_TECH_TEXT,
            video_title="Fenced Test",
        )
        assert summary.schema_version == "summary.v3"

    @patch("httpx.Client.post")
    def test_generate_and_persist_summary(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(SAMPLE_STRUCTURED_SUMMARY_DICT),
                        "reasoning_content": "Reasoning trace...",
                    }
                }
            ],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 400},
        }
        mock_post.return_value = mock_resp

        session = create_in_memory_session()
        video = Video(
            video_id="vid_persisted",
            title="Postgres Indexing",
            transcript_no_ts=SHORT_TECH_TEXT,
        )
        session.add(video)
        session.commit()

        summary_run, _summary = SummaryService.generate_and_persist_summary(
            session=session,
            video_id="vid_persisted",
            model_name="nemo-qwen3.8-27b-nvfp4",
            reasoning_effort="medium",
        )

        assert summary_run.id is not None
        assert summary_run.status == "completed"
        assert summary_run.reasoning_output == "Reasoning trace..."

        # Verify legacy SummariesV2 projection created
        v2 = session.scalar(select(SummariesV2).where(SummariesV2.video_id == "vid_persisted"))
        assert v2 is not None
        assert v2.concise_summary is not None
        assert v2.concise_summary.startswith("This video details")

        # Verify SummaryRun persisted
        sr = session.scalar(select(SummaryRun).where(SummaryRun.video_id == "vid_persisted"))
        assert sr is not None
        assert sr.model_name == "nemo-qwen3.8-27b-nvfp4"
        assert sr.generation_profile_hash is not None

        second_run, _ = SummaryService.generate_and_persist_summary(
            session=session,
            video_id="vid_persisted",
            model_name="nemo-qwen3.8-27b-nvfp4",
            reasoning_effort="medium",
        )
        all_runs = session.scalars(select(SummaryRun).where(SummaryRun.video_id == "vid_persisted")).all()
        assert len(all_runs) == 2
        assert second_run.id != sr.id

    @patch("httpx.Client.post")
    def test_generate_and_persist_summary_validation_failure_review_required(self, mock_post):
        # Create summary with hallucinated quote not in transcript
        bad_summary = dict(SAMPLE_STRUCTURED_SUMMARY_DICT)
        bad_summary["evidence"] = [
            {
                "id": "E1",
                "start_seconds": 10.0,
                "end_seconds": 20.0,
                "speaker": "Speaker",
                "excerpt": "This exact sentence does not appear anywhere in the video transcript at all.",
                "youtube_url": None,
            }
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(bad_summary)}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 200},
        }
        mock_post.return_value = mock_resp

        session = create_in_memory_session()
        video = Video(
            video_id="vid_bad_quotes",
            title="Bad Quotes Test",
            transcript_no_ts=SHORT_TECH_TEXT,
        )
        session.add(video)
        session.commit()

        summary_run, _ = SummaryService.generate_and_persist_summary(
            session=session,
            video_id="vid_bad_quotes",
            model_name="nemo-qwen3.8-27b-nvfp4",
        )

        assert summary_run.status == "review_required"
        assert summary_run.validation_errors is not None
        assert len(summary_run.validation_errors) > 0
        assert any("Ungrounded evidence quote" in err for err in summary_run.validation_errors)

        # Ensure legacy SummariesV2 was NOT written for invalid run
        v2 = session.scalar(select(SummariesV2).where(SummariesV2.video_id == "vid_bad_quotes"))
        assert v2 is None
