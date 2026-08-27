"""Finalize worker stage handler.

Performs pipeline completion checks, logs metrics, and marks the video processing pipeline complete.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ContentChunk, SummaryRun, Video

logger = logging.getLogger(__name__)


def handle_finalize(payload: dict[str, Any], session: Session) -> dict[str, Any]:
    """Execute pipeline completion checks and finalize video status."""
    video_id = payload.get("video_id")
    if not video_id:
        raise ValueError("Payload missing required 'video_id'")

    video = session.get(Video, video_id)
    if not video:
        raise ValueError(f"Video {video_id} not found during finalize")

    chunk_count = len(session.scalars(select(ContentChunk).where(ContentChunk.video_id == video_id)).all())
    summary_runs = len(session.scalars(select(SummaryRun).where(SummaryRun.video_id == video_id)).all())

    logger.info(
        "Pipeline finalized for video %s ('%s'): %d total indexed chunks, %d summary runs",
        video_id,
        video.title or "Untitled",
        chunk_count,
        summary_runs,
    )

    return {
        "result": {
            "video_id": video_id,
            "status": "ready",
            "total_chunks": chunk_count,
            "summary_runs": summary_runs,
        },
        "downstream_items": [],
    }
