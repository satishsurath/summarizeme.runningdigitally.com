"""Transcript acquisition stage handler with rate pacing and circuit breaking.

Enforces YouTube start rate interval (12s + 3s jitter), fetches timestamped transcripts,
persists segments, and schedules downstream summarize and embed_transcript stages.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app_config import YT_MIN_START_INTERVAL_SECONDS, YT_START_JITTER_SECONDS
from db.models import ensure_utc, utcnow
from services.resource_admission import ResourceAdmission
from services.youtube_acquisition import YouTubeAcquisitionService

logger = logging.getLogger(__name__)


def handle_transcript(payload: dict[str, Any], session: Session) -> dict[str, Any]:
    """Execute rate-paced transcript retrieval, segment persistence, and downstream staging."""
    video_id = payload.get("video_id")
    if not video_id:
        raise ValueError("Payload missing required 'video_id'")

    title = payload.get("title", "Untitled")
    upload_date = payload.get("upload_date")
    channel_id = payload.get("channel_id", "unknown_channel")
    playlist_name = payload.get("playlist_name", channel_id)
    content_type = payload.get("content_type", "video")

    # 1. Rate pacing: Reserve start slot and sleep if slot is in future
    scheduled_start = ResourceAdmission.reserve_external_start(
        session=session,
        provider_key="youtube",
        min_interval_seconds=YT_MIN_START_INTERVAL_SECONDS,
        jitter_seconds=YT_START_JITTER_SECONDS,
    )
    now = utcnow()
    scheduled_utc = ensure_utc(scheduled_start)
    if scheduled_utc and scheduled_utc > now:
        sleep_sec = (scheduled_utc - now).total_seconds()
        logger.info("Rate-pacing YouTube request for %s: sleeping for %.2fs", video_id, sleep_sec)
        time.sleep(sleep_sec)

    # 2. Fetch transcript segments
    try:
        segments = YouTubeAcquisitionService.fetch_video_transcript(video_id)
    except Exception as exc:
        err_msg = str(exc)
        if "429" in err_msg or "Too Many Requests" in err_msg or "rate limit" in err_msg.lower():
            logger.warning("YouTube 429 throttling detected for video %s. Tripping circuit breaker.", video_id)
            ResourceAdmission.open_circuit(session, provider_key="youtube", backoff_seconds=60, error_code="HTTP_429")
        raise

    if not segments:
        logger.warning("No transcript segments returned for video %s ('%s').", video_id, title)
        # Note: If captions are absent, we still persist empty video record so it's recorded
        YouTubeAcquisitionService.persist_video_and_segments(
            session=session,
            video_id=video_id,
            title=title,
            upload_date=upload_date,
            channel_id=channel_id,
            playlist_name=playlist_name,
            content_type=content_type,
            segments=[],
        )
        return {
            "result": {
                "video_id": video_id,
                "segments_count": 0,
                "status": "no_captions_available",
            },
            "downstream_items": [],
        }

    # 3. Persist Video and TranscriptSegment rows
    YouTubeAcquisitionService.persist_video_and_segments(
        session=session,
        video_id=video_id,
        title=title,
        upload_date=upload_date,
        channel_id=channel_id,
        playlist_name=playlist_name,
        content_type=content_type,
        segments=segments,
    )

    # 4. Record successful acquisition (resets circuit breaker)
    ResourceAdmission.record_external_success(session, provider_key="youtube")

    # 5. Enqueue downstream summarize (generation) and embed_transcript (embedding)
    downstream_items = [
        {
            "stage": "summarize",
            "resource_class": "generation",
            "item_key": video_id,
            "priority": payload.get("priority", 0),
            "payload": {
                "video_id": video_id,
                "title": title,
                "upload_date": upload_date,
                "channel_id": channel_id,
                "playlist_name": playlist_name,
                "content_type": content_type,
                "segments_count": len(segments),
            },
        },
        {
            "stage": "embed_transcript",
            "resource_class": "embedding",
            "item_key": video_id,
            "priority": payload.get("priority", 0),
            "payload": {
                "video_id": video_id,
                "title": title,
                "channel_id": channel_id,
                "segments_count": len(segments),
            },
        },
    ]

    logger.info(
        "Transcript stage completed for %s: %d segments stored, scheduled summarize & embed_transcript",
        video_id,
        len(segments),
    )

    return {
        "result": {
            "video_id": video_id,
            "segments_count": len(segments),
            "status": "persisted",
        },
        "downstream_items": downstream_items,
    }
