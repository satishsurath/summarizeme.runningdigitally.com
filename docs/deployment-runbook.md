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

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `VLLM_GEN_HOST` | Yes | vLLM generation host |
| `VLLM_GEN_PORT` | Yes | vLLM generation port (default 8000) |
| `VLLM_EMBED_HOST` | Yes | vLLM embedding host |
| `VLLM_EMBED_PORT` | Yes | vLLM embedding port (default 8001) |
| `REDIS_URL` | Yes | Redis connection string |
| `SECRET_KEY` | Yes | Flask secret key (generate with `secrets.token_hex(32)`) |
| `DEV_AUTH_ENABLED` | No | Set to `false` in production |
| `POSTGRES_USER` | No | PostgreSQL username (default: summarizeme) |
| `POSTGRES_PASSWORD` | No | PostgreSQL password |
| `POSTGRES_DB` | No | PostgreSQL database name (default: summarizeme) |

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
# Create backup
docker compose -f docker-compose.prod.yml exec app python backup_database.py --compress

# Restore from backup
docker compose -f docker-compose.prod.yml exec app bash -c "gunzip -c /backups/summarizeme_*.sql.gz | psql -U summarizeme -d summarizeme"
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
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]
```

To scale:
1. Increase worker count in `Dockerfile` or use environment variable
2. Increase resource limits in `docker-compose.prod.yml`
3. Use horizontal scaling with a load balancer

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

## Rollback

```bash
# Stop current deployment
docker compose -f docker-compose.prod.yml down

# Start previous image
docker compose -f docker-compose.prod.yml up -d

# Verify
curl http://localhost:8000/health
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
