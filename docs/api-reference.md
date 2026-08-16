# SummarizeMe API Reference

## Overview

SummarizeMe exposes REST API endpoints for channel management, summarization,
chat, and vLLM model listing. All API endpoints (except health) require
authentication when `DEV_AUTH_ENABLED` is false.

## Authentication

Admin endpoints require the `admin` role. The `get_current_user` function
(resolved at runtime from `app.py`) returns `(email, role)` from the JWT or
dev auth cookie.

## Endpoints

### Health

```
GET /health
```

Returns `200 OK` with `{"status": "healthy"}` when the application is running.
Used by Docker health checks.

### Channels

```
GET /api/channels
```

List all channels with pagination.

**Query Parameters:**
- `page` (int, default 1): Page number
- `page_size` (int, default 20): Items per page (max 100)
- `sort_by` (str, default "title"): Sort field (`title`, `date`)
- `sort_order` (str, default "asc"): Sort order (`asc`, `desc`)

**Response:**
```json
{
  "channels": [{"id": 1, "folder_name": "test", ...}],
  "total": 10,
  "page": 1,
  "page_size": 20
}
```

---

```
POST /api/channels
```

Rename a channel. Requires `admin` role.

**Body:**
```json
{"new_name": "new_channel_name"}
```

---

```
POST /api/channels/refresh
```

Refresh a channel's video list and transcripts. Requires `admin` role.

**Body:**
```json
{"channel_name": "test_channel"}
```

**Response:**
```json
{"status": "initiated", "task_id": "dl_abc123"}
```

---

```
POST /api/channels/delete
```

Delete a channel and its folder associations. Requires `admin` role.

**Body:**
```json
{"channel_name": "test_channel"}
```

### Videos

```
GET /api/videos/<channel_name>
```

List videos for a channel with pagination.

**Query Parameters:**
- `page` (int, default 1): Page number
- `page_size` (int, default 20): Items per page (max 100)
- `sort_by` (str, default "title"): Sort field (`title`, `date`)
- `sort_order` (str, default "asc"): Sort order (`asc`, `desc`)
- `search` (str, optional): Search title

**Response:**
```json
{
  "videos": [{"video_id": "abc", "title": "...", ...}],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

### Summarization

```
POST /api/summarize_v2
```

Generate summaries for channel videos. Requires `admin` role.

**Body:**
```json
{
  "channel_name": "test_channel",
  "video_ids": ["vid1", "vid2"],
  "model": "nemo-qwen3.6-35b-a3b-nvfp4"
}
```

**Response:**
```json
{"status": "initiated", "task_id": "summ_v2_abc123"}
```

---

```
GET /api/summarize_v2/status/<task_id>
```

Get summarization task status.

**Response:**
```json
{
  "status": "completed|in_progress|failed",
  "processed": 5,
  "total": 10,
  "errors": []
}
```

### Chat

```
POST /api/chat-channel/<channel_name>
```

Chat with a channel's combined content.

**Body:**
```json
{
  "query": "What is this about?",
  "data_type": "comprehensive_notes",
  "model_name": "nemo-qwen3.6-35b-a3b-nvfp4"
}
```

**data_type values:**
- `comprehensive_notes` (default)
- `concise_summary`
- `key_topics`
- `important_takeaways`
- `transcript`

**Response:**
```json
{
  "answer": "<p>HTML answer...</p>",
  "videos_used": [{"video_id": "...", "title": "..."}]
}
```

---

```
POST /api/chat-video/<video_id>
```

Chat with a single video's content.

**Body:**
```json
{
  "query": "What is this about?",
  "data_type": "comprehensive_notes",
  "model_name": "nemo-qwen3.6-35b-a3b-nvfp4"
}
```

### Tasks

```
GET /api/all-tasks
```

List all active tasks (downloads, summarizations, refreshes).

**Response:**
```json
[
  {
    "task_id": "dl_abc123",
    "status": "in_progress",
    "processed": 5,
    "total": 10,
    "errors": []
  }
]
```

### vLLM

```
GET /api/vllm/models
```

List available models from vLLM backends.

**Response:**
```json
{
  "generation": ["model_name"],
  "embedding": ["model_name"]
}
```

## Error Responses

All endpoints return JSON error responses:

```json
{
  "status": "error",
  "message": "Description of the error"
}
```

Common status codes:
- `400` — Bad request (missing params, invalid input)
- `403` — Forbidden (authentication/authorization failure)
- `404` — Not found (resource doesn't exist)
- `500` — Internal server error
