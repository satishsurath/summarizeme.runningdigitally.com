"""Unit tests for discovery and transcript stage handlers."""

from __future__ import annotations

import contextlib
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.models import Base, ExternalRateLimit, TranscriptSegment, Video
from workers.stages.discovery import handle_discovery
from workers.stages.transcript import handle_transcript


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestDiscoveryStage:
    """Test suite for workers/stages/discovery.py."""

    @patch("services.youtube_acquisition.YouTubeAcquisitionService.discover_channel_videos")
    def test_handle_discovery_generates_transcript_work_items(self, mock_discover):
        mock_discover.return_value = (
            "UC_CHAN123",
            [
                {"video_id": "v1", "title": "Intro to AI", "upload_date": "20260101"},
                {"video_id": "v2", "title": "Advanced RAG", "upload_date": "20260102"},
            ],
        )

        session = create_in_memory_session()
        payload = {"channel_url": "https://youtube.com/@myaichannel", "playlist_name": "AI Course"}
        outcome = handle_discovery(payload, session)

        assert outcome["result"]["channel_id"] == "UC_CHAN123"
        assert outcome["result"]["total_videos"] == 2
        assert len(outcome["downstream_items"]) == 2

        item1 = outcome["downstream_items"][0]
        assert item1["stage"] == "transcript"
        assert item1["resource_class"] == "youtube"
        assert item1["item_key"] == "v1"
        assert item1["payload"]["playlist_name"] == "AI Course"


class TestTranscriptStage:
    """Test suite for workers/stages/transcript.py."""

    @patch("services.youtube_acquisition.YouTubeAcquisitionService.fetch_video_transcript")
    def test_handle_transcript_success_and_downstream_enqueues(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "segment_index": 0,
                "start_seconds": 0.0,
                "end_seconds": 15.0,
                "speaker": "Presenter",
                "text": "Hello and welcome.",
                "normalized_text": "hello and welcome",
                "content_hash": "hash-abc",
            }
        ]

        session = create_in_memory_session()
        payload = {
            "video_id": "v123",
            "title": "Welcome Video",
            "channel_id": "UC_TEST",
            "playlist_name": "Test Playlist",
            "content_type": "video",
        }

        outcome = handle_transcript(payload, session)

        assert outcome["result"]["video_id"] == "v123"
        assert outcome["result"]["segments_count"] == 1
        assert len(outcome["downstream_items"]) == 2

        # Verify stages generated
        stages = [item["stage"] for item in outcome["downstream_items"]]
        assert "summarize" in stages
        assert "embed_transcript" in stages

        # Verify database record
        video = session.get(Video, "v123")
        assert video is not None
        assert video.title == "Welcome Video"
        segments = session.scalars(select(TranscriptSegment).where(TranscriptSegment.video_id == "v123")).all()
        assert len(segments) == 1

    @patch("services.youtube_acquisition.YouTubeAcquisitionService.fetch_video_transcript")
    def test_handle_transcript_429_trips_circuit_breaker(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("HTTP 429: Too Many Requests from YouTube")

        session = create_in_memory_session()
        payload = {"video_id": "v_throttled", "title": "Throttled Video"}

        with contextlib.suppress(RuntimeError):
            handle_transcript(payload, session)

        # Circuit breaker should be tripped
        rate_limit = session.get(ExternalRateLimit, "youtube")
        assert rate_limit is not None
        assert rate_limit.failure_count >= 1
        assert rate_limit.backoff_until is not None

    @patch("services.youtube_acquisition.YouTubeAcquisitionService.fetch_video_transcript")
    def test_handle_transcript_empty_captions_handling(self, mock_fetch):
        mock_fetch.return_value = []

        session = create_in_memory_session()
        payload = {"video_id": "v_no_subs", "title": "Silent Video"}

        outcome = handle_transcript(payload, session)
        assert outcome["result"]["status"] == "no_captions_available"
        assert outcome["downstream_items"] == []

        # Video row is still recorded
        video = session.get(Video, "v_no_subs")
        assert video is not None
