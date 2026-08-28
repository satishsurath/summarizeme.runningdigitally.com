"""Embedding worker stage handlers for transcript chunks and structured summaries.

Acquires embedding capacity leases, invokes EmbeddingService, and registers content chunks into pgvector.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app_config import DEFAULT_EMBED_MODEL
from services.embedding_service import EmbeddingService
from services.resource_admission import ResourceAdmission

logger = logging.getLogger(__name__)


def handle_embed_transcript(payload: dict[str, Any], session: Session) -> dict[str, Any]:
    """Execute transcript chunking and batched vector embedding."""
    video_id = payload.get("video_id")
    if not video_id:
        raise ValueError("Payload missing required 'video_id'")

    model_name = payload.get("model_name", DEFAULT_EMBED_MODEL)
    owner = f"worker-embed-ts-{video_id}"

    # 1. Acquire embedding capacity lease (max 4 concurrent)
    lease_id = ResourceAdmission.acquire_lease(
        session=session,
        resource_class="embedding",
        owner=owner,
        lease_seconds=120,
    )
    if not lease_id:
        raise RuntimeError("Embedding capacity full (4 in-flight); yielding for retry")

    try:
        count = EmbeddingService.embed_and_index_transcript(
            session=session,
            video_id=video_id,
            model_name=model_name,
        )
    finally:
        ResourceAdmission.release_lease(session=session, lease_id=lease_id, owner=owner)

    logger.info("embed_transcript completed for %s: indexed %d chunks", video_id, count)
    return {
        "result": {"video_id": video_id, "chunks_indexed": count, "stage": "embed_transcript"},
        "downstream_items": [],
    }


def handle_embed_summary(payload: dict[str, Any], session: Session) -> dict[str, Any]:
    """Execute structured summary section chunking, embedding, and schedule pipeline finalization."""
    video_id = payload.get("video_id")
    if not video_id:
        raise ValueError("Payload missing required 'video_id'")

    model_name = payload.get("model_name", DEFAULT_EMBED_MODEL)
    owner = f"worker-embed-sum-{video_id}"

    # 1. Acquire embedding capacity lease
    lease_id = ResourceAdmission.acquire_lease(
        session=session,
        resource_class="embedding",
        owner=owner,
        lease_seconds=120,
    )
    if not lease_id:
        raise RuntimeError("Embedding capacity full (4 in-flight); yielding for retry")

    try:
        count = EmbeddingService.embed_and_index_summary(
            session=session,
            video_id=video_id,
            model_name=model_name,
        )
    finally:
        ResourceAdmission.release_lease(session=session, lease_id=lease_id, owner=owner)

    # 2. Schedule finalization stage
    downstream_items = [
        {
            "stage": "finalize",
            "resource_class": "control",
            "item_key": video_id,
            "priority": payload.get("priority", 0),
            "payload": {
                "video_id": video_id,
                "summary_run_id": payload.get("summary_run_id"),
            },
        }
    ]

    logger.info("embed_summary completed for %s: indexed %d summary chunks", video_id, count)
    return {
        "result": {"video_id": video_id, "chunks_indexed": count, "stage": "embed_summary"},
        "downstream_items": downstream_items,
    }
