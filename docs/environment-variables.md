# Environment Variables Reference

## Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string (`postgresql://user:pass@host:port/db`) |
| `REDIS_URL` | Yes | — | Redis connection string (`redis://host:port/db`) |
| `SECRET_KEY` | Yes | — | Flask secret key for sessions and CSRF |
| `FLASK_ENV` | No | `production` | Flask environment (`development` or `production`) |
| `DEV_AUTH_ENABLED` | No | `false` | Enable development auth mode (do NOT use in production) |

## vLLM Generation

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VLLM_GEN_HOST` | Yes | — | vLLM generation service host |
| `VLLM_GEN_PORT` | No | `8000` | vLLM generation service port |
| `VLLM_GEN_API_KEY` | No | — | API key for vLLM generation endpoint |

## vLLM Embeddings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VLLM_EMBED_HOST` | Yes | — | vLLM embedding service host |
| `VLLM_EMBED_PORT` | No | `8001` | vLLM embedding service port |
| `VLLM_EMBED_API_KEY` | No | — | API key for vLLM embedding endpoint |
| `VLLM_EMBED_MODEL` | No | `nemo-nomic-embed-text-v1.5` | Embedding model name |

## PostgreSQL

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | No | `summarizeme` | PostgreSQL username |
| `POSTGRES_PASSWORD` | No | `summarizeme_pass` | PostgreSQL password |
| `POSTGRES_DB` | No | `summarizeme` | PostgreSQL database name |

## Backup

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BACKUP_DIR` | No | `./backups` | Directory for database backups |
| `BACKUP_RETENTION` | No | `30` | Days to retain backups |

## Notes

- **Never commit `.env` files** to version control
- Use `docker compose` secrets or a secret manager for production
- Generate `SECRET_KEY` with: `python -c "import secrets; print(secrets.token_hex(32))"`
- All vLLM endpoints must be reachable from the application container
