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


class SummaryService:
    """Service for generating and validating 9-section structured video summaries."""

    @staticmethod
    def generate_structured_summary(
        transcript_text: str,
        video_title: str = "Video",
        model_name: str = DEFAULT_GEN_MODEL,
        reasoning_effort: str = "medium",
        base_url: str = VLLM_GEN_URL,
        timeout_seconds: float = 180.0,
    ) -> tuple[StructuredSummaryV3, str | None, dict[str, int]]:
        """Call generation endpoint with SGLang JSON schema format to produce StructuredSummaryV3.

        Returns (StructuredSummaryV3, reasoning_output, usage_dict).
        """
        schema = StructuredSummaryV3.model_json_schema()
        user_prompt = (
            f"Video Title: {video_title}\n\n"
            f"Transcript:\n{transcript_text}\n\n"
            "Generate full 9-section structured summary JSON."
        )

        messages = [
            {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

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

        # Apply reasoning effort if enabled
        if reasoning_effort != ReasoningEffort.DISABLED:
            payload["reasoning_effort"] = reasoning_effort

        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        logger.info(
            "Requesting structured summary from %s (model=%s, reasoning=%s)",
            url,
            model_name,
            reasoning_effort,
        )

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

        # Validate JSON content
        try:
            summary = StructuredSummaryV3.model_validate_json(raw_content)
        except Exception as exc:
            logger.warning("Initial JSON parsing failed: %s. Attempting extraction.", exc)
            # Attempt to extract JSON substring if extra markdown fences exist
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if match:
                summary = StructuredSummaryV3.model_validate_json(match.group(0))
            else:
                raise

        # Check evidence integrity
        integrity_errors = validate_evidence_integrity(summary)
        if integrity_errors:
            logger.warning("Evidence integrity warnings for %s: %s", video_title, integrity_errors)

        # Check quote containment against source transcript
        ungrounded_quotes = [
            ev.id for ev in summary.evidence if not validate_quote_containment(ev.excerpt, transcript_text)
        ]
        if ungrounded_quotes:
            logger.warning(
                "Detected ungrounded evidence quotes %s in summary for %s",
                ungrounded_quotes,
                video_title,
            )

        return summary, reasoning_content, usage_dict

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

        # Assemble transcript text: prioritize transcript_segments, fallback to transcript_with_ts or transcript_no_ts
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
        summary, reasoning_output, usage = SummaryService.generate_structured_summary(
            transcript_text=transcript_text,
            video_title=title,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            base_url=base_url,
        )

        now = utcnow()

        # 1. Append an immutable generation record. Re-summarization must retain
        # prior output and reasoning for auditability and comparison.
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
            status="completed",
            created_at=now,
        )
        session.add(summary_run)

        # 2. Dual-write legacy SummariesV2 projection
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
            "Saved StructuredSummaryV3 and SummaryRun %s for video %s",
            summary_run.id,
            video_id,
        )

        return summary_run, summary
