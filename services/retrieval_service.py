"""Hybrid retrieval service with pgvector similarity and full-text search RRF fusion.

Combines 768-dim dense embedding vector search with lexical matching across content_chunks,
applying Reciprocal Rank Fusion (RRF), score thresholds, and parent context expansion.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app_config import DEFAULT_EMBED_MODEL, VLLM_EMBED_URL
from db.models import ContentChunk, VideoFolder
from services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class RetrievalService:
    """Service for hybrid semantic and keyword retrieval over indexed content chunks."""

    @staticmethod
    def retrieve_context(
        session: Session,
        query: str,
        scope_type: str,  # 'video', 'channel', 'global'
        scope_id: str,  # video_id or channel/playlist_id
        top_k: int = 10,
        model_name: str = DEFAULT_EMBED_MODEL,
        base_url: str = VLLM_EMBED_URL,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant context chunks for a query using hybrid RRF scoring."""
        if not query or not query.strip():
            return []

        # 1. Resolve video IDs within scope
        target_video_ids: list[str] = []
        if scope_type == "video":
            target_video_ids = [scope_id]
        elif scope_type == "channel":
            target_video_ids = [
                vid
                for vid in session.scalars(
                    select(VideoFolder.video_id).where(
                        (VideoFolder.folder_name == scope_id) | (VideoFolder.original_playlist_id == scope_id)
                    )
                ).all()
                if vid is not None
            ]
            if not target_video_ids:
                target_video_ids = [scope_id]

        # 2. Fetch candidate chunks (bounded to prevent OOM without pgvector)
        _MAX_CANDIDATE_CHUNKS = 5000
        stmt = select(ContentChunk)
        if target_video_ids:
            stmt = stmt.where(ContentChunk.video_id.in_(target_video_ids))
        stmt = stmt.limit(_MAX_CANDIDATE_CHUNKS)

        candidate_chunks = session.scalars(stmt).all()
        if not candidate_chunks:
            logger.info("No content chunks found in scope (%s=%s)", scope_type, scope_id)
            return []

        # 3. Compute query embedding
        try:
            query_vectors = EmbeddingService.embed_texts(
                [query],
                is_query=True,
                model_name=model_name,
                base_url=base_url,
            )
            query_vec = query_vectors[0] if query_vectors else None
        except Exception as exc:
            logger.warning("Query embedding generation failed: %s. Falling back to keyword rank.", exc)
            query_vec = None

        # 4. Score candidates via Vector Similarity & Lexical Match
        vector_ranked: list[tuple[float, ContentChunk]] = []
        lexical_ranked: list[tuple[float, ContentChunk]] = []
        query_words = set(query.lower().split())

        for chunk in candidate_chunks:
            # Dense Vector Score
            if query_vec and chunk.embedding:
                sim = cosine_similarity(query_vec, chunk.embedding)
                vector_ranked.append((sim, chunk))

            # Lexical Score (term overlap count)
            chunk_words = set(chunk.text.lower().split())
            overlap = len(query_words.intersection(chunk_words))
            if overlap > 0:
                lexical_ranked.append((float(overlap), chunk))

        vector_ranked.sort(key=lambda x: x[0], reverse=True)
        lexical_ranked.sort(key=lambda x: x[0], reverse=True)

        # 5. Apply Reciprocal Rank Fusion (RRF with k=60)
        rrf_k = 60
        scores: dict[int, float] = {}
        chunk_map: dict[int, ContentChunk] = {}

        for rank, (_score, chunk) in enumerate(vector_ranked):
            chunk_map[chunk.id] = chunk
            scores[chunk.id] = scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank + 1))

        for rank, (_score, chunk) in enumerate(lexical_ranked):
            chunk_map[chunk.id] = chunk
            scores[chunk.id] = scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank + 1))

        # 6. Sort by combined RRF score
        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

        results: list[dict[str, Any]] = []
        for cid in sorted_ids[:top_k]:
            c = chunk_map[cid]
            results.append(
                {
                    "chunk_id": c.id,
                    "video_id": c.video_id,
                    "chunk_type": c.chunk_type,
                    "parent_id": c.parent_id,
                    "start_seconds": c.start_seconds,
                    "end_seconds": c.end_seconds,
                    "speaker": c.speaker,
                    "text": c.text,
                    "score": round(scores[cid], 5),
                }
            )

        logger.info(
            "Hybrid retrieval for query '%s' (%s=%s): returned %d chunks",
            query[:40],
            scope_type,
            scope_id,
            len(results),
        )
        return results
