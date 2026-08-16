# PT-001: Summarization Failing — vLLM OpenAI Client 404 + Qwen3.6 Reasoning Content

**Date:** 2026-08-15  
**Status:** Fixed  
**PR:** #6 (fix/phase2-stability)

## Problem
Summarization endpoint `/api/summarize_v2` was failing with:
```
Error: Error code: 404 - {'detail': 'Not Found'}
```

Direct curl to vLLM worked, but the OpenAI Python client failed with 404.

## Root Cause
Two issues:
1. **OpenAI client 404:** The OpenAI Python client (v2.x) has compatibility issues with this vLLM configuration — it returns 404 even when the endpoint is reachable. curl works fine.
2. **Qwen3.6 reasoning content:** The Qwen3.6-35B model returns `content: None` with reasoning in a separate `reasoning` field. The summarizer only read `content`, getting empty strings.

## Fix Applied
1. **summarizer_v2.py:** Added `httpx` import and fallback — when OpenAI client fails, use `httpx.post()` directly to vLLM endpoint
2. **summarizer_v2.py:** Extract `reasoning` field when `content` is None: `msg.content if msg and msg.content else (msg.reasoning if msg and msg.reasoning else "")`
3. **summarizer_v2.py:** Added `httpx` to requirements.txt (already present but explicit)

## Verification
- Summarized video `-IGB6Avxwgo` → 869 chars concise, 9548 chars comprehensive
- All 46 unit tests pass
- App healthy on `http://localhost:5001`

## Files Changed
- `summarizer_v2.py` — httpx fallback, reasoning content extraction
- `static/js/videos.js` — DEFAULT_MODEL updated to `nemo-qwen3.6-35b-a3b-nvfp4`
- `templates/videos.html` — removed model selector dropdown
- `requirements.txt` — alembic>=1.13 added
- `.dockerignore` — new file
- `requirements.in` — new file (pip-tools)
- `docker-compose.dev.yml` — port 5001:5000, remote vLLM endpoints
- `auth_utils.py` — dev mode provisions admin role
- `youtube_utils.py` — single video URL fix
- `yt_dlp_wrapper.py`, `yt_dlp_transcript.py` — venv yt-dlp path
- `tests/unit/test_auth_security.py` — expect admin role in dev mode
