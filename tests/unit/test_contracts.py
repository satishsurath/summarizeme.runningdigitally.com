"""Unit tests for services/contracts.py schemas, streaming events, and validation helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.contracts import (
    AnswerDeltaEvent,
    Chapter,
    ClaimClassification,
    DoneEvent,
    EvidenceReference,
    ReasoningDeltaEvent,
    ReasoningEffort,
    SourceItem,
    SourcesEvent,
    StructuredSummaryV3,
    UsageEvent,
    validate_evidence_integrity,
    validate_quote_containment,
    validate_summary_timestamps,
)
from tests.fixtures.synthetic_transcripts import (
    SAMPLE_STRUCTURED_SUMMARY_DICT,
    SHORT_TECH_TEXT,
)


class TestSummaryContracts:
    """Test 9-section canonical summary Pydantic models."""

    def test_valid_structured_summary_v3_parse(self):
        summary = StructuredSummaryV3.model_validate(SAMPLE_STRUCTURED_SUMMARY_DICT)
        assert summary.schema_version == "summary.v3"
        assert summary.executive_overview.text.startswith("This video details")
        assert len(summary.chapters) == 2
        assert len(summary.evidence) == 5
        assert summary.important_details[0].classification == ClaimClassification.FACT
        assert summary.important_details[1].classification == ClaimClassification.RECOMMENDATION

    def test_missing_required_section_fails(self):
        invalid_dict = dict(SAMPLE_STRUCTURED_SUMMARY_DICT)
        del invalid_dict["executive_overview"]
        with pytest.raises(ValidationError):
            StructuredSummaryV3.model_validate(invalid_dict)

    def test_invalid_claim_classification_fails(self):
        invalid_dict = dict(SAMPLE_STRUCTURED_SUMMARY_DICT)
        invalid_dict["important_details"] = [
            {
                "statement": "Some statement",
                "classification": "unsupported_classification",
                "evidence_ids": ["E1"],
            }
        ]
        with pytest.raises(ValidationError):
            StructuredSummaryV3.model_validate(invalid_dict)

    def test_timestamp_ordering_validation_on_evidence(self):
        with pytest.raises(ValidationError, match=r"end_seconds .* must be greater than or equal to start_seconds"):
            EvidenceReference(
                id="E1",
                start_seconds=100.0,
                end_seconds=50.0,
                excerpt="Some quote",
            )

    def test_timestamp_ordering_validation_on_chapter(self):
        with pytest.raises(ValidationError, match=r"Chapter end_seconds .* must be >= start_seconds"):
            Chapter(
                title="Intro",
                start_seconds=120.0,
                end_seconds=60.0,
                summary="Chapter summary",
            )


class TestStreamingEventContracts:
    """Test SSE streaming event models."""

    def test_reasoning_delta_event(self):
        event = ReasoningDeltaEvent(content="Analyzing the architecture...")
        assert event.type == "reasoning_delta"
        assert event.content == "Analyzing the architecture..."
        json_data = event.model_dump()
        assert json_data["type"] == "reasoning_delta"

    def test_answer_delta_event(self):
        event = AnswerDeltaEvent(content="PostgreSQL 16 offers...")
        assert event.type == "answer_delta"
        assert event.content == "PostgreSQL 16 offers..."

    def test_usage_event(self):
        event = UsageEvent(input_tokens=150, reasoning_tokens=80, output_tokens=220)
        assert event.type == "usage"
        assert event.reasoning_tokens == 80

    def test_done_event(self):
        event = DoneEvent()
        assert event.type == "done"

    def test_sources_event(self):
        event = SourcesEvent(
            items=[
                SourceItem(
                    video_id="vid123",
                    video_title="Test Video",
                    similarity=0.88,
                    content="Test content snippet",
                )
            ]
        )
        assert event.type == "sources"
        assert len(event.items) == 1
        assert event.items[0].video_id == "vid123"


class TestValidationHelpers:
    """Test quote containment, evidence reference integrity, and timestamp validators."""

    def test_quote_containment_exact_match(self):
        excerpt = "allocate sufficient maintenance_work_mem before building HNSW indexes"
        assert validate_quote_containment(excerpt, SHORT_TECH_TEXT) is True

    def test_quote_containment_whitespace_and_case_insensitive(self):
        excerpt = "Allocate   Sufficient  maintenance_work_mem\nbefore building HNSW indexes."
        assert validate_quote_containment(excerpt, SHORT_TECH_TEXT) is True

    def test_quote_containment_hallucination_fails(self):
        excerpt = "This sentence was never spoken in the video transcript at all."
        assert validate_quote_containment(excerpt, SHORT_TECH_TEXT) is False

    def test_quote_containment_empty_returns_false(self):
        assert validate_quote_containment("", SHORT_TECH_TEXT) is False

    def test_evidence_integrity_passes_on_valid_summary(self):
        summary = StructuredSummaryV3.model_validate(SAMPLE_STRUCTURED_SUMMARY_DICT)
        errors = validate_evidence_integrity(summary)
        assert errors == []

    def test_evidence_integrity_fails_on_missing_evidence_id(self):
        data = dict(SAMPLE_STRUCTURED_SUMMARY_DICT)
        data["executive_overview"] = {
            "text": "Summary text",
            "evidence_ids": ["E999"],  # E999 does not exist in evidence list
        }
        summary = StructuredSummaryV3.model_validate(data)
        errors = validate_evidence_integrity(summary)
        assert len(errors) == 1
        assert "E999" in errors[0]

    def test_evidence_integrity_detects_duplicate_ids(self):
        data = dict(SAMPLE_STRUCTURED_SUMMARY_DICT)
        # Duplicate E1
        data["evidence"] = [*list(data["evidence"]), data["evidence"][0]]
        summary = StructuredSummaryV3.model_validate(data)
        errors = validate_evidence_integrity(summary)
        assert len(errors) == 1
        assert "Duplicate evidence ID" in errors[0]

    def test_timestamp_bounds_validator(self):
        summary = StructuredSummaryV3.model_validate(SAMPLE_STRUCTURED_SUMMARY_DICT)
        # Video duration 300s -> all valid
        errors = validate_summary_timestamps(summary, max_duration_seconds=300.0)
        assert errors == []

        # Video duration 100s -> chapters and evidence > 100s will fail
        errors = validate_summary_timestamps(summary, max_duration_seconds=100.0)
        assert len(errors) > 0
        assert any("exceeds video duration" in err for err in errors)


class TestReasoningEffortEnum:
    """Test ReasoningEffort enum values."""

    def test_reasoning_effort_values(self):
        assert ReasoningEffort.DISABLED == "disabled"
        assert ReasoningEffort.LOW == "low"
        assert ReasoningEffort.MEDIUM == "medium"
        assert ReasoningEffort.XHIGH == "xhigh"
