# Environment Variables Reference

## Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string (`postgresql://user:pass@host:port/db`) |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string for the task store. Optional — the task store falls back to in-memory storage when Redis is unreachable |
| `FLASK_SECRET_KEY` | Recommended | random per start | Flask secret key for sessions and CSRF. Set a stable value in production |
| `JWT_SECRET_KEY` | No | falls back to `FLASK_SECRET_KEY` | Secret for issuing/validating JWT auth tokens. Must be set (directly or via `FLASK_SECRET_KEY`) when `FLASK_ENV` is not `development` |
| `FLASK_ENV` | No | `production` | Flask environment (`development` or `production`) |
| `DEV_AUTH_ENABLED` | No | `false` | Enable development auth mode (do NOT use in production) |
| `CORS_ALLOWED_ORIGINS` | No | — | Comma-separated list of extra browser origins allowed by the CORS middleware (e.g. the frontend origin). Dev origins are always allowed |

## Cloudflare Access

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLOUDFLARE_JWKS_URL` | No | — | JWKS endpoint used to verify Cloudflare Access JWTs. When unset, Cloudflare verification is disabled and only dev auth (if enabled) works |
| `CLOUDFLARE_ISSUER` | No | — | Expected `iss` claim of the Cloudflare Access token |
| `CLOUDFLARE_AUD_TAG` | No | — | Expected `aud` claim of the Cloudflare Access token |

## vLLM Generation

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VLLM_GEN_HOST` | Yes | `localhost` | vLLM generation service host |
| `VLLM_GEN_PORT` | No | `8000` | vLLM generation service port |
| `VLLM_GEN_API_KEY` | No | `not-needed` | API key for the vLLM generation endpoint |
| `VLLM_GEN_MODEL` | No | `nemo-qwen3.6-35b-a3b-nvfp4` | Default generation model name |

## vLLM Embeddings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VLLM_EMBED_HOST` | Yes | `localhost` | vLLM embedding service host |
| `VLLM_EMBED_PORT` | No | `8001` | vLLM embedding service port |
| `VLLM_EMBED_API_KEY` | No | falls back to `VLLM_GEN_API_KEY` | API key for the vLLM embedding endpoint |
| `VLLM_EMBED_MODEL` | No | `nemo-nomic-embed-text-v1.5` | Embedding model name |

## Testing

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TEST_DATABASE_URL` | No | temp SQLite | Database used by the test suite. Set to a disposable PostgreSQL URL to run the integration tests against a real database (never the dev database) |

## PostgreSQL (dev compose)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | No | `summarizeme` | PostgreSQL username |
| `POSTGRES_PASSWORD` | No | — | PostgreSQL password (sensitive) |
| `POSTGRES_DB` | No | `summarizeme` | PostgreSQL database name |

## Backup

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BACKUP_DIR` | No | `./backups` | Directory for database backups |
| `BACKUP_RETENTION` | No | `30` | Days to retain backups |

## Notes

- **Never commit `.env` files** to version control
- Use `docker compose` secrets or a secret manager for production
- Generate `FLASK_SECRET_KEY` / `JWT_SECRET_KEY` with: `python -c "import secrets; print(secrets.token_hex(32))"`
- All vLLM endpoints must be reachable from the application container
