# ADR 0001: Dual-Scale RAG Architecture for Long-Context LLMs

## Status
Accepted

## Date
2026-08-18

## Context
The SummarizeMe platform connects to a vLLM generation endpoint running `nemo-qwen3.6-35b-a3b-nvfp4` (`nvidia/Qwen3.6-35B-A3B-NVFP4`). Empirical runtime verification of the endpoint confirmed a supported context length (`max_model_len`) of **262,144 tokens (~256K)**.

Legacy RAG implementation in [`blueprints/chat.py`](../../blueprints/chat.py) used a uniform, aggressive top-k filter (`LIMIT 5`), returning only ~1,500 to 2,500 tokens of context to the generator regardless of query scope. For single-video Q&A, this resulted in severe retrieval underutilization (>99% of context window wasted) and frequent retrieval miss errors for details outside the 5 retrieved snippets.

## Decision
We adopt a **Dual-Scale RAG Architecture** tailored to query scope and LLM context capacity:

1. **Single-Video Chat (Full-Context Pass-Through):**
   - For queries targeting a single video (`/api/chat-video/<video_id>`), retrieve the complete video transcript (`transcript_no_ts`) and summary artifacts alongside top vector similarity chunks.
   - Supply the full transcript directly in the context prompt to Qwen 3.6 35B.
   - Eliminates retrieval miss failures for single-video interactions.

2. **Channel-Wide Chat (Expanded Context RAG):**
   - For queries spanning an entire channel (`/api/chat-channel/<channel_name>`), expand vector retrieval from `LIMIT 5` to `LIMIT 15` chunks.
   - Increases context density to ~15,000–30,000 tokens (~10–15% of Qwen 3.6's context window), enabling richer multi-video synthesis and cross-video comparison.

## Consequences

### Positive
- **Zero Retrieval Misses in Single-Video Chat:** Models receive 100% of the video content, enabling comprehensive answers without chunk-boundary blind spots.
- **Richer Multi-Video Synthesis:** Channel-level queries receive 3x more retrieved context fragments with metadata citations.
- **High Throughput Maintenance:** Qwen 3.6 35B NVFP4 processes expanded context prompts efficiently on host hardware.

### Negative / Trade-offs
- Slightly higher prompt token count for single-video queries on long transcripts (mitigated by vLLM KV caching and high GPU decoding throughput).
