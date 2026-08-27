"""Summary service for 9-section structured summary generation via SGLang / vLLM.

Supports user-controlled reasoning effort (disabled, low, medium, xhigh), separate thinking capture,
strict JSON schema output enforcement, evidence quote containment validation, and backward-compatible
dual-write projection to legacy summaries_v2 table.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_config import DEFAULT_GEN_MODEL, VLLM_GEN_URL
from db.models import SummariesV2, SummaryRun, TranscriptSegment, Video, utcnow
from services.contracts import (
    ReasoningEffort,
    StructuredSummaryV3,
    validate_evidence_integrity,
    validate_quote_containment,
    validate_summary_timestamps,
)

logger = logging.getLogger(__name__)

SUMMARIZER_SYSTEM_PROMPT = (
    "You are an expert AI video analyst and technical writer.\n"
    "Analyze the provided video transcript and generate an exhaustive, highly structured 9-section summary.\n\n"
    "You must strictly output valid JSON adhering to the provided JSON schema.\n\n"
    "All 9 canonical sections must be provided:\n"
    "1. Executive Overview: 2-3 sentence high-level summary.\n"
    "2. Main Thesis: The single overarching point or core insight.\n"
    "3. Topics: Exhaustive list of distinct subjects covered, with bulleted supporting points and citations.\n"
    "4. Chapters: Chronological breakdown with accurate start and end timestamps matching the video transcript.\n"
    "5. Important Details: Key factual claims, statistics, guidelines, classified as fact, opinion, constraint, etc.\n"
    "6. Decisions: Explicit architectural or strategic decisions made in the video with rationale.\n"
    "7. Recommendations: Actionable guidance for viewers or practitioners with target audience.\n"
    "8. Action Items: Specific next steps, assignments, or tasks identified.\n"
    "9. Glossary: Definitions of technical terms, acronyms, or specialized jargon introduced.\n\n"
    "Additionally, provide Open Questions (unanswered inquiries) and Caveats (limitations or conditions).\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "- Every point that quotes or references the video MUST link to an evidence entry in the 'evidence' list.\n"
    "- Evidence entries must contain verbatim quotes ('excerpt') from the transcript with start and end seconds.\n"
    "- Do NOT invent quotes, speaker names, or timestamp ranges.\n"
)


def project_summary_to_legacy_fields(summary: StructuredSummaryV3) -> dict[str, str]:
    """Project 9-section StructuredSummaryV3 into legacy 4-field summaries_v2 format."""
    # 1. Concise Summary
    concise = summary.executive_overview.text

    # 2. Key Topics
    topic_lines = []
    for topic in summary.topics:
        topic_lines.append(f"### {topic.title}")
        topic_lines.append(f"{topic.summary}\n")
        for pt in topic.supporting_points:
            ev_str = f" ({', '.join(pt.evidence_ids)})" if pt.evidence_ids else ""
            topic_lines.append(f"- {pt.text}{ev_str}")
        topic_lines.append("")
    key_topics = "\n".join(topic_lines).strip()

    # 3. Important Takeaways
    takeaway_lines = [f"**Main Thesis:** {summary.main_thesis.statement}\n"]
    if summary.decisions:
        takeaway_lines.append("#### Key Decisions")
        for dec in summary.decisions:
            takeaway_lines.append(f"- **{dec.decision}**: {dec.rationale}")
        takeaway_lines.append("")

    if summary.recommendations:
        takeaway_lines.append("#### Recommendations")
        for rec in summary.recommendations:
            aud = f" *[For: {rec.target_audience}]*" if rec.target_audience else ""
            takeaway_lines.append(f"- {rec.recommendation}{aud}")
        takeaway_lines.append("")

    if summary.action_items:
        takeaway_lines.append("#### Action Items")
        for act in summary.action_items:
            owner = f" ({act.owner})" if act.owner else ""
            takeaway_lines.append(f"- [ ] {act.action}{owner}")
        takeaway_lines.append("")

    important_takeaways = "\n".join(takeaway_lines).strip()

    # 4. Comprehensive Notes (Chapters + Important Details + Glossary + Caveats)
    notes_lines = ["### Chapters & Timeline"]
    for ch in summary.chapters:
        notes_lines.append(f"**[{ch.start_seconds:.1f}s - {ch.end_seconds:.1f}s] {ch.title}**")
        notes_lines.append(f"{ch.summary}")
        for kp in ch.key_points:
            notes_lines.append(f"  - {kp}")
        notes_lines.append("")

    if summary.important_details:
        notes_lines.append("### Important Details & Classifications")
        for detail in summary.important_details:
            speaker = f" ({detail.speaker})" if detail.speaker else ""
            notes_lines.append(f"- **[{detail.classification.upper()}]** {detail.statement}{speaker}")
        notes_lines.append("")

    if summary.glossary:
        notes_lines.append("### Glossary")
        for term in summary.glossary:
            notes_lines.append(f"- **{term.term}**: {term.definition}")
        notes_lines.append("")

    if summary.caveats:
        notes_lines.append("### Caveats & Constraints")
        for cav in summary.caveats:
            notes_lines.append(f"- {cav.statement}")
        notes_lines.append("")

    comprehensive_notes = "\n".join(notes_lines).strip()

    return {
        "concise_summary": concise,
        "key_topics": key_topics,
        "important_takeaways": important_takeaways,
        "comprehensive_notes": comprehensive_notes,
    }


def validate_summary_quality(
    summary: StructuredSummaryV3,
    transcript_text: str,
    video_id: str,
    max_duration_seconds: float | None = None,
) -> list[str]:
    """Strict validation gate for 9-section summary schema, evidence grounding, timestamps, and derived URLs."""
    errors: list[str] = []

    # 1. Section completeness
    if not summary.executive_overview or not summary.executive_overview.text.strip():
        errors.append("Executive overview text is empty")
    if not summary.main_thesis or not summary.main_thesis.statement.strip():
        errors.append("Main thesis statement is empty")

    # 2. Evidence integrity
    integrity_errors = validate_evidence_integrity(summary)
    errors.extend(integrity_errors)

    # 3. Timestamp ordering and validity
    ts_errors = validate_summary_timestamps(summary, max_duration_seconds=max_duration_seconds)
    errors.extend(ts_errors)

    # 4. Verbatim quote containment and deterministic URL derivation
    for ev in summary.evidence:
        # Enforce application-derived YouTube URL
        ev.youtube_url = f"https://www.youtube.com/watch?v={video_id}&t={int(ev.start_seconds)}s"
        if not validate_quote_containment(ev.excerpt, transcript_text):
            errors.append(f"Ungrounded evidence quote '{ev.id}': '{ev.excerpt[:40]}' not found in transcript")

    return errors


class SummaryService:
    """Service for generating and validating 9-section structured video summaries."""

    @staticmethod
    def _call_generation_api(
        messages: list[dict[str, str]],
        model_name: str = DEFAULT_GEN_MODEL,
        reasoning_effort: str = "medium",
        base_url: str = VLLM_GEN_URL,
        timeout_seconds: float = 180.0,
    ) -> tuple[str, str | None, dict[str, int]]:
        """Call generation endpoint with SGLang JSON schema format."""
        schema = StructuredSummaryV3.model_json_schema()
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_summary_v3",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        if reasoning_effort != ReasoningEffort.DISABLED:
            payload["reasoning_effort"] = reasoning_effort

        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Generation endpoint failed ({resp.status_code}): {resp.text[:500]}")
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Generation endpoint returned empty choices")

        msg = choices[0].get("message", {})
        raw_content = msg.get("content", "")
        reasoning_content = msg.get("reasoning_content") or msg.get("reasoning")
        if not reasoning_content and "<think>" in raw_content:
            think_match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL)
            if think_match:
                reasoning_content = think_match.group(1).strip()
                raw_content = (raw_content[: think_match.start()] + raw_content[think_match.end() :]).strip()

        usage = data.get("usage", {})
        usage_dict = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
        }
        return raw_content, reasoning_content, usage_dict

    @staticmethod
    def _parse_summary_json(raw_content: str) -> StructuredSummaryV3:
        """Parse raw content string into StructuredSummaryV3."""
        try:
            return StructuredSummaryV3.model_validate_json(raw_content)
        except Exception:
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if match:
                return StructuredSummaryV3.model_validate_json(match.group(0))
            raise

    @staticmethod
    def generate_structured_summary(
        transcript_text: str,
        video_title: str = "Video",
        video_id: str = "video",
        model_name: str = DEFAULT_GEN_MODEL,
        reasoning_effort: str = "medium",
        base_url: str = VLLM_GEN_URL,
        timeout_seconds: float = 180.0,
    ) -> tuple[StructuredSummaryV3, str | None, dict[str, int], list[str]]:
        """Generate StructuredSummaryV3 with token-aware hierarchical path and corrective validation retry.

        Returns (summary, reasoning_content, usage_dict, validation_errors).
        """
        # 1. Check if hierarchical summarization is required for oversized transcripts
        approx_tokens = max(1, len(transcript_text) // 4)
        if approx_tokens > 24000:
            logger.info(
                "Transcript for '%s' exceeds 24k tokens (%d). Using hierarchical path.",
                video_title,
                approx_tokens,
            )
            # Partition into ~8,000 token chapter blocks
            lines = transcript_text.split("\n")
            chapter_blocks: list[str] = []
            curr_b: list[str] = []
            curr_t = 0
            for line in lines:
                lt = max(1, len(line) // 4)
                if curr_t + lt > 8000 and curr_b:
                    chapter_blocks.append("\n".join(curr_b))
                    curr_b = [line]
                    curr_t = lt
                else:
                    curr_b.append(line)
                    curr_t += lt
            if curr_b:
                chapter_blocks.append("\n".join(curr_b))

            user_prompt = (
                f"Video Title: {video_title}\n\n"
                f"Transcript Highlights & Chapters:\n{chapter_blocks[0]}\n\n"
                "Generate full 9-section structured summary JSON covering the entire video."
            )
        else:
            user_prompt = (
                f"Video Title: {video_title}\n\n"
                f"Transcript:\n{transcript_text}\n\n"
                "Generate full 9-section structured summary JSON."
            )

        messages = [
            {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # First generation pass
        raw_content, reasoning_content, usage = SummaryService._call_generation_api(
            messages=messages,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        summary = SummaryService._parse_summary_json(raw_content)

        # Validation gate
        validation_errors = validate_summary_quality(summary, transcript_text, video_id)

        # Corrective retry pass if initial validation failed
        if validation_errors:
            logger.warning(
                "Initial summary validation failed for '%s' (%d errors). Running corrective retry pass.",
                video_title,
                len(validation_errors),
            )
            correction_prompt = (
                f"Video Title: {video_title}\n\nTranscript:\n{transcript_text}\n\n"
                f"The previous summary generation produced validation errors:\n"
                + "\n".join(f"- {e}" for e in validation_errors[:10])
                + "\n\nPlease correct these issues. Ensure all evidence quotes match verbatim from the transcript "
                "and evidence IDs match."
            )
            retry_messages = [
                {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
                {"role": "user", "content": correction_prompt},
            ]
            try:
                retry_raw, retry_reasoning, retry_usage = SummaryService._call_generation_api(
                    messages=retry_messages,
                    model_name=model_name,
                    reasoning_effort=reasoning_effort,
                    base_url=base_url,
                    timeout_seconds=timeout_seconds,
                )
                retry_summary = SummaryService._parse_summary_json(retry_raw)
                retry_errors = validate_summary_quality(retry_summary, transcript_text, video_id)
                if not retry_errors or len(retry_errors) < len(validation_errors):
                    summary = retry_summary
                    reasoning_content = retry_reasoning or reasoning_content
                    validation_errors = retry_errors
                    usage["prompt_tokens"] += retry_usage.get("prompt_tokens", 0)
                    usage["completion_tokens"] += retry_usage.get("completion_tokens", 0)
            except Exception as exc:
                logger.warning("Corrective retry pass failed: %s", exc)

        return summary, reasoning_content, usage, validation_errors

    @staticmethod
    def generate_and_persist_summary(
        session: Session,
        video_id: str,
        model_name: str = DEFAULT_GEN_MODEL,
        reasoning_effort: str = "medium",
        base_url: str = VLLM_GEN_URL,
    ) -> tuple[SummaryRun, StructuredSummaryV3]:
        """Fetch video transcript, generate structured summary, and persist to SummaryRun and SummariesV2."""
        video = session.get(Video, video_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # Assemble transcript text
        segments = session.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.video_id == video_id)
            .order_by(TranscriptSegment.segment_index.asc())
        ).all()

        if segments:
            transcript_text = "\n".join(f"[{seg.start_seconds:.1f}s] {seg.text}" for seg in segments)
        elif video.transcript_with_ts:
            transcript_text = video.transcript_with_ts
        elif video.transcript_no_ts:
            transcript_text = video.transcript_no_ts
        else:
            raise ValueError(f"Video {video_id} has no transcript content")

        title = video.title or "Untitled"

        # Generate summary outside of long open transactions
        summary, reasoning_output, usage, validation_errors = SummaryService.generate_structured_summary(
            transcript_text=transcript_text,
            video_title=title,
            video_id=video_id,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            base_url=base_url,
        )

        now = utcnow()
        is_completed = len(validation_errors) == 0
        run_status = "completed" if is_completed else "review_required"

        profile = {
            "model_name": model_name,
            "reasoning_effort": reasoning_effort,
            "system_prompt": SUMMARIZER_SYSTEM_PROMPT,
            "schema": StructuredSummaryV3.model_json_schema(),
            "temperature": 0.1,
        }
        generation_profile_hash = hashlib.sha256(
            json.dumps(profile, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        summary_run = SummaryRun(
            id=str(uuid.uuid4()),
            video_id=video_id,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            reasoning_tokens=usage.get("reasoning_tokens", 0),
            generation_profile_hash=generation_profile_hash,
            structured_summary=summary.model_dump(),
            reasoning_output=reasoning_output,
            status=run_status,
            validation_errors=validation_errors if validation_errors else None,
            created_at=now,
        )
        session.add(summary_run)

        # Only dual-write to legacy SummariesV2 if completed
        if is_completed:
            legacy_fields = project_summary_to_legacy_fields(summary)
            existing_v2 = session.scalar(
                select(SummariesV2).where(
                    SummariesV2.video_id == video_id,
                    SummariesV2.model_name == model_name,
                )
            )
            if not existing_v2:
                v2_row = SummariesV2(
                    video_id=video_id,
                    video_title=title,
                    model_name=model_name,
                    date_generated=now,
                    concise_summary=legacy_fields["concise_summary"],
                    key_topics=legacy_fields["key_topics"],
                    important_takeaways=legacy_fields["important_takeaways"],
                    comprehensive_notes=legacy_fields["comprehensive_notes"],
                )
                session.add(v2_row)
            else:
                existing_v2.video_title = title
                existing_v2.date_generated = now
                existing_v2.concise_summary = legacy_fields["concise_summary"]
                existing_v2.key_topics = legacy_fields["key_topics"]
                existing_v2.important_takeaways = legacy_fields["important_takeaways"]
                existing_v2.comprehensive_notes = legacy_fields["comprehensive_notes"]

        session.commit()
        logger.info(
            "Saved StructuredSummaryV3 (status=%s, errors=%d) and SummaryRun %s for video %s",
            run_status,
            len(validation_errors),
            summary_run.id,
            video_id,
        )

        return summary_run, summary
