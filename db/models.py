from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


def utcnow() -> datetime.datetime:
    """Return current UTC datetime with timezone."""
    return datetime.datetime.now(datetime.UTC)


def ensure_utc(dt: datetime.datetime | None) -> datetime.datetime | None:
    """Normalize datetime to timezone-aware UTC datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.UTC)
    return dt.astimezone(datetime.UTC)


class Video(Base):
    __tablename__ = "videos"
    video_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(512))
    upload_date: Mapped[str | None] = mapped_column(String(32))
    transcript_with_ts: Mapped[str | None] = mapped_column(Text)
    transcript_no_ts: Mapped[str | None] = mapped_column(Text)
    tokens_with_ts: Mapped[int] = mapped_column(Integer, default=0)
    tokens_no_ts: Mapped[int] = mapped_column(Integer, default=0)
    last_modified: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    folders: Mapped[list[VideoFolder]] = relationship("VideoFolder", back_populates="video")
    summaries_v2: Mapped[list[SummariesV2]] = relationship("SummariesV2", back_populates="video")
    segments: Mapped[list[TranscriptSegment]] = relationship(
        "TranscriptSegment", back_populates="video", cascade="all, delete-orphan", lazy="selectin"
    )
    summary_runs: Mapped[list[SummaryRun]] = relationship(
        "SummaryRun", back_populates="video", cascade="all, delete-orphan", lazy="selectin"
    )
    chunks: Mapped[list[ContentChunk]] = relationship(
        "ContentChunk", back_populates="video", cascade="all, delete-orphan", lazy="selectin"
    )


class VideoFolder(Base):
    __tablename__ = "video_folders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folder_name: Mapped[str | None] = mapped_column(String(255))
    original_playlist_id: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(20), default="playlist", server_default="playlist")
    video_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("videos.video_id"))
    last_modified: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video | None] = relationship("Video", back_populates="folders")


class SummariesV2(Base):
    __tablename__ = "summaries_v2"
    __table_args__ = (UniqueConstraint("video_id", "model_name", name="uq_summaries_v2_video_model"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("videos.video_id"))
    video_title: Mapped[str | None] = mapped_column(String(512))
    model_name: Mapped[str | None] = mapped_column(String(50))
    date_generated: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    concise_summary: Mapped[str | None] = mapped_column(Text)
    key_topics: Mapped[str | None] = mapped_column(Text)
    important_takeaways: Mapped[str | None] = mapped_column(Text)
    comprehensive_notes: Mapped[str | None] = mapped_column(Text)

    video: Mapped[Video | None] = relationship("Video", back_populates="summaries_v2")


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    message: Mapped[str | None] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="reader")


# ---------------------------------------------------------------------------
# Processing Pipeline Models (Phase 1)
# ---------------------------------------------------------------------------


class Job(Base):
    """Durable top-level ingest, summarization, or refresh request."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)  # channel_ingest, refresh, summarize, reindex
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # pending, running, completed, partial, failed, cancelled
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    work_items: Mapped[list[WorkItem]] = relationship(
        "WorkItem", back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkItem(Base):
    """Independently claimable and retryable work item in the processing pipeline."""

    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint("job_id", "stage", "item_key", name="uq_work_items_job_stage_key"),
        Index("ix_work_items_candidate", "status", "resource_class", "available_at", "priority"),
        Index("ix_work_items_job_status", "job_id", "status"),
        Index("ix_work_items_lease_expires", "lease_expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # discover, transcript, summarize, embed_transcript, embed_summary, finalize
    resource_class: Mapped[str] = mapped_column(String(64), nullable=False)  # control, youtube, generation, embedding
    item_key: Mapped[str] = mapped_column(String(255), nullable=False)  # video_id or playlist URL
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # pending, leased, completed, retry, failed, cancelled
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship("Job", back_populates="work_items")


class ResourceLimit(Base):
    """Configured concurrency ceiling per resource class."""

    __tablename__ = "resource_limits"

    resource_class: Mapped[str] = mapped_column(String(64), primary_key=True)
    max_in_flight: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ResourceLease(Base):
    """Expiring cross-process capacity lease for generation, embedding, or YouTube execution."""

    __tablename__ = "resource_leases"
    __table_args__ = (Index("ix_resource_leases_class_expires", "resource_class", "expires_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resource_class: Mapped[str] = mapped_column(
        String(64), ForeignKey("resource_limits.resource_class", ondelete="CASCADE"), nullable=False
    )
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExternalRateLimit(Base):
    """Cross-process start rate limiter and circuit-breaker state (e.g. YouTube pacing)."""

    __tablename__ = "external_rate_limits"

    provider_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_allowed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    backoff_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TranscriptSegment(Base):
    """Normalized timestamped transcript segment with speaker and content hash."""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint("video_id", "segment_index", name="uq_transcript_segments_video_idx"),
        Index("ix_transcript_segments_video_start", "video_id", "start_seconds"),
        Index("ix_transcript_segments_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video] = relationship("Video", back_populates="segments")


class SummaryRun(Base):
    """Execution run of 9-section structured summary generation with thinking and validation status."""

    __tablename__ = "summary_runs"
    __table_args__ = (
        Index("ix_summary_runs_video_id", "video_id"),
        Index("ix_summary_runs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String(50), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    reasoning_effort: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_profile_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    structured_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reasoning_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    validation_errors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video] = relationship("Video", back_populates="summary_runs")


class ContentChunk(Base):
    """Unified hybrid content chunk with metadata, timestamps, and 768-dim embedding vector."""

    __tablename__ = "content_chunks"
    __table_args__ = (
        UniqueConstraint("video_id", "chunk_type", "sequence_index", name="uq_content_chunks_video_type_seq"),
        Index("ix_content_chunks_video_type", "video_id", "chunk_type"),
        Index("ix_content_chunks_start_seconds", "video_id", "start_seconds"),
        Index("ix_content_chunks_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(50), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaker: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video] = relationship("Video", back_populates="chunks")


class Conversation(Base):
    """Multi-turn conversation session scoped to channel, video, or global context."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_id", "user_id"),
        Index("ix_conversations_scope", "scope_type", "scope_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)  # channel, video, global
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    reasoning_effort: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    messages: Mapped[list[ConversationMessage]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.sequence_index",
        lazy="selectin",
    )


class ConversationMessage(Base):
    """Individual message in a conversation thread with reasoning trace and cited sources."""

    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence_index", name="uq_conversation_messages_conv_seq"),
        Index("ix_conversation_messages_conv_id", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")


class AIEndpoint(Base):
    """Hardware endpoint configuration for vLLM / SGLang generation or embedding services."""

    __tablename__ = "ai_endpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    endpoint_type: Mapped[str] = mapped_column(String(32), nullable=False)  # generation, embedding, rerank
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    models: Mapped[list[AIModel]] = relationship("AIModel", back_populates="endpoint", cascade="all, delete-orphan")


class AIModel(Base):
    """Registered AI model available on a specific serving endpoint."""

    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint("endpoint_id", "model_id", name="uq_ai_models_endpoint_model"),
        Index("ix_ai_models_endpoint_id", "endpoint_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    endpoint_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_endpoints.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, nullable=False, default=32768)
    qualification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="passed")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    endpoint: Mapped[AIEndpoint] = relationship("AIEndpoint", back_populates="models")


class AIRuntimePool(Base):
    """Runtime concurrency and interactive lease allocation pool."""

    __tablename__ = "ai_runtime_pools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    max_in_flight: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    interactive_reserve: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserAIPreference(Base):
    """Per-user AI model selection and reasoning effort preferences."""

    __tablename__ = "user_ai_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    preferred_gen_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    preferred_reasoning_effort: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
