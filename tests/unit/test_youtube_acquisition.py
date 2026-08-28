"""Unit tests for services/youtube_acquisition.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.models import Base, TranscriptSegment, VideoFolder
from services.youtube_acquisition import (
    YouTubeAcquisitionService,
    compute_segment_hash,
)

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:05,500
<v Alice>Welcome to the database scaling tutorial.</v>

2
00:00:05,500 --> 00:00:12,200
<v Bob>Today we will discuss PostgreSQL 16 performance.</v>
"""


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestYouTubeAcquisitionService:
    """Test suite for YouTube acquisition and transcript parsing."""

    def test_compute_segment_hash_deterministic(self):
        hash1 = compute_segment_hash("vid123", 0, "Hello world")
        hash2 = compute_segment_hash("vid123", 0, "  Hello   World  ")
        assert hash1 == hash2  # Normalized text matches

        hash3 = compute_segment_hash("vid123", 1, "Hello world")
        assert hash1 != hash3  # Different segment index

    def test_parse_raw_srt_with_speakers(self):
        entries = YouTubeAcquisitionService.parse_raw_srt(SAMPLE_SRT)
        assert len(entries) == 2
        assert entries[0]["start_seconds"] == 0.0
        assert entries[0]["end_seconds"] == 5.5
        assert entries[0]["speaker"] == "Alice"
        assert entries[0]["text"] == "Welcome to the database scaling tutorial."

        assert entries[1]["start_seconds"] == 5.5
        assert entries[1]["end_seconds"] == 12.2
        assert entries[1]["speaker"] == "Bob"
        assert entries[1]["text"] == "Today we will discuss PostgreSQL 16 performance."

    def test_parse_raw_srt_empty_returns_empty_list(self):
        assert YouTubeAcquisitionService.parse_raw_srt("") == []
        assert YouTubeAcquisitionService.parse_raw_srt("   ") == []

    def test_time_to_seconds_parsing(self):
        assert YouTubeAcquisitionService._time_to_seconds("00:01:30.500") == 90.5
        assert YouTubeAcquisitionService._time_to_seconds("01:00:00,000") == 3600.0
        assert YouTubeAcquisitionService._time_to_seconds("45.200") == 45.2

    @patch("subprocess.run")
    def test_discover_channel_videos_subprocess_fallback(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = (
            '{"id": "UC_TEST123", "entries": ['
            '{"id": "v1", "title": "Video 1", "upload_date": "20260101"},'
            '{"id": "v2", "title": "Video 2", "upload_date": "20260102"}'
            "]}"
        )
        mock_run.return_value = mock_proc

        with patch("urllib.request.urlopen", side_effect=Exception("No wrapper")):
            channel_id, videos = YouTubeAcquisitionService.discover_channel_videos("https://youtube.com/@test")

        assert channel_id == "UC_TEST123"
        assert len(videos) == 2
        assert videos[0]["video_id"] == "v1"
        assert videos[1]["title"] == "Video 2"

    @patch("urllib.request.urlopen")
    def test_fetch_video_transcript_from_wrapper(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"transcript": "1\\n00:00:01,000 --> 00:00:04,000\\nHello world"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        segments = YouTubeAcquisitionService.fetch_video_transcript("vid-abc")
        assert len(segments) == 1
        assert segments[0]["segment_index"] == 0
        assert segments[0]["start_seconds"] == 1.0
        assert segments[0]["end_seconds"] == 4.0
        assert segments[0]["text"] == "Hello world"
        assert "content_hash" in segments[0]

    def test_persist_video_and_segments_dual_write(self):
        session = create_in_memory_session()
        segments = [
            {
                "segment_index": 0,
                "start_seconds": 0.0,
                "end_seconds": 10.0,
                "speaker": "Alice",
                "text": "First segment.",
                "normalized_text": "first segment",
                "content_hash": "hash-0",
            },
            {
                "segment_index": 1,
                "start_seconds": 10.0,
                "end_seconds": 25.0,
                "speaker": "Alice",
                "text": "Second segment.",
                "normalized_text": "second segment",
                "content_hash": "hash-1",
            },
        ]

        video = YouTubeAcquisitionService.persist_video_and_segments(
            session=session,
            video_id="vid-test-1",
            title="Test Video Title",
            upload_date="2026-08-27",
            channel_id="chan-test",
            playlist_name="Test Playlist",
            content_type="playlist",
            segments=segments,
        )

        assert video.video_id == "vid-test-1"
        assert video.transcript_with_ts is not None
        assert "[0.0s] First segment." in video.transcript_with_ts
        assert video.transcript_no_ts == "First segment. Second segment."

        # Verify folder association
        folder = session.scalar(select(VideoFolder).where(VideoFolder.video_id == "vid-test-1"))
        assert folder is not None
        assert folder.folder_name == "Test Playlist"

        # Verify transcript segments
        stored_segs = session.scalars(select(TranscriptSegment).where(TranscriptSegment.video_id == "vid-test-1")).all()
        assert len(stored_segs) == 2
        assert stored_segs[0].segment_index == 0
        assert stored_segs[1].segment_index == 1
        assert stored_segs[0].text == "First segment."
