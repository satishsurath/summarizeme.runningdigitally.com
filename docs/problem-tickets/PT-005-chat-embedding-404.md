# PT-005: Chat Failing — Embedding 404 from Wrong vLLM Endpoint

**Date:** 2026-08-15  
**Status:** Fixed  
**PR:** #7 (fix/chat-model-selector)

## Problem
Chat endpoint `/api/chat-channel/<channel_name>` failing with:
```
openai.NotFoundError: Error code: 404 - {'detail': 'Not Found'}
```

## Root Cause
Two issues:
1. **Wrong vLLM endpoint:** `_get_llm_url()` returned `VLLM_GEN_URL` (port 8000) for embeddings, but embeddings are on `VLLM_EMBED_URL` (port 8001).
2. **Wrong model name:** Code used `nomic-ai/nomic-embed-text-v1.5` but vLLM server has `nemo-nomic-embed-text-v1.5`.

## Fix Applied
1. **summarizer_v2.py:** Added `_VLLM_EMBED_HOST`, `_VLLM_EMBED_PORT`, `VLLM_EMBED_URL` config
2. **summarizer_v2.py:** Fixed `_get_llm_url(for_embedding=False)` to return embed URL when `for_embedding=True`
3. **summarizer_v2.py:** Fixed `ollama_embed_chunk()` to call `_get_llm_url(for_embedding=True)`
4. **summarizer_v2.py:** Added httpx fallback for embedding calls (same pattern as generation)
5. **summarizer_v2.py:** Fixed model name default from `nomic-ai/nomic-embed-text-v1.5` to `nemo-nomic-embed-text-v1.5`
6. **blueprints/chat.py:** Fixed model name in both chat endpoints

## Verification
- Embedding call returns valid 768-dim vector: `[0.02877..., 0.01177..., ...]`
- Chat endpoint no longer returns 404 from embedding call
- Note: Chat still fails with "UndefinedTable" for embeddings view — this is expected until PGAI vectorizer is run

## Files Changed
- `summarizer_v2.py` — embed URL config, _get_llm_url fix, model name fix, httpx fallback
- `blueprints/chat.py` — model name fix
