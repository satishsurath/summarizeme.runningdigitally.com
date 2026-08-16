# Testing Maturity Audit — SummarizeMe

**Date:** 2026-08-15
**Agent:** TestAudit

## 1. Route Coverage (15/25 tested = 60%)

### Covered routes (12):
- `index()` — tested in tests/integration/test_endpoints.py:14-17
- `api_list_channels()` — tested in tests/integration/test_endpoints.py:21-33, 36-48
- `api_rename_channel()` — auth tested (test_endpoints.py:50-55)
- `api_refresh_channel()` — auth tested (test_endpoints.py:62-65)
- `api_delete_channel()` — auth tested (test_endpoints.py:57-60)
- `api_summarize_v2()` — tested in tests/integration/test_endpoints.py:68-82
- `api_summarize_v2_status()` — tested in tests/integration/test_endpoints.py:84-87
- `api_chat_channel()` — empty query tested (test_endpoints.py:90-93)
- `api_chat_video()` — empty query tested (test_endpoints.py:95-101)
- `api_ollama_models()` — tested in tests/integration/test_endpoints.py:104-110
- `admin_settings()` — tested in tests/unit/test_auth.py:84-97, tests/integration/test_endpoints.py:103-106
- `admin_update_role()` — tested in tests/integration/test_endpoints.py:108-111
- `admin_add_user()` — tested in tests/integration/test_endpoints.py:113-117

### UNTESTED routes (10/25) — Critical gaps:
- `status_page()` (app.py:131) — no test exists
- `videos_page(channel_name)` (app.py:139) — no test
- `api_channel_start()` (app.py:167) — no test. Core admin function, completely untested.
- `api_channel_status(task_id)` (app.py:203) — no test
- `api_get_videos(channel_name)` (app.py:214) — no test. Core API with pagination, sorting, filtering — all untested.
- `api_all_tasks()` (app.py:592) — no test
- `view_summary_v2(summary_id)` (app.py:662) — no test
- `view_transcript_v2(video_id)` (app.py:696) — no test
- `chat_channel_page(channel_name)` (app.py:793) — no test
- `chat_video_page(video_id)` (app.py:946) — no test

### Untested functions/modules:
- `download_channel_transcripts()` (youtube_utils.py:28-120) — zero tests
- `get_channel_and_videos()` (youtube_utils.py:123-160) — zero tests
- `get_upload_date_for_video()` (youtube_utils.py:163-185) — zero tests
- `get_transcript_for_video()` (youtube_utils.py:188-210) — zero tests
- `ollama_generate_chunk()` (summarizer_v2.py:98-140) — only 1 mock test
- `ollama_embed_chunk()` (summarizer_v2.py:192-220) — zero tests
- `run_vectorizers.py` — entire file, zero tests
- `yt_dlp_wrapper.py` HTTP service — zero tests
- `yt_dlp_transcript.py` HTTP service — zero tests

## 2. Test Quality

### 2a. Assertions — Issues
- tests/integration/test_endpoints.py:91-92: **Contradictory test** — docstring says "Chat-video should reject empty queries" and comment says "Empty query → should return an error" but asserts `resp.status_code == 200` and checks for `"answer"` key. The actual behavior differs from the test's stated intent.
- tests/integration/test_endpoints.py:20, 34, 40, 45, 51, 57, 63, 69, 75, 81, 87, 93, 99, 105, 111, 117: 16 tests assert only `status_code` without checking response body content.
- No tests assert on response JSON schema (required keys, types, value ranges).
- No tests assert on DB state changes after operations.

### 2b. Fixtures (conftest.py) — Issues

**conftest.py:31-39 — Test database setup:**
- Creates a temp file DB at module import time. If multiple test sessions run in parallel, they may collide on `/tmp`.
- No cleanup of the temp file between test runs — stale DB files accumulate.

**conftest.py:42-49 — `_test_db` fixture (session-scoped):**
- Session-scoped means tables persist across ALL tests. No per-test cleanup.
- No transaction rollback between tests — tests share state.

**conftest.py:67-92 — admin_user, member_user, reader_user fixtures:**
- Each fixture creates its own `SessionLocal()` engine (3 redundant engines) instead of using the `with_db` fixture's engine.
- Uses hardcoded email addresses — tests using these fixtures may conflict if run in parallel.
- No cleanup — users persist across all tests in the session.

**conftest.py:95-114 — `mock_ollama_response` fixture:**
- **Strength**: Clean dependency injection for LLM tests. Patches at the right level.
- **Issue**: Only mocks vLLM path. No equivalent mock for Ollama path.

### 2c. Edge Case Coverage Gaps — Critical

- No tests for empty databases (no channels, no videos, no users)
- No tests for concurrent access to `download_statuses` / `summarize_v2_statuses` (app.py:78-79)
- No tests for invalid JSON input to JSON endpoints
- No tests for SQL injection attempts (despite code claiming SQL injection fix at app.py:720-770)
- No tests for rate limiting (app.config["TESTING"] = True at conftest.py:39 disables it)
- No tests for large payloads (e.g., 1000 video_ids in summarize request)
- No tests for database constraint violations (duplicate emails, FK violations)
- No tests for network failures (yt-dlp wrapper timeout, LLM API failure)

## 3. Integration Test Completeness

### 3.1 Missing Integration Tests
- Full channel download pipeline: start → poll status → verify completion → verify DB state
- Full summarize pipeline: start → poll status → verify completion → verify DB inserts (SummariesV2 rows)
- Chat pipeline: query → verify embedding → verify vector search → verify LLM response
- Cross-route workflows: create channel → add video → generate summary → chat about video
- DB migration tests: init_db.py, update_db.py — no tests verify schema is correct
- Error path integration: DB connection failure, LLM API timeout, yt-dlp wrapper failure

## 4. Mock Usage Analysis

### 4.1 Missing Mocks
- **No mock for `youtube_utils.download_channel_transcripts`**: Would enable testing `api_channel_start()` without requiring real YouTube access.
- **No mock for `requests.get` in `api_ollama_models()`**: Would enable testing vLLM model listing path.
- **No mock for `SessionLocal` / DB queries**: All tests create real DB records. This makes tests slow and state-dependent.
- **No mock for `threading.Thread`**: Background threads in `api_channel_start()` and `api_summarize_v2()` are never awaited or verified.

## 5. Severity Summary

| Severity | Count | Details |
|----------|-------|---------|
| **Critical** | 5 | (1) api_channel_start completely untested, (2) api_delete_channel cascade delete logic untested, (3) api_get_videos completely untested, (4) tests/integration/test_endpoints.py:24 references nonexistent file (dead code), (5) No per-test DB isolation |
| **Major** | 8 | (1) No error-path tests, (2) No pipeline integration tests, (3) No concurrency tests, (4) No input validation tests, (5) No DB state assertions, (6) No background thread completion tests, (7) No SQL injection tests, (8) Contradictory test at test_endpoints.py:91-92 |
| **Minor** | 5 | (1) Redundant fixture engines, (2) Inconsistent assertion style, (3) Missing response body assertions in 16 tests, (4) No schema validation, (5) Stale temp DB files |

## 6. Recommendations (Priority Order)

1. Add tests for `api_get_videos()` — pagination, sorting, filtering, empty results
2. Add tests for `api_delete_channel()` — folder not found, cascade delete, preserved videos, auth
3. Add tests for `api_channel_start()` — mock `download_channel_transcripts`, test task creation, test background thread completion
4. Add per-test DB isolation — use `with_db` fixture consistently, add autouse transaction rollback
5. Add error-path tests — DB errors, network failures, empty responses, invalid inputs
6. Add integration pipeline test — create channel → add video → generate summary → chat
7. Remove dead code — tests/integration/test_endpoints.py:24 references nonexistent file
8. Fix contradictory test — tests/integration/test_endpoints.py:91-92
9. Add mock for `download_channel_transcripts`
10. Add mock for `requests.get`
