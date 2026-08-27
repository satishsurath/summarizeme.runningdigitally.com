"""Canonical schemas, Pydantic contracts, streaming event envelopes, and validation helpers.

Authoritative for the 9-section summary contract, evidence integrity rules, and typed SSE protocol.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaimClassification(StrEnum):
    """Classification of statements in summary artifacts."""

    FACT = "fact"
    SPEAKER_CLAIM = "speaker_claim"
    OPINION = "opinion"
    ESTIMATE = "estimate"
    RECOMMENDATION = "recommendation"
    INFERENCE = "inference"


class ReasoningEffort(StrEnum):
    """User-selectable reasoning levels."""

    DISABLED = "disabled"
    LOW = "low"
    MEDIUM = "medium"
    XHIGH = "xhigh"


class EvidenceReference(BaseModel):
    """Stable timestamped evidence reference."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Evidence identifier, e.g. E1, E2")
    start_seconds: float = Field(ge=0, description="Start timestamp in video seconds")
    end_seconds: float = Field(ge=0, description="End timestamp in video seconds")
    speaker: str | None = Field(default=None, description="Speaker name if identified")
    excerpt: str = Field(description="Verbatim excerpt from normalized transcript")
    youtube_url: str | None = Field(default=None, description="Derived playback link with timestamp")

    @field_validator("end_seconds")
    @classmethod
    def validate_timestamp_order(cls, v: float, info: Any) -> float:
        start = info.data.get("start_seconds")
        if start is not None and v < start:
            raise ValueError(f"end_seconds ({v}) must be greater than or equal to start_seconds ({start})")
        return v


class ExecutiveOverview(BaseModel):
    """Section 1: Executive overview."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="Comprehensive high-level summary of the entire video")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class MainThesis(BaseModel):
    """Section 2: Main thesis."""

    model_config = ConfigDict(extra="forbid")
    statement: str = Field(description="Core thesis or primary conclusion")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class SupportingPoint(BaseModel):
    """Supporting point within a topic."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="Supporting point description")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class Topic(BaseModel):
    """Section 3: Topics and supporting points."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(description="Topic title")
    summary: str = Field(description="Topic summary")
    supporting_points: list[SupportingPoint] = Field(default_factory=list, description="Supporting points")


class Chapter(BaseModel):
    """Section 4: Chapter or timeline breakdown."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(description="Chapter title")
    start_seconds: float = Field(ge=0, description="Chapter start time in seconds")
    end_seconds: float = Field(ge=0, description="Chapter end time in seconds")
    summary: str = Field(description="Chapter summary")
    key_points: list[str] = Field(default_factory=list, description="Key points in chapter")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")

    @field_validator("end_seconds")
    @classmethod
    def validate_chapter_order(cls, v: float, info: Any) -> float:
        start = info.data.get("start_seconds")
        if start is not None and v < start:
            raise ValueError(f"Chapter end_seconds ({v}) must be >= start_seconds ({start})")
        return v


class ImportantDetail(BaseModel):
    """Section 5: Important facts and technical details."""

    model_config = ConfigDict(extra="forbid")
    statement: str = Field(description="Specific detail or technical fact")
    classification: ClaimClassification = Field(
        default=ClaimClassification.FACT, description="Classification of the statement"
    )
    speaker: str | None = Field(default=None, description="Speaker who made the statement")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class Decision(BaseModel):
    """Section 6a: Decisions made in video."""

    model_config = ConfigDict(extra="forbid")
    decision: str = Field(description="Decision description")
    rationale: str | None = Field(default=None, description="Decision rationale")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class Recommendation(BaseModel):
    """Section 6b: Recommendations made in video."""

    model_config = ConfigDict(extra="forbid")
    recommendation: str = Field(description="Recommendation description")
    target_audience: str | None = Field(default=None, description="Target audience")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class ActionItem(BaseModel):
    """Section 6c: Action items."""

    model_config = ConfigDict(extra="forbid")
    action: str = Field(description="Action item description")
    owner: str | None = Field(default=None, description="Owner of the action")
    due_date: str | None = Field(default=None, description="Due date or timeline")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class GlossaryTerm(BaseModel):
    """Section 7: Definitions and glossary."""

    model_config = ConfigDict(extra="forbid")
    term: str = Field(description="Technical or domain term")
    definition: str = Field(description="Definition as explained in the video")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class OpenQuestion(BaseModel):
    """Section 8a: Open questions."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(description="Unresolved question or topic left open")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class Caveat(BaseModel):
    """Section 8b: Caveats, limitations, and warnings."""

    model_config = ConfigDict(extra="forbid")
    statement: str = Field(description="Limitation, constraint, or caveat")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")


class StructuredSummaryV3(BaseModel):
    """Canonical 9-section structured summary object stored in PostgreSQL JSONB."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["summary.v3"] = "summary.v3"
    executive_overview: ExecutiveOverview
    main_thesis: MainThesis
    topics: list[Topic] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    important_details: list[ImportantDetail] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    caveats: list[Caveat] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Streaming Event Envelopes
# ---------------------------------------------------------------------------


class ReasoningDeltaEvent(BaseModel):
    """SSE event for streaming model thinking tokens."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["reasoning_delta"] = "reasoning_delta"
    content: str


class AnswerDeltaEvent(BaseModel):
    """SSE event for streaming final answer tokens."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["answer_delta"] = "answer_delta"
    content: str


class SourceItem(BaseModel):
    """Source item payload in SSE sources event."""

    video_id: str
    video_title: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    similarity: float | None = None
    content: str
    source_kind: str | None = None


class SourcesEvent(BaseModel):
    """SSE event for returning retrieved sources."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["sources"] = "sources"
    items: list[SourceItem] = Field(default_factory=list)


class UsageEvent(BaseModel):
    """SSE event for returning token usage metrics."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["usage"] = "usage"
    input_tokens: int = 0
    reasoning_tokens: int = 0
    output_tokens: int = 0


class DoneEvent(BaseModel):
    """SSE event indicating stream completion."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["done"] = "done"


StreamEvent = Annotated[
    ReasoningDeltaEvent | AnswerDeltaEvent | SourcesEvent | UsageEvent | DoneEvent,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------


def normalize_transcript_text(text: str) -> str:
    """Normalize text for whitespace, casing, and punctuation matching."""
    if not text:
        return ""
    # Collapse multiple whitespaces/newlines into a single space
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    return cleaned


def validate_quote_containment(excerpt: str, normalized_transcript: str) -> bool:
    """Check if an evidence excerpt appears verbatim within the normalized transcript."""
    if not excerpt:
        return False
    norm_excerpt = normalize_transcript_text(excerpt)
    norm_transcript = normalize_transcript_text(normalized_transcript)
    return norm_excerpt in norm_transcript


def extract_all_evidence_ids(summary: StructuredSummaryV3) -> set[str]:
    """Collect all evidence IDs referenced across all sections of a summary."""
    ids: set[str] = set()
    ids.update(summary.executive_overview.evidence_ids)
    ids.update(summary.main_thesis.evidence_ids)

    for topic in summary.topics:
        for point in topic.supporting_points:
            ids.update(point.evidence_ids)

    for chapter in summary.chapters:
        ids.update(chapter.evidence_ids)

    for detail in summary.important_details:
        ids.update(detail.evidence_ids)

    for decision in summary.decisions:
        ids.update(decision.evidence_ids)

    for rec in summary.recommendations:
        ids.update(rec.evidence_ids)

    for action in summary.action_items:
        ids.update(action.evidence_ids)

    for term in summary.glossary:
        ids.update(term.evidence_ids)

    for question in summary.open_questions:
        ids.update(question.evidence_ids)

    for caveat in summary.caveats:
        ids.update(caveat.evidence_ids)

    return ids


def validate_evidence_integrity(summary: StructuredSummaryV3) -> list[str]:
    """Validate that all referenced evidence IDs exist in summary.evidence list.

    Returns a list of error descriptions (empty if valid).
    """
    errors: list[str] = []
    defined_evidence_ids = {e.id for e in summary.evidence}
    referenced_ids = extract_all_evidence_ids(summary)

    missing = referenced_ids - defined_evidence_ids
    if missing:
        errors.append(f"Referenced evidence IDs missing from evidence list: {sorted(missing)}")

    # Check for duplicate evidence IDs
    seen: set[str] = set()
    for e in summary.evidence:
        if e.id in seen:
            errors.append(f"Duplicate evidence ID in evidence list: '{e.id}'")
        seen.add(e.id)

    return errors


def validate_summary_timestamps(summary: StructuredSummaryV3, max_duration_seconds: float | None = None) -> list[str]:
    """Validate timestamp bounds for chapters and evidence references.

    Returns a list of error descriptions (empty if valid).
    """
    errors: list[str] = []

    for e in summary.evidence:
        if e.start_seconds < 0:
            errors.append(f"Evidence {e.id} has negative start_seconds: {e.start_seconds}")
        if e.end_seconds < e.start_seconds:
            errors.append(f"Evidence {e.id} has end_seconds ({e.end_seconds}) < start_seconds ({e.start_seconds})")
        if max_duration_seconds is not None and e.end_seconds > max_duration_seconds:
            errors.append(
                f"Evidence {e.id} end_seconds ({e.end_seconds}) exceeds video duration ({max_duration_seconds})"
            )

    for c in summary.chapters:
        if c.start_seconds < 0:
            errors.append(f"Chapter '{c.title}' has negative start_seconds: {c.start_seconds}")
        if c.end_seconds < c.start_seconds:
            errors.append(f"Chapter '{c.title}' has end_seconds ({c.end_seconds}) < start_seconds ({c.start_seconds})")
        if max_duration_seconds is not None and c.end_seconds > max_duration_seconds:
            errors.append(
                f"Chapter '{c.title}' end_seconds ({c.end_seconds}) exceeds video duration ({max_duration_seconds})"
            )

    return errors
