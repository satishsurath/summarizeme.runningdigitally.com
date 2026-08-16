# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `docker-compose.prod.yml` — production Docker Compose with health checks, restart policies, resource limits
- `backup_database.py` — database backup utility with compression, retention, and dry-run support
- `.env.example` — production environment variable template with documentation
- `CONTRIBUTING.md` — contribution guidelines
- `SECURITY.md` — security vulnerability reporting policy
- `docs/architecture.md` — system architecture documentation
- `LICENSE` — MIT License

### Changed
- [Add future changes here]

### Fixed
- [Add future fixes here]

## [0.2.0] - 2026-08-16

### Added
- vLLM-only architecture (complete Ollama removal)
- Chat embedding pipeline with proper vector cast and SQL templates
- `run_vectorizers.py` for embedding backfill with UNIQUE constraints
- youtu.be URL support for single video downloads
- Database persistence via host path mount (`./.data/postgres`)
  - Problem tickets in `docs/problem-tickets/`
- PR code review cycle instructions in `AGENTS.md`
- Structured logging via `shared_logger`
- Alembic migrations setup with initial schema migration

### Changed
- Split `app.py` into Flask blueprints (`blueprints/main.py`, `api.py`, `chat.py`, `admin.py`)
- Created `app_config.py` to break circular imports
- Pinned dependencies via pip-tools (`requirements.in` → `pip-compile`)
- Created `.dockerignore` for clean Docker builds
- Fixed all bare `except Exception` with specific exception types
- Replaced deprecated `datetime.UTC` with `datetime.timezone.utc`
- Used `uuid.uuid4()` for task IDs (collision prevention)
- Added `psycopg2.sql.Identifier` for SQL injection prevention
- Added retry with exponential backoff for vLLM failures
- Added empty-query validation in chat endpoints
- Added whitelist validation for SQL view names

### Fixed
- Chat embedding 404 (wrong vLLM URL and model name)
- Qwen3.6 reasoning content extraction
- Single video download youtu.be format detection
- Database not persistent on Docker rebuild
- Task ID collision in background threads
- Broken chunk boundary calculation in vectorizers
- Stale `vllm_cache` volume in docker-compose.dev.yml

### Removed
- All Ollama SDK dependencies and references
- OLLAMA_URL and _REMOTE_OLLAMA_HOST environment variables
- ollama package from requirements

## [0.1.0] - 2026-08-01

### Added
- Initial release of SummarizeMe
- YouTube video summarization with multiple models
- Chat functionality with RAG over video content
- PostgreSQL/pgvector for semantic search
- Docker Compose development environment
- Basic test suite
