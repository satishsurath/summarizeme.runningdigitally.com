# Problem Ticket: Status Page Errors, Chat Failures, and Video Refresh

**Date:** 2026-08-17
**Repository:** summarizeme.runningdigitally.com
**Status:** Resolved

---

## Problem 1: `/summaries/2` Page Shows Placeholder Text

### Symptoms
- Visiting `http://localhost:3000/summaries/2` displays placeholder text instead of actual summary content
- No API endpoint existed to serve summary data to the Next.js frontend

### Root Cause
- Flask backend had no JSON API endpoint for individual summaries
- Next.js frontend had no route to proxy summary requests to Flask

### Fix
- Added `GET /api/summaries/<int:summary_id>` endpoint in `blueprints/main.py`
- Created Next.js API route at `frontend/src/app/api/summaries/[id]/route.ts`
- Updated `frontend/src/app/summaries/[id]/page.tsx` to fetch and render real content in tabs

---

## Problem 2: Docker Networking — Next.js Can't Reach Flask

### Symptoms
- `GET /api/summaries/2 500` errors in Next.js dev server logs
- `wget` from inside the frontend container failed with `Connection refused`

### Root Cause
- `NEXT_API_URL` in `docker-compose.dev.yml` was set to `http://app:5001`
- Port 5001 is the **host-facing** port; inside the Docker network, Flask listens on port 5000

### Fix
- Changed `NEXT_API_URL` from `http://app:5001` to `http://app:5000` in `docker-compose.dev.yml`

---

## Problem 3: `'TaskStore' object is not subscriptable`

### Symptoms
- Status page shows error: `'TaskStore' object is not subscriptable`
- Download tasks incorrectly marked as `"completed"` instead of `"failed"`

### Root Cause
- `app_config.py` aliased `download_statuses = task_store` (a `TaskStore` instance, not a dict)
- `youtube_utils.py` `download_channel_transcripts()` accepted a `status_dict` parameter and used dict syntax like `status_dict["errors"].append(...)`
- When called as `download_channel_transcripts(channel_url, task_store)`, the function received the `TaskStore` instance and tried to subscript it

### Fix
1. **`services/task_store.py`**: Added `__setitem__`, `__getitem__`, `__delitem__`, `__contains__` methods for backward compatibility
2. **`youtube_utils.py`**: Changed function signature to `download_channel_transcripts(channel_url, task_store, task_id)` and replaced all `status_dict["..."]` operations with `task_store.update_task(task_id, ...)` calls using a local `errors: list[str]` accumulator
3. **`blueprints/api.py`**: Updated both callers to pass `task_id` as the third argument
4. Added `raise` after storing errors so the caller properly marks tasks as `"failed"`

---

## Problem 4: "Invalid Date" on Status Page

### Symptoms
- Status page shows "Invalid Date" for Created and Updated fields

### Root Cause
- `/api/all-tasks` endpoint didn't include `created_at` and `updated_at` fields in its response

### Fix
- Added `created_at` and `updated_at` to the response dict in `api_all_tasks()` in `blueprints/api.py`

---

## Problem 5: `TypeError: Cannot read properties of undefined (reading 'length')`

### Symptoms
- Frontend crashes with: `Cannot read properties of undefined (reading 'length')` at `page.tsx:288`

### Root Cause
- `task.errors` could be `undefined` for tasks created before the fix
- `task.created_at` and `task.updated_at` could also be missing

### Fix
- Added null checks: `task.errors && task.errors.length > 0` and `task.created_at ? new Date(...) : "N/A"` in `frontend/src/app/status/page.tsx`

---

## Problem 6: `/api/*` 404 on Frontend

### Symptoms
- All API proxy routes returned 404

### Root Cause
- `API_BASE` in `frontend/src/lib/api.ts` used `process.env.NEXT_API_URL` which isn't exposed to the browser (needs `NEXT_PUBLIC_` prefix)
- No catch-all proxy route existed in Next.js

### Fix
1. Created catch-all route at `frontend/src/app/api/[...slug]/route.ts` that forwards all `/api/*` requests to the Flask backend
2. Changed `API_BASE` to `""` so all calls use relative paths through the proxy

---

## Problem 7: Video Refresh Fails for Single Video URLs

### Symptoms
- Refreshing a channel created from a single video URL fails with yt-dlp 404/400 errors
- Folder `-IGB6Avxwgo` had invalid playlist ID but was treated as a playlist

### Root Cause
- Refresh endpoint always constructed a playlist URL: `https://www.youtube.com/playlist?list={id}`
- No distinction between video and playlist content types was stored

### Fix
1. **`db/models.py`**: Added `content_type` column to `VideoFolder` (default `"playlist"`)
2. **`youtube_utils.py`**: Detects URL type (`youtube.com/watch` or `youtu.be/` → video), sets `content_type` on folders, passes it to `ensure_folder_association()`
3. **`blueprints/api.py`**: Refresh endpoint checks `content_type` and constructs the correct URL (`watch?v=` for video, `playlist?list=` for playlist)

---

## Problem 8: Chat Returns "No relevant content found"

### Symptoms
- Chat endpoint returns: "No relevant content found for this channel and data type."
- Video has transcript but chat can't find it

### Root Cause
1. Transcript embeddings weren't generated (vectorizer had bugs)
2. Chat SQL template for transcripts joined `summaries_v2` which doesn't contain transcript rows
3. Chat had no fallback when selected data type had no content

### Fix
1. **`run_vectorizers.py`**: Fixed schema-qualified table name handling (stripped `public.` prefix from `sql.Identifier`), fixed missing comma in SQL query
2. Added unique constraints on embedding tables for `ON CONFLICT` support
3. **`app_config.py`**: Added transcript-specific SQL template that joins `video_folders` and `videos` directly
4. **`blueprints/chat.py`**: Added transcript fallback when no content found for selected data type

---

## Files Changed

| File | Change |
|------|--------|
| `blueprints/main.py` | Added `GET /api/summaries/<id>` endpoint |
| `blueprints/api.py` | Added `created_at`/`updated_at` to all-tasks; fixed refresh to use `content_type` |
| `blueprints/chat.py` | Added transcript fallback for both channel and video chat |
| `db/models.py` | Added `content_type` column to `VideoFolder` |
| `services/task_store.py` | Added dict-like methods (`__setitem__`, etc.) |
| `youtube_utils.py` | Rewrote `download_channel_transcripts` to use `task_store`; added content_type detection |
| `app_config.py` | Added transcript-specific chat SQL template |
| `run_vectorizers.py` | Fixed schema-qualified table names and SQL query |
| `docker-compose.dev.yml` | Fixed `NEXT_API_URL` port |
| `frontend/src/app/api/[...slug]/route.ts` | Created catch-all API proxy |
| `frontend/src/app/status/page.tsx` | Added null checks for `errors`, `created_at`, `updated_at` |
| `frontend/src/lib/api.ts` | Changed `API_BASE` to `""` for relative paths |

---

## Verification

- All 229 unit tests pass
- TypeScript compiles cleanly
- Ruff lint/format clean
- Fresh video download completes successfully with correct `content_type`
- Chat with transcript data type returns meaningful answers
- Status page renders dates and errors without crashes
