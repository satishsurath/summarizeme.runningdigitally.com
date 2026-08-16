# PT-002: Chat Pages — Deprecated Model Selector Not Working

**Date:** 2026-08-15  
**Status:** Fixed  
**PR:** #7 (fix/chat-model-selector)

## Problem
Chat page at `/chat-channel/<channel_name>` had a model selector dropdown that:
1. Tried to load models from `/api/ollama/models` on page load
2. Fell back to `phi4:latest` on error (model doesn't exist on vLLM)
3. Chat requests failed with "Connection error" because `phi4:latest` isn't available

## Root Cause
- Model selector UI was leftover from Ollama-only era
- vLLM is now the primary LLM backend (Qwen3.6-35B-A3B-NVFP4)
- `/api/ollama/models` returns vLLM models in different format, selector fails silently
- Fallback model `phi4:latest` doesn't exist on vLLM

## Fix Applied
1. **templates/channel_chat.html:** Removed model selector dropdown (lines 30-39)
2. **templates/channel_chat.html:** Removed `loadOllamaModels()` function (lines 100-117)
3. **templates/channel_chat.html:** Removed `loadOllamaModels()` call (line 165)
4. **templates/channel_chat.html:** Hardcoded `model_name: "nemo-qwen3.6-35b-a3b-nvfp4"` in chat requests (line 116)

## Verification
- Chat page loads without errors
- Chat requests use correct model `nemo-qwen3.6-35b-a3b-nvfp4`
- Consistent with videos.html fix from PR #6

## Files Changed
- `templates/channel_chat.html` — removed model selector, use default model

## Note
`video_chat.html` did NOT have a model selector — only `channel_chat.html` was affected.
