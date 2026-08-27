"""Hybrid retrieval service with pgvector similarity and full-text search RRF fusion.

Combines 768-dim dense embedding vector search with lexical matching across content_chunks,
applying Reciprocal Rank Fusion (RRF), score thresholds, and parent context expansion.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from sqlalchemy import select, text
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
        max_tokens_budget: int = 8000,
        max_chunks_per_video: int = 4,
        model_name: str = DEFAULT_EMBED_MODEL,
        base_url: str = VLLM_EMBED_URL,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant context chunks for a query using hybrid RRF scoring and token packing."""
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

        # 2. Compute query embedding (without holding open long DB transactions)
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

        bind = session.get_bind()
        dialect_name = bind.dialect.name if bind else "sqlite"

        rrf_k = 60
        scores: dict[int, float] = {}
        chunk_map: dict[int, Any] = {}

        # 3. Check for native PostgreSQL execution
        if dialect_name == "postgresql" and query_vec:
            try:
                # Vector Search via pgvector HNSW / cosine distance (<=>)
                vec_sql = """
                    SELECT id, video_id, chunk_type, parent_id, sequence_index, start_seconds, end_seconds,
                           speaker, text, token_count, (embedding_vec <=> :query_vec::vector) as distance
                    FROM content_chunks
                    WHERE (:has_scope = false OR video_id = ANY(:target_ids))
                      AND embedding_vec IS NOT NULL
                    ORDER BY embedding_vec <=> :query_vec::vector
                    LIMIT 50
                """
                vec_params = {
                    "query_vec": str(query_vec),
                    "has_scope": bool(target_video_ids),
                    "target_ids": target_video_ids,
                }
                vec_rows = session.execute(text(vec_sql), vec_params).fetchall()
                for rank, row in enumerate(vec_rows):
                    cid = row.id
                    chunk_map[cid] = row
                    scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))

                # Full-Text Search via tsvector / plainto_tsquery
                fts_sql = """
                    SELECT id, video_id, chunk_type, parent_id, sequence_index, start_seconds, end_seconds,
                           speaker, text, token_count,
                           ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', :query)) as rank
                    FROM content_chunks
                    WHERE (:has_scope = false OR video_id = ANY(:target_ids))
                      AND to_tsvector('english', text) @@ plainto_tsquery('english', :query)
                    ORDER BY rank DESC
                    LIMIT 50
                """
                fts_params = {
                    "query": query,
                    "has_scope": bool(target_video_ids),
                    "target_ids": target_video_ids,
                }
                fts_rows = session.execute(text(fts_sql), fts_params).fetchall()
                for rank, row in enumerate(fts_rows):
                    cid = row.id
                    chunk_map[cid] = row
                    scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))

            except Exception as pg_exc:
                logger.warning("PostgreSQL native hybrid search failed: %s. Falling back to in-memory ranking.", pg_exc)
                scores.clear()
                chunk_map.clear()

        # 4. In-memory / SQLite fallback
        if not scores:
            _MAX_CANDIDATES = 2000
            stmt = select(ContentChunk)
            if target_video_ids:
                stmt = stmt.where(ContentChunk.video_id.in_(target_video_ids))
            stmt = stmt.limit(_MAX_CANDIDATES)

            candidates = session.scalars(stmt).all()
            if not candidates:
                logger.info("No content chunks found in scope (%s=%s)", scope_type, scope_id)
                return []

            vector_ranked: list[tuple[float, ContentChunk]] = []
            lexical_ranked: list[tuple[float, ContentChunk]] = []
            query_words = set(query.lower().split())

            for chunk in candidates:
                if query_vec and chunk.embedding:
                    sim = cosine_similarity(query_vec, chunk.embedding)
                    vector_ranked.append((sim, chunk))

                chunk_words = set(chunk.text.lower().split())
                overlap = len(query_words.intersection(chunk_words))
                if overlap > 0:
                    lexical_ranked.append((float(overlap), chunk))

            vector_ranked.sort(key=lambda x: x[0], reverse=True)
            lexical_ranked.sort(key=lambda x: x[0], reverse=True)

            for rank, (_score, chunk) in enumerate(vector_ranked[:50]):
                chunk_map[chunk.id] = chunk
                scores[chunk.id] = scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank + 1))

            for rank, (_score, chunk) in enumerate(lexical_ranked[:50]):
                chunk_map[chunk.id] = chunk
                scores[chunk.id] = scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank + 1))

        # 5. Apply diversity limits and token budget packing
        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
        results: list[dict[str, Any]] = []
        video_chunk_counts: dict[str, int] = {}
        accumulated_tokens = 0

        for cid in sorted_ids:
            if len(results) >= top_k:
                break

            c = chunk_map[cid]
            vid = c.video_id
            if video_chunk_counts.get(vid, 0) >= max_chunks_per_video:
                continue

            t_count = getattr(c, "token_count", 0) or max(1, len(c.text) // 4)
            if accumulated_tokens + t_count > max_tokens_budget and results:
                break

            video_chunk_counts[vid] = video_chunk_counts.get(vid, 0) + 1
            accumulated_tokens += t_count

            # Parent context expansion if parent_id exists
            parent_context: str | None = None
            parent_id = getattr(c, "parent_id", None)
            if parent_id and hasattr(c, "id"):
                # Query parent chunk if needed
                parent_row = session.scalar(
                    select(ContentChunk.text)
                    .where(
                        ContentChunk.video_id == vid,
                        ContentChunk.chunk_type == "summary_topic",
                        ContentChunk.sequence_index == 0,
                    )
                    .limit(1)
                )
                parent_context = parent_row

            results.append(
                {
                    "chunk_id": c.id,
                    "video_id": vid,
                    "chunk_type": getattr(c, "chunk_type", "transcript"),
                    "parent_id": parent_id,
                    "parent_context": parent_context,
                    "start_seconds": getattr(c, "start_seconds", 0.0),
                    "end_seconds": getattr(c, "end_seconds", 0.0),
                    "speaker": getattr(c, "speaker", None),
                    "text": c.text,
                    "token_count": t_count,
                    "score": round(scores[cid], 5),
                }
            )

        logger.info(
            "Hybrid retrieval for query '%s' (%s=%s): returned %d chunks (%d tokens)",
            query[:40],
            scope_type,
            scope_id,
            len(results),
            accumulated_tokens,
        )
        return results
