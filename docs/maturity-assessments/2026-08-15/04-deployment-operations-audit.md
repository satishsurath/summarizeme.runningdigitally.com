# Deployment & Operations Audit — SummarizeMe

**Date:** 2026-08-15
**Agent:** OpsAudit

## 1. CI/CD Pipeline

### Critical
**C1** `.github/workflows/main_summarize-me.yml:29` — Image tagged `:latest` only. No SHA digest pinning or versioned tags. Non-reproducible deploys.

**C2** `.github/workflows/main_summarize-me.yml:37-42` — Deploy step runs `docker stop` → `docker rm` → `docker run` sequentially. No health-check gate between stop and run. If the new container fails, the service is offline with no automatic recovery.

**C3** `.github/workflows/main_summarize-me.yml:21` — Uses `secrets.CR_PAT` for GHCR login. Legacy naming convention; GitHub now provides `GITHUB_TOKEN` automatically.

### Major
**M1** `.github/workflows/main_summarize-me.yml:29` — `docker build` uses no BuildKit features: no `--cache-from`, no `--load`, no multi-platform build.

**M2** `.github/workflows/main_summarize-me.yml:29` — Production deploy job skips Dockerfile validation. The `pr-checks.yml` has a `docker-build` job but the production deploy job does not.

**M3** `.github/workflows/main_summarize-me.yml:31` — `docker build` does not pass any build args or secrets.

### Minor
**N1** `.github/workflows/pr-checks.yml:3` — `concurrency` group uses `${{ github.ref }}` which includes `refs/heads/` prefix.

**N2** `.github/workflows/pr-checks.yml:56` — Lint step installs ruff fresh per run. No pip cache.

## 2. Docker Best Practices

### Critical
**C4** `Dockerfile.dev:20` — Development Dockerfile runs `flask run` directly (not gunicorn). Dev and prod use different WSGI servers.

**C5** `Dockerfile:11` — `COPY . /app` copies all app code. Production Dockerfile has no `.dockerignore` of its own.

**C6** `Dockerfile` — No non-root user. Container runs as `root` by default.

**C7** `Dockerfile:7` — `pip install --no-cache-dir -r requirements.txt` installs from source with no `pip` version pin or `--constraint` file.

### Major
**M4** `Dockerfile.dev:1` — No multi-stage build. Dev deps in final image.

**M5** `docker-compose.dev.yml:4-7` — Hardcoded database credentials in compose file.

**M6** `docker-compose.dev.yml:29,53` — vLLM images use `:latest` tag. No version pinning.

**M7** `docker-compose.dev.yml` — No `restart` policy on any service.

**M8** `docker-compose.dev.yml:35,59` — `HUGGING_FACE_HUB_TOKEN` may be unset, causing model download failures.

### Minor
**N3** `Dockerfile:5` — No `ENV PYTHONDONTWRITEBYTECODE=1` or `ENV PYTHONUNBUFFERED=1`.

**N4** `docker-compose.dev.yml:14` — Redis healthcheck has no `start_period`.

**N5** `Dockerfile:13` — `EXPOSE 8000` is informational only.

**N6** `Dockerfile` — No `COPY --chown` for the app directory.

## 3. Dependency Management

### Critical
**C7** `requirements.txt:47` — `tiktoken==0.8.0` is pinned but `openai>=1.0.0` is a range constraint.

**C8** `requirements.txt:49` — `PyJWT` has **no version constraint at all**. Security risk.

### Major
**M9** `requirements.txt` — No `pip-tools` lockfile. Direct `requirements.txt` with mixed pinning is fragile.

**M10** `requirements-dev.txt` — `pytest-cov>=6.0` and `pytest-mock>=3.14` use range constraints.

**M11** `requirements-dev.txt` — `httpx==0.27.2` is pinned in dev and also in `requirements.txt:16`.

### Minor
**N7** `pyproject.toml` — No `[project]` metadata.

**N8** `.python-version` — No enforcement tool (pyenv/asdf) in CI.

## 4. Pre-commit & Linting

### Critical
**C9** `.pre-commit-config.yaml:19-20` — `pytest-check` runs only on `pre-push`. `pre-commit run --all-files` does NOT exercise tests.

### Major
**M12** `.pre-commit-config.yaml:12-13` — Ruff hooks use `--fix` auto-fixes silently on every commit.

**M13** `.pre-commit-config.yaml` — No `mypy` or `pyright` integration in pre-commit.

### Minor
**N9** `.pre-commit-config.yaml:16` — `language: system` for pytest uses PATH Python.

**N10** `.pre-commit-config.yaml` — No `end-of-file-fixer` or `trailing-whitespace` hooks.

## 5. Environment Management

### Critical
**C10** `env.example:7` — Default `DATABASE_URL` contains literal password `password`. Risk of accidental commit.

**C11** `README.md:34` — README references `cp env.example .env` but two example files exist (`env.example` and `.env.vllm.example`). Ambiguity.

### Major
**M15** `docker-compose.dev.yml:6` — `POSTGRES_PASSWORD: summarizeme_pass` is hardcoded.

**M16** `docker-compose.dev.yml:35,59` — `HUGGING_FACE_HUB_TOKEN` may be unset.

**M17** `.github/workflows/pr-checks.yml:41,95` — CI test services use hardcoded passwords.

**M18** `.github/workflows/main_summarize-me.yml:41` — Deploy uses host-specific path `/home/satsur/.env`. Not portable.

### Minor
**N11** `env.example` — No `CLOUDFLARE_*` variables documented.

**N12** `env.example` — No `REDIS_URL` documented.

## 6. Security Practices

### Critical
**C12** `docker-compose.dev.yml:6` — Default PostgreSQL password `summarizeme_pass` is trivially guessable.

**C13** `Dockerfile` — No container image security scanning in CI or build pipeline.

### Major
**M19** `.github/workflows/main_summarize-me.yml:41` — Deploy passes `--env-file=/home/satsur/.env` with production secrets. Not portable.

**M20** `Dockerfile` — No `HEALTHCHECK` directive.

**M21** `docker-compose.dev.yml` — No resource limits (memory/CPU) on any service.

### Minor
**N13** — No `--no-install-recommends` in pip install.

**N14** — No `COPY --chown` for app directory.

**N15** — No `security_opt` or `read_only` settings on any service.

## Summary Table

| Severity | Count | Key Themes |
|----------|-------|------------|
| Critical | 13 | No versioned image tags, no zero-downtime deploy, no non-root user, unversioned deps (PyJWT), hardcoded passwords, no security scanning, no HEALTHCHECK |
| Major | 12 | No multi-stage dev build, latest image tags, no pip-tools, no type-checking pre-commit, host-specific deploy paths, no resource limits |
| Minor | 15 | Missing env var docs, no resource limits, missing file-cleaner hooks, no security_opt, no PYTHONUNBUFFERED |
