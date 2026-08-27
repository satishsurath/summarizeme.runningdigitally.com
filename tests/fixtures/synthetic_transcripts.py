"""Synthetic transcript fixtures with deterministic timestamps, speakers, topics, and excerpts.

Used for unit testing chunking, prompt planning, evidence verification, and quality evaluation.
"""

from __future__ import annotations

from typing import Any

# Short 5-minute technical video transcript
SHORT_TECH_TRANSCRIPT: list[dict[str, Any]] = [
    {
        "start_seconds": 0.0,
        "end_seconds": 35.0,
        "speaker": "Alice",
        "text": (
            "Welcome everyone. Today we are discussing PostgreSQL 16 performance optimizations "
            "for vector search and indexing."
        ),
    },
    {
        "start_seconds": 35.0,
        "end_seconds": 90.0,
        "speaker": "Alice",
        "text": (
            "The main thesis is that using HNSW indexes with pgvector reduces query latency by "
            "80 percent compared to IVFFlat."
        ),
    },
    {
        "start_seconds": 90.0,
        "end_seconds": 180.0,
        "speaker": "Alice",
        "text": (
            "When configuring pgvector, always allocate sufficient maintenance_work_mem before building HNSW indexes."
        ),
    },
    {
        "start_seconds": 180.0,
        "end_seconds": 240.0,
        "speaker": "Alice",
        "text": (
            "In conclusion, our recommendation is to migrate all production vector tables to HNSW indexes immediately."
        ),
    },
    {
        "start_seconds": 240.0,
        "end_seconds": 300.0,
        "speaker": "Alice",
        "text": "Action item for the team: Satish will deploy the new pgvector index migration by Friday.",
    },
]

# Combined plain text for SHORT_TECH_TRANSCRIPT
SHORT_TECH_TEXT: str = " ".join(seg["text"] for seg in SHORT_TECH_TRANSCRIPT)

# Multi-speaker panel discussion transcript (20 minutes)
MULTI_SPEAKER_TRANSCRIPT: list[dict[str, Any]] = [
    {
        "start_seconds": 0.0,
        "end_seconds": 45.0,
        "speaker": "Host",
        "text": (
            "Welcome to the AI Architecture Roundtable. Today we have Bob from infrastructure "
            "and Carol from AI research."
        ),
    },
    {
        "start_seconds": 45.0,
        "end_seconds": 210.0,
        "speaker": "Bob",
        "text": (
            "From an infrastructure standpoint, running SGLang with NVFP4 quantization allows us "
            "to host a 27B parameter model on a single GPU."
        ),
    },
    {
        "start_seconds": 210.0,
        "end_seconds": 420.0,
        "speaker": "Carol",
        "text": (
            "I agree with Bob, but we caveat that reasoning models require strict token ceilings "
            "to avoid latency spikes during batch processing."
        ),
    },
    {
        "start_seconds": 420.0,
        "end_seconds": 700.0,
        "speaker": "Bob",
        "text": (
            "We decided to cap client batch generation at 2 concurrent requests while keeping "
            "1 reserved slot for interactive user chat."
        ),
    },
    {
        "start_seconds": 700.0,
        "end_seconds": 1200.0,
        "speaker": "Host",
        "text": "Thank you both. The action item is to benchmark Nomic sequence batch sizes next week.",
    },
]

# Combined plain text for MULTI_SPEAKER_TRANSCRIPT
MULTI_SPEAKER_TEXT: str = " ".join(seg["text"] for seg in MULTI_SPEAKER_TRANSCRIPT)


# Sample valid 9-section structured summary dictionary
SAMPLE_STRUCTURED_SUMMARY_DICT: dict[str, Any] = {
    "schema_version": "summary.v3",
    "executive_overview": {
        "text": "This video details PostgreSQL 16 performance optimizations using HNSW pgvector indexing.",
        "evidence_ids": ["E1"],
    },
    "main_thesis": {
        "statement": "HNSW indexes reduce query latency by 80 percent compared to IVFFlat.",
        "evidence_ids": ["E2"],
    },
    "topics": [
        {
            "title": "PostgreSQL Vector Optimization",
            "summary": "Exploration of pgvector indexing mechanisms.",
            "supporting_points": [
                {
                    "text": "HNSW offers superior latency over IVFFlat.",
                    "evidence_ids": ["E2"],
                },
                {
                    "text": "Allocate sufficient maintenance_work_mem before building indexes.",
                    "evidence_ids": ["E3"],
                },
            ],
        }
    ],
    "chapters": [
        {
            "title": "Introduction & Thesis",
            "start_seconds": 0.0,
            "end_seconds": 90.0,
            "summary": "Overview of pgvector and core latency claims.",
            "key_points": ["PostgreSQL 16 optimizations", "HNSW vs IVFFlat latency"],
            "evidence_ids": ["E1", "E2"],
        },
        {
            "title": "Configuration & Actions",
            "start_seconds": 90.0,
            "end_seconds": 300.0,
            "summary": "Configuration recommendations and next steps.",
            "key_points": ["maintenance_work_mem setting", "Migration timeline"],
            "evidence_ids": ["E3", "E4", "E5"],
        },
    ],
    "important_details": [
        {
            "statement": ("Using HNSW indexes with pgvector reduces query latency by 80 percent compared to IVFFlat."),
            "classification": "fact",
            "speaker": "Alice",
            "evidence_ids": ["E2"],
        },
        {
            "statement": "Allocate sufficient maintenance_work_mem before building HNSW indexes.",
            "classification": "recommendation",
            "speaker": "Alice",
            "evidence_ids": ["E3"],
        },
    ],
    "decisions": [
        {
            "decision": "Migrate all production vector tables to HNSW indexes immediately.",
            "rationale": "80% latency reduction.",
            "evidence_ids": ["E4"],
        }
    ],
    "recommendations": [
        {
            "recommendation": "Allocate sufficient maintenance_work_mem before building HNSW indexes.",
            "target_audience": "Database Administrators",
            "evidence_ids": ["E3"],
        }
    ],
    "action_items": [
        {
            "action": "Satish will deploy the new pgvector index migration by Friday.",
            "owner": "Satish",
            "due_date": "Friday",
            "evidence_ids": ["E5"],
        }
    ],
    "glossary": [
        {
            "term": "HNSW",
            "definition": "Hierarchical Navigable Small World graph index for approximate nearest neighbors.",
            "evidence_ids": ["E2"],
        }
    ],
    "open_questions": [
        {
            "question": "What is the memory footprint impact of HNSW on large multi-million row datasets?",
            "evidence_ids": [],
        }
    ],
    "caveats": [
        {
            "statement": "HNSW index builds consume more memory during construction than IVFFlat.",
            "evidence_ids": ["E3"],
        }
    ],
    "evidence": [
        {
            "id": "E1",
            "start_seconds": 0.0,
            "end_seconds": 35.0,
            "speaker": "Alice",
            "excerpt": (
                "Welcome everyone. Today we are discussing PostgreSQL 16 performance optimizations "
                "for vector search and indexing."
            ),
            "youtube_url": "https://www.youtube.com/watch?v=sample123&t=0s",
        },
        {
            "id": "E2",
            "start_seconds": 35.0,
            "end_seconds": 90.0,
            "speaker": "Alice",
            "excerpt": (
                "The main thesis is that using HNSW indexes with pgvector reduces query latency by "
                "80 percent compared to IVFFlat."
            ),
            "youtube_url": "https://www.youtube.com/watch?v=sample123&t=35s",
        },
        {
            "id": "E3",
            "start_seconds": 90.0,
            "end_seconds": 180.0,
            "speaker": "Alice",
            "excerpt": (
                "When configuring pgvector, always allocate sufficient maintenance_work_mem "
                "before building HNSW indexes."
            ),
            "youtube_url": "https://www.youtube.com/watch?v=sample123&t=90s",
        },
        {
            "id": "E4",
            "start_seconds": 180.0,
            "end_seconds": 240.0,
            "speaker": "Alice",
            "excerpt": (
                "In conclusion, our recommendation is to migrate all production vector tables "
                "to HNSW indexes immediately."
            ),
            "youtube_url": "https://www.youtube.com/watch?v=sample123&t=180s",
        },
        {
            "id": "E5",
            "start_seconds": 240.0,
            "end_seconds": 300.0,
            "speaker": "Alice",
            "excerpt": "Action item for the team: Satish will deploy the new pgvector index migration by Friday.",
            "youtube_url": "https://www.youtube.com/watch?v=sample123&t=240s",
        },
    ],
}
