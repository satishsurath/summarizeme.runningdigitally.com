"""Tests for youtube_utils.py — transcript downloading and parsing."""

from youtube_utils import build_transcript_variants, parse_srt, srt_time_to_seconds


class TestParseSRT:
    """Tests for SRT subtitle parsing."""

    def test_single_entry(self):
        """A single SRT entry parses correctly."""
        srt = """1
00:00:01,000 --> 00:00:04,000
Hello world

"""
        entries = parse_srt(srt)
        assert len(entries) == 1
        assert entries[0]["text"] == "Hello world"
        assert entries[0]["start"] == 1.0

    def test_multiple_entries(self):
        """Multiple entries parse correctly."""
        srt = """1
00:00:01,000 --> 00:00:04,000
First

2
00:00:05,000 --> 00:00:08,000
Second

"""
        entries = parse_srt(srt)
        assert len(entries) == 2

    def test_empty_srt(self):
        """Empty SRT returns empty list."""
        entries = parse_srt("")
        assert entries == []

    def test_srt_with_timestamps(self):
        """Timestamps are converted to seconds."""
        srt = """1
00:01:30,500 --> 00:01:35,750
Test line

"""
        entries = parse_srt(srt)
        assert entries[0]["start"] == 90.5


class TestSrtTimeToSeconds:
    """Tests for time conversion."""

    def test_hours_minutes_seconds(self):
        """Full timestamp converts correctly."""
        assert srt_time_to_seconds("01:33:34,234") == 5614.234

    def test_minutes_seconds(self):
        """Short timestamp converts correctly."""
        assert srt_time_to_seconds("00:00:00,500") == 0.5

    def test_zero_timestamp(self):
        """Zero timestamp returns zero."""
        assert srt_time_to_seconds("00:00:00,000") == 0.0


class TestBuildTranscriptVariants:
    """Tests for transcript variant building."""

    def test_builds_both_variants(self):
        """Returns both timestamped and plain transcript."""
        entries = [
            {"text": "Hello", "start": 1.0, "duration": 3.0},
            {"text": "World", "start": 4.0, "duration": 2.0},
        ]
        with_ts, _no_ts = build_transcript_variants(entries)
        assert "Hello" in with_ts
        assert "World" in with_ts
        assert "1.0" in with_ts or "00:00:01" in with_ts

    def test_no_ts_has_no_timestamps(self):
        """Plain transcript should not contain timestamp markers."""
        entries = [{"text": "Clean text", "start": 0.0, "duration": 1.0}]
        _, no_ts = build_transcript_variants(entries)
        assert "Clean text" in no_ts

    def test_empty_entries(self):
        """Empty entries return empty strings."""
        with_ts, no_ts = build_transcript_variants([])
        assert with_ts == ""
        assert no_ts == ""
