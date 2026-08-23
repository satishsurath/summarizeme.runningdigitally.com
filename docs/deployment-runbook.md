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

## Production VM Deployment (LAN-only)

The production instance runs on a dedicated LAN-only Docker host (the
homelab personal-automation VM; internal documentation owns the host
identity, sizing, and backup lanes). No public routes, no Cloudflare
tunnel, no Cloudflare Access. Host-specific values (hostnames, IPs,
secrets) live only in the local `.env` — never in this repository.

Topology:

```
browser (LAN) -> frontend :3000 (Next.js)
              -> app      :8000 (Flask/gunicorn, direct API + SSE)
app -> db     : PostgreSQL 17 + pgvector  (named volume: pgdata)
app -> redis  : task store + rate limits  (named volume: redis-data, AOF)
app -> vLLM (external host): gen :8000, embed :8001
```

### Auth posture

The host is LAN-only and the app has no login endpoint. Production auth on
this host uses `DEV_AUTH_ENABLED=true` (single user `dev@localhost` with
admin role), mirroring the workstation development instance. Access is
bounded to the trusted LAN. Do not publish ports 3000/8000 beyond the LAN.

### Database and data persistence

- Image: `pgvector/pgvector:pg17` (plain PostgreSQL 17 + pgvector; the app
  does not use TimescaleDB features).
- Data lives in the named Docker volume `summarizeme_pgdata`
  (`/var/lib/docker/volumes/summarizeme_pgdata/_data`). It persists across
  container restarts, image rebuilds, `docker compose restart`, host
  reboots, and `docker compose down` (without `-v`).
- **Never run `docker compose down -v`** on this stack: it deletes the
  database and Redis data.
- `restart: unless-stopped` is set on all services and the host auto-starts
  Docker on boot, so the stack comes back after a reboot with its data
  intact.
- First-boot schema bootstrap is the one-shot `db-init` service (idempotent):
  `alembic upgrade head` + `run_vectorizers.py` (creates the pgvector
  extension + embedding tables; backfills embeddings when data exists).

### First-time deployment

Run on the target host as a user who can invoke Docker through `sudo`
(passwordless sudo; `sudo` prefix required when the user is not in the
`docker` group). Place the code in `<repo-dir>` (e.g. `/opt/summarizeme`).

```bash
# 1. Get the code onto the host (git clone with a registered key, or a
#    tar/clone transfer from a workstation).
cd <repo-dir>

# 2. Create the .env. Generate the secrets on the host:
FLASK_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
POSTGRES_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
cat > .env <<EOF
# Production — LAN-only host
DATABASE_URL=postgresql://summarizeme:${POSTGRES_PASSWORD}@db:5432/summarizeme
POSTGRES_USER=summarizeme
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=summarizeme

# vLLM endpoints — same values as the workstation development instance
VLLM_GEN_HOST=<vllm-host>
VLLM_GEN_PORT=8000
VLLM_GEN_API_KEY=local-noauth
VLLM_GEN_MODEL=nemo-qwen3.6-35b-a3b-nvfp4

VLLM_EMBED_HOST=<vllm-host>
VLLM_EMBED_PORT=8001
VLLM_EMBED_API_KEY=local-noauth
VLLM_EMBED_MODEL=nemo-nomic-embed-text-v1.5

REDIS_URL=redis://redis:6379/0
FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
JWT_SECRET_KEY=${FLASK_SECRET_KEY}
DEV_AUTH_ENABLED=true
# The frontend origin(s) as the browser sees them
CORS_ALLOWED_ORIGINS=http://<vm-host>:3000
NEXT_PUBLIC_FLASK_URL=http://<vm-host>:8000
BACKUP_DIR=/app/backups
BACKUP_RETENTION=30
EOF

# 3. Build and start
sudo docker compose -f docker-compose.prod.yml up -d --build

# 4. Bootstrap the schema (idempotent; re-run after deploys that include
#    migrations)
sudo docker compose -f docker-compose.prod.yml run --rm db-init
```

Notes: `<vm-host>` is this host's LAN name or IP as the browser reaches it
(list both comma-separated if users mix them). `<vllm-host>` is the LAN
address of the vLLM endpoints, the same value the workstation dev instance
uses. `CORS_ALLOWED_ORIGINS` must list the frontend origin because the
browser talks to `:8000` directly (SSE streaming).

### Verification

```bash
sudo docker compose -f docker-compose.prod.yml ps          # all services healthy
curl -s http://localhost:8000/health                      # {"status":"healthy"}
curl -s http://localhost:3000 -o /dev/null -w '%{http_code}\n'   # 200
curl -s http://localhost:8000/api/models                  # lists the vLLM gen+embed models

# persistence check: restart the db and confirm data + extensions survive
sudo docker compose -f docker-compose.prod.yml restart db
sudo docker compose -f docker-compose.prod.yml exec db \
  psql -U summarizeme -d summarizeme -tc "SELECT extname FROM pg_extension;"
# -> plpgsql, vector
```

End-to-end: open `http://<vm-host>:3000` in a LAN browser, download a
channel, run a summary (exercises generation), and ask a chat question
(exercises embeddings + pgvector similarity).

### Optional: seed from the workstation development database

```bash
# On the workstation:
docker exec summarizemerunningdigitallycom-db-1 \
  pg_dump -U summarizeme -d summarizeme --no-owner --no-privileges \
  | gzip > summarizeme-dev.sql.gz
# copy to the host, then on the host:
gunzip -c summarizeme-dev.sql.gz | \
  sudo docker compose -f docker-compose.prod.yml exec -T db \
  psql -U summarizeme -d summarizeme
# embedding tables come with the dump; re-running db-init backfills any gaps
sudo docker compose -f docker-compose.prod.yml run --rm db-init
```

### Daily backup

Logical dump from the `db` container (the app image has no `pg_dump`),
retention 14 days:

```bash
sudo mkdir -p /opt/summarizeme-backups
sudo tee /usr/local/bin/summarizeme-db-backup >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/summarizeme   # adjust to <repo-dir>
ts=$(date +%Y%m%d_%H%M%S)
out=/opt/summarizeme-backups/summarizeme_${ts}.sql.gz
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U summarizeme -d summarizeme --no-owner --no-privileges \
  | gzip > "$out"
ls -1t /opt/summarizeme-backups/*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f --
EOF
sudo chmod +x /usr/local/bin/summarizeme-db-backup

sudo tee /etc/systemd/system/summarizeme-db-backup.timer >/dev/null <<'EOF'
[Unit]
Description=Daily SummarizeMe database backup
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
EOF
sudo systemctl enable --now summarizeme-db-backup.timer
```

The host-level VM backup lane (see internal documentation) already covers
the whole guest including the Docker volume; the daily logical dump is the
fast, file-level recovery path for the database.

### Updates and rollback

```bash
# Update
cd <repo-dir>
git pull
sudo docker compose -f docker-compose.prod.yml build
sudo docker compose -f docker-compose.prod.yml up -d
sudo docker compose -f docker-compose.prod.yml run --rm db-init  # if migrations changed

# Rollback the app (DB volume is untouched)
git revert <commit>  # or git reset --hard <previous-commit>
sudo docker compose -f docker-compose.prod.yml build && sudo docker compose -f docker-compose.prod.yml up -d

# Restore a database backup
gunzip -c /opt/summarizeme-backups/summarizeme_<ts>.sql.gz | \
  sudo docker compose -f docker-compose.prod.yml exec -T db \
  psql -U summarizeme -d summarizeme --clean --if-exists
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
