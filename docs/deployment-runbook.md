# Deployment Runbook

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL/TimescaleDB instance (managed or self-hosted)
- Redis instance
- vLLM endpoints for generation (port 8000) and embeddings (port 8001)
- `.env` file with production secrets

## Quick Start

```bash
# 1. Copy and edit environment variables
cp .env.example .env
# Edit .env with production values

# 2. Build and start
docker compose -f docker-compose.prod.yml up -d --build

# 3. Verify
curl http://localhost:8000/health
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `VLLM_GEN_HOST` | Yes | — | vLLM generation host |
| `VLLM_GEN_PORT` | No | `8000` | vLLM generation port |
| `VLLM_EMBED_HOST` | Yes | — | vLLM embedding host |
| `VLLM_EMBED_PORT` | No | `8001` | vLLM embedding port |
| `REDIS_URL` | Yes | — | Redis connection string |
| `SECRET_KEY` | Yes | — | Flask secret key (generate with `secrets.token_hex(32)`) |
| `DEV_AUTH_ENABLED` | No | `false` | Enable development auth mode |
| `VLLM_EMBED_MODEL` | No | `nemo-nomic-embed-text-v1.5` | Embedding model name |
| `VLLM_GEN_API_KEY` | No | — | API key for vLLM generation endpoint |
| `VLLM_EMBED_API_KEY` | No | — | API key for vLLM embedding endpoint |
| `FLASK_ENV` | No | `production` | Flask environment |
| `POSTGRES_USER` | No | `summarizeme` | PostgreSQL username |
| `POSTGRES_PASSWORD` | No | — | PostgreSQL password |
| `POSTGRES_DB` | No | `summarizeme` | PostgreSQL database name |

## Database Setup

### Initial Setup

```bash
# Connect to the database
docker compose -f docker-compose.prod.yml exec db psql -U summarizeme -d summarizeme

# Run migrations
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

### Backup

```bash
# Create backup (compressed)
docker compose -f docker-compose.prod.yml exec app python backup_database.py --compress

# Restore from backup
docker compose -f docker-compose.prod.yml cp backups/summarizeme_YYYYMMDD_HHMMSS.sql app:/app/backups/
docker compose -f docker-compose.prod.yml exec db psql -U ${POSTGRES_USER:-summarizeme} -d ${POSTGRES_DB:-summarizeme} < /app/backups/summarizeme_YYYYMMDD_HHMMSS.sql
```

## Health Checks

The application exposes a health endpoint at `GET /health`.

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

Docker Compose health checks:
- **App:** `curl -f http://localhost:8000/health` every 30s
- **PostgreSQL:** `pg_isready` every 10s
- **Redis:** `redis-cli ping` every 10s

## Scaling

The production Dockerfile uses Gunicorn with 4 workers:

```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "wsgi:app"]
```

To scale:
1. Increase worker count in `Dockerfile` or use environment variable
2. Increase resource limits in `docker-compose.prod.yml`

## Rollback

```bash
# Tag production image before deploy: docker tag summarizeme:latest summarizeme:v1.0.0
# On rollback, specify the previous tag:
docker compose -f docker-compose.prod.yml up -d --no-deps app  # restart with current image
# Or revert to previous tag by editing docker-compose.prod.yml or .env
```

## Monitoring

### Logs

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f app

# View last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 app
```

### Resource Usage

```bash
# View resource usage
docker stats

# View specific container
docker stats app
```

## Troubleshooting

### App won't start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs app

# Check environment variables
docker compose -f docker-compose.prod.yml exec app env | grep DATABASE

# Test database connection
docker compose -f docker-compose.prod.yml exec app python -c "from app_config import SessionLocal; print('OK')"
```

### Database connection failed

```bash
# Check database is running
docker compose -f docker-compose.prod.yml ps db

# Test connection
docker compose -f docker-compose.prod.yml exec db pg_isready -U summarizeme -d summarizeme

# Check database exists
docker compose -f docker-compose.prod.yml exec db psql -U summarizeme -c "\l" | grep summarizeme
```

### vLLM endpoint unreachable

```bash
# Test vLLM generation endpoint
curl http://<VLLM_GEN_HOST>:<VLLM_GEN_PORT>/v1/models

# Test vLLM embedding endpoint
curl http://<VLLM_EMBED_HOST>:<VLLM_EMBED_PORT>/v1/models
```

## Maintenance

### Update dependencies

```bash
# Update requirements
pip install -r requirements.txt --upgrade
pip freeze > requirements.txt

# Rebuild
docker compose -f docker-compose.prod.yml build app
docker compose -f docker-compose.prod.yml up -d app
```

### Database migration

```bash
# Create migration
docker compose -f docker-compose.prod.yml exec app alembic revision --autogenerate -m "description"

# Apply migration
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

# Rollback migration
docker compose -f docker-compose.prod.yml exec app alembic downgrade -1
```

### Backup schedule

Add to crontab for daily backups:

```bash
0 2 * * * cd /path/to/app && docker compose -f docker-compose.prod.yml exec app python backup_database.py --compress --retention 30 >> /var/log/backup.log 2>&1
```
