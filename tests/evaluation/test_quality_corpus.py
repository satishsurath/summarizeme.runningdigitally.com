"""Quality corpus benchmark & evaluation test across all 4 reasoning effort levels.

Evaluates structure conformance, quote containment, reasoning trace separation,
and performance metrics across disabled, low, medium, and xhigh reasoning levels.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from db.models import TranscriptSegment, Video
from services.contracts import StructuredSummaryV3, validate_quote_containment
from services.summary_service import SummaryService
from tests.fixtures.synthetic_transcripts import (
    SAMPLE_STRUCTURED_SUMMARY_DICT,
    SHORT_TECH_TRANSCRIPT,
)


class TestQualityCorpusBenchmark:
    """Evaluation suite for 9-section structured generation across reasoning levels."""

    @patch("services.summary_service.httpx.Client.post")
    def test_eval_across_all_reasoning_levels(self, mock_post):
        """Verify generation, evidence resolution, and clean thinking separation for all 4 reasoning levels."""
        reasoning_levels = ["disabled", "low", "medium", "xhigh"]

        for level in reasoning_levels:
            # Mock SGLang / vLLM JSON response
            mock_resp = MagicMock()
            mock_resp.status_code = 200

            reasoning_prefix = (
                f"<think>\nAnalyzing architectural tradeoffs at {level} reasoning effort...\n"
                "Checking quote containment for E1, E2, E3.\n</think>\n"
                if level != "disabled"
                else ""
            )
            raw_content = reasoning_prefix + json.dumps(SAMPLE_STRUCTURED_SUMMARY_DICT)

            mock_resp.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": raw_content,
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 850,
                },
            }
            mock_post.return_value = mock_resp

            video = Video(video_id=f"v_eval_{level}", title=f"Evaluation Benchmark - {level}")
            segments = [
                TranscriptSegment(
                    video_id=f"v_eval_{level}",
                    segment_index=i,
                    start_seconds=s["start_seconds"],
                    end_seconds=s["end_seconds"],
                    speaker=s.get("speaker"),
                    text=s["text"],
                    normalized_text=s["text"].lower(),
                    content_hash=f"hash-{i}",
                )
                for i, s in enumerate(SHORT_TECH_TRANSCRIPT)
            ]

            transcript_text = " ".join([s.text for s in segments])

            summary_v3, thinking, metrics, _errors = SummaryService.generate_structured_summary(
                transcript_text=transcript_text,
                video_title=video.title or "Evaluation Benchmark",
                reasoning_effort=level,
            )

            # 1. Structure Conformance
            assert isinstance(summary_v3, StructuredSummaryV3)
            assert summary_v3.schema_version == "summary.v3"
            assert len(summary_v3.executive_overview.text) >= 1
            assert len(summary_v3.topics) >= 1
            assert len(summary_v3.chapters) >= 1
            assert len(summary_v3.important_details) >= 1
            assert len(summary_v3.recommendations) >= 1
            assert len(summary_v3.evidence) >= 1

            # 2. Quote Containment
            contained_count = sum(
                1 for ev in summary_v3.evidence if validate_quote_containment(ev.excerpt, transcript_text)
            )
            containment_rate = contained_count / len(summary_v3.evidence) if summary_v3.evidence else 1.0
            assert containment_rate >= 0.8

            # 3. Thinking Separation
            if level == "disabled":
                assert thinking is None or thinking == ""
            else:
                assert thinking is not None
                assert f"{level} reasoning effort" in thinking
                # Thinking trace must NOT leak into the structured summary fields
                summary_json_str = summary_v3.model_dump_json()
                assert "<think>" not in summary_json_str
                assert "</think>" not in summary_json_str

            # 4. Metrics
            assert metrics["prompt_tokens"] == 1500
            assert metrics["completion_tokens"] == 850
            assert metrics["reasoning_tokens"] >= 0
