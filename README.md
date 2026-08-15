# SummarizeMe

SummarizeMe is a Flask application for downloading YouTube transcripts, producing
stored summaries, and chatting with individual videos or channel collections. It
uses PostgreSQL for application data and can use separate OpenAI-compatible vLLM
endpoints for embeddings and generation. Ollama is the fallback when vLLM is not
configured.

## Repository map

- `app.py`: Flask routes for channels, videos, summaries, chat, and administration.
- `db/models.py`: SQLAlchemy models for videos, folders, summaries, sync jobs, and
  users.
- `youtube_utils.py`: YouTube playlist and transcript acquisition.
- `summarizer_v2.py`: transcript chunking, prompts, generation, and embeddings.
- `auth_utils.py`: Cloudflare Access JWT and explicit development-auth behavior.
- `run_vectorizers.py`: PostgreSQL embedding backfill.
- `init_db.py`: creates SQLAlchemy tables.
- `docker-compose.dev.yml`: local PostgreSQL, Redis, vLLM, and application services.

Repository-level assistant instructions are in [AGENTS.md](AGENTS.md).

## Prerequisites

- Python 3.12
- PostgreSQL for runtime use; pgvector/PGAI are required only for the vectorized
  chat path.
- Docker and Docker Compose for the containerized development stack.
- A vLLM-compatible embedding and generation service, or an Ollama service.

Copy the committed example rather than creating a secret-bearing file from memory:

```bash
cp env.example .env
```

Set `DATABASE_URL` and, when using vLLM, `VLLM_EMBED_HOST`,
`VLLM_EMBED_PORT`, `VLLM_GEN_HOST`, and `VLLM_GEN_PORT`. Keep API keys only in
untracked environment files or the runtime secret store.

## Local Python environment

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

The project pins its development target to Python 3.12 in `.python-version` and
configures Pyright through `pyproject.toml`.

## Database and vector setup

Create the relational schema after configuring a disposable or local database:

```bash
.venv/bin/python init_db.py
```

`run_vectorizers.py` writes embeddings to PostgreSQL and needs both a compatible
database and a reachable embedding endpoint:

```bash
.venv/bin/python run_vectorizers.py
```

Do not run either command against production unless that is the explicit task.

## Containers

The development Compose definition includes PostgreSQL, Redis, vLLM embedding and
generation services, and the Flask application. Starting the full stack requires
the appropriate GPU runtime and any model-download credentials:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Inspect the Compose file before selectively starting services: the database port,
model images, and initialization scripts are part of the runtime contract.

## Validation

Run the narrowest relevant check first:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest tests/unit/ -q
.venv/bin/pyright
```

By default, tests use a temporary SQLite database. To test the same suite against
a disposable PostgreSQL database, supply `TEST_DATABASE_URL`; this is intentionally
separate from the normal `DATABASE_URL` to avoid pointing tests at a developer or
production database.

```bash
TEST_DATABASE_URL='postgresql://summarizeme:summarizeme_pass@localhost:5432/summarizeme_test' \
  .venv/bin/pytest tests/ -q
```

PGAI tests additionally require the `ai` extension and a reachable embedding
endpoint. A skipped or non-blocking PGAI check is not proof that the production
chat path works.

Install local hooks after creating the environment:

```bash
.venv/bin/pre-commit install --hook-type pre-push
```

## Safety and operating notes

- `DEV_AUTH_ENABLED=true` is an explicit local-development mode; do not use it as
  production authentication.
- Mocked model, YouTube, or authentication tests validate only the contract under
  test. Verify live integrations separately when a change touches them.
- `app.py` currently contains several runtime boundaries. For cross-cutting
  changes, trace callers and inspect the relevant source rather than relying on a
  route name or graph edge alone.
