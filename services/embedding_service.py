"""Embedding service for batched Nomic embeddings and unified content chunk indexing.

Implements strict batch packing (<= 32 sequences, <= 8,192 tokens), task prefixing (search_document: / search_query:),
768-dimension validation, transcript sentence-aware chunking, structured summary parent section extraction,
and unified persistence to the content_chunks table.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app_config import (
    DEFAULT_EMBED_MODEL,
    EMBED_MAX_BATCH_TOKENS,
    EMBED_MAX_SEQUENCES,
    VLLM_EMBED_URL,
)
from db.models import ContentChunk, SummaryRun, TranscriptSegment, Video, utcnow
from services.contracts import StructuredSummaryV3

logger = logging.getLogger(__name__)


def estimate_token_count(text: str) -> int:
    """Estimate token count for whitespace/subword approximations (approx 4 chars per token)."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def compute_chunk_hash(video_id: str, chunk_type: str, sequence_index: int, text: str) -> str:
    """Compute deterministic SHA-256 hash for content chunk."""
    payload = f"{video_id}:{chunk_type}:{sequence_index}:{text.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def split_oversize_text(text: str, max_tokens: int = EMBED_MAX_BATCH_TOKENS) -> list[str]:
    """Deterministically split an oversize text into chunks each fitting within max_tokens."""
    if estimate_token_count(text) <= max_tokens:
        return [text]

    # Split by paragraphs or sentences
    chunks: list[str] = []
    lines = text.split("\n")
    current_chunk: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = estimate_token_count(line)
        if line_tokens > max_tokens:
            # Word-level fallback for huge lines
            words = line.split()
            w_chunk: list[str] = []
            w_tokens = 0
            for w in words:
                wt = estimate_token_count(w + " ")
                if w_tokens + wt > max_tokens and w_chunk:
                    chunks.append(" ".join(w_chunk))
                    w_chunk = [w]
                    w_tokens = wt
                else:
                    w_chunk.append(w)
                    w_tokens += wt
            if w_chunk:
                chunks.append(" ".join(w_chunk))
            continue

        if current_tokens + line_tokens > max_tokens and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_tokens = line_tokens
        else:
            current_chunk.append(line)
            current_tokens += line_tokens

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks or [text[: max_tokens * 4]]


def pack_embedding_batch(
    texts: list[str],
    max_batch_size: int = EMBED_MAX_SEQUENCES,
    max_tokens: int = EMBED_MAX_BATCH_TOKENS,
) -> list[list[str]]:
    """Pack texts into batches respecting max items and max aggregate token limits (Nemo hard ceiling)."""
    # First ensure no individual item exceeds max_tokens
    normalized_texts: list[str] = []
    for text in texts:
        if estimate_token_count(text) > max_tokens:
            normalized_texts.extend(split_oversize_text(text, max_tokens=max_tokens))
        else:
            normalized_texts.append(text)

    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for text in normalized_texts:
        t_count = estimate_token_count(text)
        if len(current_batch) >= max_batch_size or (current_tokens + t_count > max_tokens and current_batch):
            batches.append(current_batch)
            current_batch = [text]
            current_tokens = t_count
        else:
            current_batch.append(text)
            current_tokens += t_count

    if current_batch:
        batches.append(current_batch)

    return batches


class EmbeddingService:
    """Service for computing dense text embeddings and maintaining unified content chunks."""

    @staticmethod
    def embed_texts(
        texts: list[str],
        is_query: bool = False,
        model_name: str = DEFAULT_EMBED_MODEL,
        base_url: str = VLLM_EMBED_URL,
        timeout_seconds: float = 60.0,
    ) -> list[list[float]]:
        """Compute 768-dim embeddings in batches using Nomic task prefixes.

        Returns list of 768-dimensional float vectors matching the input texts.
        """
        if not texts:
            return []

        prefix = "search_query: " if is_query else "search_document: "
        prefixed_texts = [t if t.startswith(("search_query: ", "search_document: ")) else f"{prefix}{t}" for t in texts]

        batches = pack_embedding_batch(
            prefixed_texts,
            max_batch_size=EMBED_MAX_SEQUENCES,
            max_tokens=EMBED_MAX_BATCH_TOKENS,
        )
        all_embeddings: list[list[float]] = []

        url = f"{base_url.rstrip('/')}/v1/embeddings"
        api_key = os.getenv("VLLM_EMBED_API_KEY", os.getenv("VLLM_GEN_API_KEY", "local-noauth"))
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

        with httpx.Client(timeout=timeout_seconds) as client:
            for batch in batches:
                payload = {"model": model_name, "input": batch}
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    raise RuntimeError(f"Embedding endpoint returned {resp.status_code}: {resp.text[:400]}")

                data = resp.json()
                items = data.get("data", [])
                if len(items) != len(batch):
                    raise RuntimeError(f"Expected {len(batch)} embeddings, received {len(items)}")

                for item in items:
                    vec = item.get("embedding")
                    if not vec or len(vec) != 768:
                        actual_dim = len(vec) if vec else 0
                        raise ValueError(f"Invalid embedding vector: expected 768 dimensions, received {actual_dim}")
                    all_embeddings.append(vec)

        return all_embeddings

    @staticmethod
    def chunk_transcript_segments(
        segments: list[TranscriptSegment | dict[str, Any]],
        target_tokens: int = 400,
        overlap_segments: int = 1,
    ) -> list[dict[str, Any]]:
        """Chunk transcript segments into ~300-600 token coherent windows with timestamp bounds."""
        if not segments:
            return []

        # Normalize segment access (ORM model or dict)
        normalized_segs: list[dict[str, Any]] = []
        for s in segments:
            if isinstance(s, dict):
                normalized_segs.append(s)
            else:
                normalized_segs.append(
                    {
                        "start_seconds": s.start_seconds,
                        "end_seconds": s.end_seconds,
                        "speaker": s.speaker,
                        "text": s.text,
                    }
                )

        chunks: list[dict[str, Any]] = []
        i = 0
        seq_idx = 0

        while i < len(normalized_segs):
            current_texts: list[str] = []
            start_sec = normalized_segs[i]["start_seconds"]
            end_sec = normalized_segs[i]["end_seconds"]
            speaker = normalized_segs[i].get("speaker")
            accumulated_tokens = 0

            j = i
            while j < len(normalized_segs):
                seg_text = normalized_segs[j]["text"]
                seg_tokens = estimate_token_count(seg_text)

                current_texts.append(seg_text)
                end_sec = normalized_segs[j]["end_seconds"]
                accumulated_tokens += seg_tokens

                j += 1
                if accumulated_tokens >= target_tokens and j < len(normalized_segs):
                    break

            chunk_text = " ".join(current_texts)
            chunks.append(
                {
                    "chunk_type": "transcript",
                    "parent_id": None,
                    "sequence_index": seq_idx,
                    "start_seconds": start_sec,
                    "end_seconds": end_sec,
                    "speaker": speaker,
                    "text": chunk_text,
                    "token_count": accumulated_tokens,
                }
            )
            seq_idx += 1

            # Advance by step (accounting for overlap)
            step = max(1, (j - i) - overlap_segments)
            i += step

        return chunks

    @staticmethod
    def chunk_structured_summary(
        summary_input: StructuredSummaryV3 | dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract parent sections from StructuredSummaryV3 into typed content chunks.

        Strictly excludes internal reasoning traces.
        """
        if isinstance(summary_input, dict):
            summary = StructuredSummaryV3.model_validate(summary_input)
        else:
            summary = summary_input

        chunks: list[dict[str, Any]] = []
        seq_idx = 0

        # 1. Overview & Thesis
        overview_text = (
            f"Executive Overview: {summary.executive_overview.text}\n\nMain Thesis: {summary.main_thesis.statement}"
        )
        chunks.append(
            {
                "chunk_type": "summary_overview",
                "parent_id": "overview",
                "sequence_index": seq_idx,
                "start_seconds": None,
                "end_seconds": None,
                "speaker": None,
                "text": overview_text,
                "token_count": estimate_token_count(overview_text),
            }
        )
        seq_idx += 1

        # 2. Topics
        for topic in summary.topics:
            pts = "\n".join(f"- {pt.text}" for pt in topic.supporting_points)
            topic_text = f"Topic: {topic.title}\n{topic.summary}\nSupporting Points:\n{pts}"
            chunks.append(
                {
                    "chunk_type": "summary_topic",
                    "parent_id": topic.title[:64],
                    "sequence_index": seq_idx,
                    "start_seconds": None,
                    "end_seconds": None,
                    "speaker": None,
                    "text": topic_text,
                    "token_count": estimate_token_count(topic_text),
                }
            )
            seq_idx += 1

        # 3. Chapters
        for ch in summary.chapters:
            kps = "\n".join(f"- {kp}" for kp in ch.key_points)
            ch_hdr = f"Chapter [{ch.start_seconds:.1f}s - {ch.end_seconds:.1f}s]: {ch.title}"
            ch_text = f"{ch_hdr}\n{ch.summary}\nKey Points:\n{kps}"
            chunks.append(
                {
                    "chunk_type": "summary_chapter",
                    "parent_id": ch.title[:64],
                    "sequence_index": seq_idx,
                    "start_seconds": ch.start_seconds,
                    "end_seconds": ch.end_seconds,
                    "speaker": None,
                    "text": ch_text,
                    "token_count": estimate_token_count(ch_text),
                }
            )
            seq_idx += 1

        # 4. Details, Decisions, Recommendations, Action Items
        detail_lines: list[str] = []
        if summary.decisions:
            detail_lines.append("Decisions:")
            for d in summary.decisions:
                detail_lines.append(f"- {d.decision}: {d.rationale}")

        if summary.recommendations:
            detail_lines.append("\nRecommendations:")
            for r in summary.recommendations:
                detail_lines.append(f"- {r.recommendation}")

        if summary.action_items:
            detail_lines.append("\nAction Items:")
            for a in summary.action_items:
                detail_lines.append(f"- {a.action}")

        if summary.glossary:
            detail_lines.append("\nGlossary:")
            for g in summary.glossary:
                detail_lines.append(f"- {g.term}: {g.definition}")

        if detail_lines:
            detail_text = "\n".join(detail_lines).strip()
            chunks.append(
                {
                    "chunk_type": "summary_detail",
                    "parent_id": "details_and_decisions",
                    "sequence_index": seq_idx,
                    "start_seconds": None,
                    "end_seconds": None,
                    "speaker": None,
                    "text": detail_text,
                    "token_count": estimate_token_count(detail_text),
                }
            )
            seq_idx += 1

        return chunks

    @staticmethod
    def embed_and_index_transcript(
        session: Session,
        video_id: str,
        model_name: str = DEFAULT_EMBED_MODEL,
        base_url: str = VLLM_EMBED_URL,
    ) -> int:
        """Fetch transcript segments, chunk, compute embeddings, and insert ContentChunk records."""
        segments = session.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.video_id == video_id)
            .order_by(TranscriptSegment.segment_index.asc())
        ).all()

        if not segments:
            # Fallback to video.transcript_no_ts if segments are absent
            video = session.get(Video, video_id)
            if not video or not video.transcript_no_ts:
                logger.warning("No transcript content to embed for video %s", video_id)
                return 0

            # Synthesize segment windows covering the whole transcript without silent truncation
            full_text = video.transcript_no_ts.strip()
            text_chunks = split_oversize_text(full_text, max_tokens=400)
            raw_chunks = [
                {
                    "chunk_type": "transcript",
                    "parent_id": None,
                    "sequence_index": idx,
                    "start_seconds": 0.0,
                    "end_seconds": 0.0,
                    "speaker": None,
                    "text": chunk_t,
                    "token_count": estimate_token_count(chunk_t),
                }
                for idx, chunk_t in enumerate(text_chunks)
            ]
        else:
            raw_chunks = EmbeddingService.chunk_transcript_segments(list(segments))

        if not raw_chunks:
            return 0

        # Compute embeddings
        texts = [c["text"] for c in raw_chunks]
        embeddings = EmbeddingService.embed_texts(texts, is_query=False, model_name=model_name, base_url=base_url)

        now = utcnow()
        # Idempotently replace existing transcript chunks
        session.execute(
            delete(ContentChunk).where(
                ContentChunk.video_id == video_id,
                ContentChunk.chunk_type == "transcript",
            )
        )

        for chunk_data, emb in zip(raw_chunks, embeddings, strict=False):
            c_hash = compute_chunk_hash(video_id, "transcript", chunk_data["sequence_index"], chunk_data["text"])
            chunk_row = ContentChunk(
                video_id=video_id,
                chunk_type="transcript",
                parent_id=chunk_data.get("parent_id"),
                sequence_index=chunk_data["sequence_index"],
                start_seconds=chunk_data.get("start_seconds"),
                end_seconds=chunk_data.get("end_seconds"),
                speaker=chunk_data.get("speaker"),
                text=chunk_data["text"],
                token_count=chunk_data["token_count"],
                content_hash=c_hash,
                embedding=emb,
                created_at=now,
            )
            session.add(chunk_row)

        session.commit()
        logger.info("Embedded and indexed %d transcript chunks for video %s", len(raw_chunks), video_id)
        return len(raw_chunks)

    @staticmethod
    def embed_and_index_summary(
        session: Session,
        video_id: str,
        model_name: str = DEFAULT_EMBED_MODEL,
        base_url: str = VLLM_EMBED_URL,
    ) -> int:
        """Fetch latest structured summary run, chunk sections, compute embeddings, and insert ContentChunk records."""
        summary_run = session.scalar(
            select(SummaryRun).where(SummaryRun.video_id == video_id).order_by(SummaryRun.created_at.desc())
        )

        if not summary_run or not summary_run.structured_summary:
            logger.warning("No structured summary found to embed for video %s", video_id)
            return 0

        raw_chunks = EmbeddingService.chunk_structured_summary(summary_run.structured_summary)
        if not raw_chunks:
            return 0

        texts = [c["text"] for c in raw_chunks]
        embeddings = EmbeddingService.embed_texts(texts, is_query=False, model_name=model_name, base_url=base_url)

        now = utcnow()
        # Idempotently replace existing summary chunks for this video
        session.execute(
            delete(ContentChunk).where(
                ContentChunk.video_id == video_id,
                ContentChunk.chunk_type.startswith("summary_"),
            )
        )

        for chunk_data, emb in zip(raw_chunks, embeddings, strict=False):
            c_hash = compute_chunk_hash(
                video_id, chunk_data["chunk_type"], chunk_data["sequence_index"], chunk_data["text"]
            )
            chunk_row = ContentChunk(
                video_id=video_id,
                chunk_type=chunk_data["chunk_type"],
                parent_id=chunk_data.get("parent_id"),
                sequence_index=chunk_data["sequence_index"],
                start_seconds=chunk_data.get("start_seconds"),
                end_seconds=chunk_data.get("end_seconds"),
                speaker=chunk_data.get("speaker"),
                text=chunk_data["text"],
                token_count=chunk_data["token_count"],
                content_hash=c_hash,
                embedding=emb,
                created_at=now,
            )
            session.add(chunk_row)

        session.commit()
        logger.info("Embedded and indexed %d summary chunks for video %s", len(raw_chunks), video_id)
        return len(raw_chunks)
