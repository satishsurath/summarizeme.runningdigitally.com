"""YouTube acquisition and transcript normalization service.

Handles channel/playlist discovery, timestamped transcript retrieval with speaker attribution,
segment content hashing, and dual-write persistence to Video and TranscriptSegment models.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import urllib.request
from typing import Any
from urllib.parse import quote

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import TranscriptSegment, Video, VideoFolder, utcnow
from services.contracts import normalize_transcript_text

logger = logging.getLogger(__name__)


def compute_segment_hash(video_id: str, segment_index: int, text: str) -> str:
    """Compute deterministic SHA-256 hash for transcript segment content."""
    payload = f"{video_id}:{segment_index}:{normalize_transcript_text(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class YouTubeAcquisitionService:
    """Service for YouTube video discovery, transcript fetching, and database persistence."""

    @staticmethod
    def discover_channel_videos(channel_url: str) -> tuple[str, list[dict[str, Any]]]:
        """Discover all videos from a channel or playlist.

        Returns (channel_id, list of video dicts with keys 'video_id', 'title', 'upload_date').
        """
        data = None

        # 1. Try host wrapper if configured
        wrapper_url = os.getenv("YTDLP_WRAPPER_URL", "http://host.docker.internal:9876")
        try:
            req = urllib.request.Request(f"{wrapper_url}/playlist?url={quote(channel_url)}")
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
        except Exception:
            pass

        # 2. Fallback to local subprocess yt-dlp
        if data is None:
            cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", "--", channel_url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"yt-dlp discovery failed: {result.stderr}")
            data = json.loads(result.stdout)

        channel_id = data.get("id", "unknown_channel_id")
        entries = data.get("entries", [])

        # Handle single video URL
        url_types = ["youtube.com/watch", "youtu.be/", "youtube.com/shorts/", "youtube.com/live/"]
        is_single_video = not entries and data.get("id") and any(k in channel_url for k in url_types)

        if is_single_video:
            vid_id = data.get("video_id") or data.get("id")
            vid_title = data.get("title", "Untitled")
            upload_date = data.get("upload_date", "UnknownDate")
            videos = [{"video_id": vid_id, "title": vid_title, "upload_date": upload_date}]
        else:
            videos = []
            for entry in entries:
                if entry is None:
                    continue
                vid_id = entry.get("video_id") or entry.get("id")
                vid_title = entry.get("title", "Untitled")
                upload_date = entry.get("upload_date", "UnknownDate")
                if vid_id:
                    videos.append({"video_id": vid_id, "title": vid_title, "upload_date": upload_date})

        logger.info("Discovered %d videos for channel/playlist %s", len(videos), channel_id)
        return channel_id, videos

    @staticmethod
    def parse_raw_srt(srt_text: str) -> list[dict[str, Any]]:
        """Parse raw SRT/VTT text into raw segment entries with start, end, speaker, and text."""
        if not srt_text or not srt_text.strip():
            return []

        entries: list[dict[str, Any]] = []
        clean_srt = re.sub(r"\r\n", "\n", srt_text)
        blocks = clean_srt.strip().split("\n\n")

        for block in blocks:
            lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
            if not lines:
                continue

            time_idx = next((i for i, line_str in enumerate(lines) if "-->" in line_str), None)
            if time_idx is None:
                continue

            try:
                start_str, end_str = lines[time_idx].split("-->")
                start_sec = YouTubeAcquisitionService._time_to_seconds(start_str)
                end_sec = YouTubeAcquisitionService._time_to_seconds(end_str)

                # Collect text following the timestamp line
                raw_text = " ".join(lines[time_idx + 1 :]).strip()
                # Strip HTML/VTT tags e.g. <v Speaker> or <c.color>
                speaker = None
                speaker_match = re.match(r"<v\s+([^>]+)>", raw_text)
                if speaker_match:
                    speaker = speaker_match.group(1).strip()

                text = re.sub(r"<[^>]+>", "", raw_text).strip()
                if text and end_sec >= start_sec:
                    entries.append(
                        {
                            "start_seconds": start_sec,
                            "end_seconds": end_sec,
                            "speaker": speaker,
                            "text": text,
                        }
                    )
            except Exception:
                continue

        return entries

    @staticmethod
    def fetch_video_transcript(video_id: str) -> list[dict[str, Any]]:
        """Fetch transcript via host wrapper or yt-dlp and return normalized segments."""
        raw_srt = ""
        wrapper_url = os.getenv("YTDLP_TRANSCRIPT_URL", "http://host.docker.internal:9877")

        # 1. Try host wrapper
        try:
            payload = json.dumps({"video_id": video_id}).encode()
            req = urllib.request.Request(
                f"{wrapper_url}/transcript",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    raw_srt = data.get("transcript", "")
        except Exception as exc:
            logger.debug("Transcript wrapper request failed for %s: %s", video_id, exc)

        # 2. Subprocess fallback
        if not raw_srt:
            try:
                cmd = [
                    "yt-dlp",
                    "--skip-download",
                    "--write-auto-subs",
                    "--write-subs",
                    "--sub-lang",
                    "en",
                    "--sub-format",
                    "vtt/srt",
                    "--output",
                    "-",
                    "--",
                    f"https://www.youtube.com/watch?v={video_id}",
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if proc.returncode == 0 and proc.stdout:
                    raw_srt = proc.stdout
                elif proc.returncode != 0:
                    stderr = proc.stderr or ""
                    if "429" in stderr or "Too Many Requests" in stderr or "rate limit" in stderr.lower():
                        raise RuntimeError(f"RATE_LIMIT_429: YouTube throttled request for {video_id}: {stderr[:200]}")
                    elif "Private video" in stderr or "Video unavailable" in stderr or "removed" in stderr.lower():
                        raise ValueError(f"UNAVAILABLE_VIDEO: Video {video_id} is private or deleted: {stderr[:200]}")
                    elif "no subtitles" in stderr.lower() or "no automatic captions" in stderr.lower():
                        logger.info("No captions available for video %s", video_id)
                        raw_srt = ""
                    else:
                        logger.warning("yt-dlp transcript fetch non-zero exit for %s: %s", video_id, stderr[:200])
            except (RuntimeError, ValueError):
                raise
            except Exception as exc:
                logger.warning("yt-dlp subprocess transcript fetch failed for %s: %s", video_id, exc)
                raise ConnectionError(f"TRANSIENT_NETWORK: Failed to fetch transcript for {video_id}: {exc}") from exc

        raw_entries = YouTubeAcquisitionService.parse_raw_srt(raw_srt)
        if not raw_entries:
            return []

        # Normalize and hash segments
        segments: list[dict[str, Any]] = []
        for idx, entry in enumerate(raw_entries):
            text = entry["text"]
            norm_text = normalize_transcript_text(text)
            c_hash = compute_segment_hash(video_id, idx, text)
            segments.append(
                {
                    "segment_index": idx,
                    "start_seconds": entry["start_seconds"],
                    "end_seconds": entry["end_seconds"],
                    "speaker": entry.get("speaker"),
                    "text": text,
                    "normalized_text": norm_text,
                    "content_hash": c_hash,
                }
            )

        return segments

    @staticmethod
    def persist_video_and_segments(
        session: Session,
        video_id: str,
        title: str,
        upload_date: str | None,
        channel_id: str,
        playlist_name: str,
        content_type: str,
        segments: list[dict[str, Any]],
    ) -> Video:
        """Persist Video record, dual-write legacy transcript strings, and insert TranscriptSegment rows."""
        now = utcnow()

        # 1. Construct legacy transcript strings
        ts_lines: list[str] = []
        no_ts_words: list[str] = []
        for seg in segments:
            ts_lines.append(f"[{seg['start_seconds']:.1f}s] {seg['text']}")
            no_ts_words.append(seg["text"])

        transcript_with_ts = "\n".join(ts_lines) if ts_lines else None
        transcript_no_ts = " ".join(no_ts_words) if no_ts_words else None

        # 2. Get or create Video
        video = session.get(Video, video_id)
        if not video:
            video = Video(
                video_id=video_id,
                title=title,
                upload_date=upload_date,
                transcript_with_ts=transcript_with_ts,
                transcript_no_ts=transcript_no_ts,
                last_modified=now,
            )
            session.add(video)
        else:
            video.title = title
            if upload_date:
                video.upload_date = upload_date
            video.transcript_with_ts = transcript_with_ts
            video.transcript_no_ts = transcript_no_ts
            video.last_modified = now

        # 3. Ensure folder association
        folder = session.scalar(
            select(VideoFolder).where(
                VideoFolder.original_playlist_id == channel_id,
                VideoFolder.video_id == video_id,
            )
        )
        if not folder:
            folder = VideoFolder(
                folder_name=playlist_name,
                original_playlist_id=channel_id,
                video_id=video_id,
                content_type=content_type,
                last_modified=now,
            )
            session.add(folder)
        else:
            folder.folder_name = playlist_name
            folder.content_type = content_type
            folder.last_modified = now

        # 4. Idempotently replace transcript_segments
        session.execute(delete(TranscriptSegment).where(TranscriptSegment.video_id == video_id))
        for seg in segments:
            seg_row = TranscriptSegment(
                video_id=video_id,
                segment_index=seg["segment_index"],
                start_seconds=seg["start_seconds"],
                end_seconds=seg["end_seconds"],
                speaker=seg.get("speaker"),
                text=seg["text"],
                normalized_text=seg["normalized_text"],
                content_hash=seg["content_hash"],
                created_at=now,
            )
            session.add(seg_row)

        session.commit()
        logger.info(
            "Persisted video %s ('%s') with %d transcript segments",
            video_id,
            title[:40],
            len(segments),
        )
        return video

    @staticmethod
    def _time_to_seconds(t_str: str) -> float:
        """Parse time strings formatted as HH:MM:SS.mmm, MM:SS.mmm, or SS.mmm to float seconds."""
        t_str = t_str.strip().split()[0].replace(",", ".")
        parts = t_str.split(":")
        if len(parts) == 3:
            return float(int(parts[0]) * 3600 + int(parts[1]) * 60) + float(parts[2])
        elif len(parts) == 2:
            return float(int(parts[0]) * 60) + float(parts[1])
        return float(parts[0])
