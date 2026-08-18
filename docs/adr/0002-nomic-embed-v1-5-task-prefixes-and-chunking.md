# ADR 0002: Task-Prefixed Matryoshka Embeddings & Sentence-Aware Chunking Strategy

## Status
Accepted

## Date
2026-08-18

## Context
SummarizeMe uses `nemo-nomic-embed-text-v1.5` (`nomic-ai/nomic-embed-text-v1.5`) via vLLM on port 8001 for dense vector retrieval. 

External research and Nomic Embed v1.5 specification guidelines establish two critical requirements:
1. **Instruction Task Prefixes:** Nomic v1.5 requires `search_document: ` for corpus index chunks and `search_query: ` for user retrieval queries. Omitting prefixes degrades cosine similarity scoring accuracy by 20–30%.
2. **Chunk Size & Boundary Quality:** Raw character-count chunking without sentence boundary preservation cuts through words and thoughts mid-sentence, corrupting dense vector representations.

## Decision
1. **Mandatory Task Prefix Enforcement:**
   - In [`summarizer_v2.py`](../../summarizer_v2.py) and [`run_vectorizers.py`](../../run_vectorizers.py), all document/summary chunk embedding calls pass `is_query=False` (automatically prepending `search_document: `).
   - In [`blueprints/chat.py`](../../blueprints/chat.py), all user query embedding requests pass `is_query=True` (automatically prepending `search_query: `).

2. **Sentence-Aware Overlapping Chunking:**
   - Refine `split_into_chunks()` in [`run_vectorizers.py`](../../run_vectorizers.py) to target ~1,500 characters (~300–500 words / ~450–600 tokens) with a 300-character sentence-boundary overlap window.
   - Ensures vector chunks maintain complete grammatical sentences and contextual coherence across chunk boundaries.

3. **Contextual Metadata Headers:**
   - Indexing passes prepend document metadata headers (`Video Title: ... | Section: ...`) before embedding to provide chunk-level topic context (Anthropic Contextual Retrieval pattern).

## Consequences

### Positive
- **Improved Retrieval Precision & Recall:** Adding task prefixes aligns embeddings with Nomic v1.5 contrastive training objectives.
- **Coherent Vector Chunks:** Sentence-boundary overlap eliminates severed thoughts and broken words across chunk boundaries.
- **Backward Compatibility:** Utility wrapper functions safely handle existing strings while ensuring strict prefix injection.

### Negative / Trade-offs
- Re-indexing existing PostgreSQL pgvector tables with `run_vectorizers.py` is required to upgrade historic embeddings to prefix-aware vectors.
