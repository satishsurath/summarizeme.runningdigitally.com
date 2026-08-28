"""Discovery stage handler for channel and playlist ingestion.

Scans channel or playlist URLs and generates downstream per-video transcript work items.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from services.youtube_acquisition import YouTubeAcquisitionService

logger = logging.getLogger(__name__)


def handle_discovery(payload: dict[str, Any], session: Session) -> dict[str, Any]:
    """Execute channel/playlist discovery and schedule downstream transcript work items."""
    channel_url = payload.get("channel_url")
    if not channel_url:
        raise ValueError("Payload missing required 'channel_url'")

    playlist_name_override = payload.get("playlist_name")
    channel_id, videos = YouTubeAcquisitionService.discover_channel_videos(channel_url)
    playlist_name = playlist_name_override or channel_id

    # Determine content type based on URL format and entries count
    url_types = ["youtube.com/watch", "youtu.be/", "youtube.com/shorts/", "youtube.com/live/"]
    is_single_video = any(k in channel_url for k in url_types) and len(videos) == 1
    content_type = "video" if is_single_video else "playlist"

    downstream_items: list[dict[str, Any]] = []
    for idx, video in enumerate(videos):
        video_id = video["video_id"]
        downstream_items.append(
            {
                "stage": "transcript",
                "resource_class": "youtube",
                "item_key": video_id,
                "priority": payload.get("priority", 0),
                "payload": {
                    "video_id": video_id,
                    "title": video.get("title", "Untitled"),
                    "upload_date": video.get("upload_date"),
                    "channel_id": channel_id,
                    "playlist_name": playlist_name,
                    "content_type": content_type,
                    "channel_url": channel_url,
                    "video_index": idx,
                    "total_videos": len(videos),
                },
            }
        )

    logger.info(
        "Discovery completed for %s: generated %d downstream transcript work items",
        channel_id,
        len(downstream_items),
    )

    return {
        "result": {
            "channel_id": channel_id,
            "playlist_name": playlist_name,
            "content_type": content_type,
            "total_videos": len(videos),
        },
        "downstream_items": downstream_items,
    }
