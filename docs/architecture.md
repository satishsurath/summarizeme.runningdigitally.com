# SummarizeMe Architecture

## Overview
SummarizeMe is a YouTube video summarization and chat application that uses
vLLM for LLM generation and embeddings. It provides semantic search over
video content using PostgreSQL with pgvector.

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser                             │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (Flask)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SummarizeMe Application                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Blueprints │  │  Blueprints │  │      app_config.py      │  │
│  │  main.py    │  │   api.py    │  │  (config, logging,      │  │
│  │  (pages)    │  │  (REST API) │  │   SQL templates,        │  │
│  └─────────────┘  └─────────────┘  │   shared utilities)     │  │
│  ┌─────────────┐  ┌─────────────┐  └─────────────────────────┘  │
│  │  chat.py    │  │  admin.py   │                               │
│  │  (chat)     │  │  (admin)    │                               │
│  └─────────────┘  └─────────────┘                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              summarizer_v2.py                           │     │
│  │  • vllm_generate_chunk()  • vllm_embed_chunk()         │     │
│  │  • chunk_transcript()     • build_prompts_for_chunk()  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              youtube_utils.py                           │     │
│  │  • download_channel_transcripts()                       │     │
│  │  • get_channel_and_videos()                             │     │
│  └─────────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  PostgreSQL     │ │     Redis       │ │     vLLM        │
│ • videos        │ │ (configured, not yet used) │ │ • nemo-qwen3.6  │
│ • summaries_v2  │ │ • sessions      │ │   -35b-a3b-nvfp4│
│ • video_folders │ │                 │ │ • nemo-nomic    │
│ • embeddings    │ │                 │ │   -embed-text   │
│ • users         │ │                 │ └─────────────────┘
└─────────────────┘ └─────────────────┘
```

## Components

### Application Layer (Flask)

The application is organized into Flask blueprints for separation of concerns:

- **`blueprints/main.py`** — Web page routes (index, status, videos, chat pages)
- **`blueprints/api.py`** — REST API endpoints (channels, summaries, tasks)
- **`blueprints/chat.py`** — Chat endpoints (channel chat, video chat)
- **`blueprints/admin.py`** — Admin endpoints (settings, user management)

### Configuration (`app_config.py`)

Central configuration module that:
- Loads environment variables from `.env`
- Creates PostgreSQL engine and session factory
- Defines SQL templates for chat (whitelist-based)
- Configures structured logging (`shared_logger`)
- Exports shared utilities for blueprints
| `*_embedding` | Vector embeddings for semantic search (e.g., `videos_transcript_no_ts_embedding`) |
### Summarizer (`summarizer_v2.py`)

Core summarization and embedding module:
- `vllm_generate_chunk()` — Generates text via vLLM (with httpx fallback)
- `vllm_embed_chunk()` — Generates embeddings via vLLM
- `chunk_transcript()` — Splits transcripts into chunks
- `build_prompts_for_chunk()` — Builds prompts for summarization

### YouTube Utilities (`youtube_utils.py`)

YouTube content acquisition:
- `download_channel_transcripts()` — Downloads transcripts for channel videos
- `get_channel_and_videos()` — Fetches channel info and video list

### Database (PostgreSQL with pgvector)

| Table | Purpose |
|-------|---------|
| `videos` | Video metadata (id, title, upload_date, transcript) |
| `summaries_v2` | Generated summaries (concise, topics, takeaways) |
| `video_folders` | Channel-to-video associations |
| `users` | User accounts with roles (admin, member, reader) |
| `*_embedding` | Vector embeddings for semantic search (e.g., `videos_transcript_no_ts_embedding`) |

### vLLM Backend

Two separate vLLM instances:
- **Generation** (port 8000): `nemo-qwen3.6-35b-a3b-nvfp4`
- **Embeddings** (port 8001): `nemo-nomic-embed-text-v1.5`

### Redis

Used for:
- Task status storage (in-memory dict with Redis fallback)
- Session caching
- Future: rate limiting, distributed locks

## Data Flow

### Summarization Pipeline

```
YouTube Channel
       │
       ▼
┌─────────────────────┐
│ download_channel    │
│ _transcripts()      │
└─────────┬───────────┘
          │ (transcripts stored in videos.transcript_no_ts)
          ▼
┌─────────────────────┐
│ chunk_transcript()  │
└─────────┬───────────┘
          │ (chunks)
          ▼
┌─────────────────────┐
│ build_prompts_for   │
│ _chunk()            │
└─────────┬───────────┘
          │ (prompts)
          ▼
┌─────────────────────┐
│ vllm_generate_chunk │─────► vLLM gen endpoint
└─────────┬───────────┘
          │ (summaries)
          ▼
   SummariesV2 table
```

### Chat Pipeline

```
User Query
       │
       ▼
┌─────────────────────┐
│ vllm_embed_chunk()  │─────► vLLM embed endpoint
└─────────┬───────────┘
          │ (embedding vector)
          ▼
┌─────────────────────┐
│ Vector similarity   │
│ search in DB        │
└─────────┬───────────┘
          │ (relevant chunks)
          ▼
┌─────────────────────┐
│ vllm_generate_chunk │─────► vLLM gen endpoint
└─────────┬───────────┘
          │ (answer)
          ▼
     Response to user
```

### Embedding Backfill (`run_vectorizers.py`)

```
Database tables
       │
       ▼
┌─────────────────────┐
│ process_column()    │
└─────────┬───────────┘
          │ (text content)
          ▼
┌─────────────────────┐
│ split_into_chunks() │
└─────────┬───────────┘
          │ (chunks)
          ▼
┌─────────────────────┐
│ get_embedding()     │─────► vLLM embed endpoint
└─────────┬───────────┘
          │ (vectors)
          ▼
┌─────────────────────┐
│ upsert_embedding()  │
└─────────┬───────────┘
          │
          ▼
   *_embedding tables
```

## Security

- **SQL injection prevention:** Whitelist-based template selection, `psycopg2.sql.Identifier` for table/column quoting
- **Authentication:** Cloudflare Access in production, dev auth mode for local development
- **Role-based access:** Admin, member, reader roles with route decorators
- **Environment variables:** No hardcoded credentials
- **Structured logging:** Security events logged via `shared_logger`

## Deployment

### Development (`docker-compose.dev.yml`)
- Hot-reload enabled
- Port 5001 mapped to container 5000
- Host volume mount for code changes
- SQLite for tests, PostgreSQL for dev

### Production (`docker-compose.prod.yml`)
- Gunicorn 4 workers on port 8000
- Health checks on `/health`
- Resource limits (CPU, memory)
- Log rotation (json-file, 10m max, 3 files)
- Restart policies (unless-stopped)
- Volume persistence for PostgreSQL and Redis

## Monitoring

- **Health endpoint:** `GET /health` — returns 200 if app is running
- **Structured logging:** All logs via `shared_logger` with timestamps and levels
- **Docker health checks:** PostgreSQL, Redis, and app health checks
- **Log rotation:** Configured in docker-compose.prod.yml

## Backup

Use `backup_database.py` for automated backups:
```bash
python backup_database.py --compress --retention 30
```

Backups are stored in `./backups/` with timestamps and optional gzip compression.
