# PT-007: Chat Thinking Block Dissolving into Main Answer Post-Stream Completion

**Date:** 2026-08-18  
**Status:** Fixed  

## Problem
During live SSE response streaming, model reasoning/thinking processes (prefixed with `Here's a thinking process:` or wrapped in `<think>...</think>`) rendered correctly inside a dedicated `<ThinkingBlock />` accordion component. However, as soon as streaming completed (`onDone` fired), the thinking block dissolved back into the main response text bubble.

## Root Cause
When model generation finished, the backend SSE completion handler in `blueprints/chat.py` formatted the complete generated response string (`full_answer`) using `md_safe(full_answer)`. Because `full_answer` contained the thinking prefix `Here's a thinking process:`, `md_safe()` converted the entire text into HTML paragraphs (`<p>Here's a thinking process:</p>...`).

When the frontend updated message state with this final HTML payload, the leading `<p>` tag prevented `parseThinkingContent()` from matching the thinking prefix regex (`/^(?:Here's a thinking process:|Thinking Process:)/i`). As a result, `parseThinkingContent()` failed to extract the thinking block and dumped the full HTML string directly into the main answer bubble.

## Fix Applied
1. **Backend Isolation (`blueprints/chat.py`)**:
   - Added `separate_thinking_and_answer()` helper function.
   - Isolates `thinking` from `main_answer` *prior* to running `md_safe()`.
   - Runs `md_safe()` ONLY on `main_answer` + context video links.
   - Formats final SSE payload as `<think>{thinking}</think>\n\n{answer_html}` (or `{answer_html}` if no thinking was generated).
2. **Frontend Parser & HTML Handling (`frontend/src/lib/thinking.ts`)**:
   - Updated `parseThinkingContent()` to decode and normalize HTML-escaped `<think>` tags (`&lt;think&gt;` -> `<think>`).
   - Extended regex prefix matching to handle HTML-wrapped element prefixes (`(?:\s*<(?:p|div|span|strong)[^>]*>)*\s*(?:Here's a thinking process:|Thinking Process:)`).
   - Escaped slashes in regular expression literals (`<\/p>`) for Turbopack/TypeScript compatibility.
3. **Unit Tests (`tests/unit/test_thinking_parser.py`)**:
   - Added unit tests verifying `separate_thinking_and_answer()` with reasoning prefixes, `<think>` XML tags, and direct answers without reasoning.

## Verification
- Added 3 unit tests in `tests/unit/test_thinking_parser.py`.
- Ran 237 passing unit tests in pytest (`.venv/bin/pytest tests/unit/ -q`).
- Passed `ruff check`, `ruff format`, and `pyright` type checks with 0 errors.
- Built Next.js production bundle without errors (`npm --prefix frontend run build`).
- Rebuilt Docker containers (`docker compose up -d --build`) and confirmed healthy runtime (`curl http://localhost:5001/health`).

## Files Changed
- `blueprints/chat.py` — added `separate_thinking_and_answer()`, updated streaming and non-streaming endpoints
- `frontend/src/lib/thinking.ts` — updated `parseThinkingContent()` to handle HTML-wrapped thinking blocks and tags
- `tests/unit/test_thinking_parser.py` — added unit tests for `separate_thinking_and_answer()`
- `walkthrough.md` — updated walkthrough documentation
