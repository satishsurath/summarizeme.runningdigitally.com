# Agent Operating Instructions

## CI/CD Quality Gate Policy

**Every `git commit` must be followed by pushing the branch and verifying all PR checks pass.**

If any check fails:
1. Read the failed check's logs (`gh run view <run_id> --log-failed` or `gh run view <run_id> -j <job_id> --log`)
2. Identify the failure cause (lint error, test failure, Docker build error)
3. Fix the issue in the source code
4. Run local verification before committing:
   - **Lint**: `ruff check . && ruff format --check .`
   - **Tests**: `DEV_AUTH_ENABLED=true pytest tests/ -q` (all must pass)
   - **Docker**: `docker build -t summarizeme:test .`
5. Commit the fix
6. Push and poll until all checks show `pass`

### Polling pattern
```bash
# Poll PR checks every 15s until all pass
for i in $(seq 1 8); do
  gh pr checks <NPR> 2>&1
  # Check: all three must show 'pass'
  sleep 15
done
```

### Common failure patterns
- **ruff check failures**: Run `ruff check --fix .` then `ruff format .`
- **ruff format failures**: Run `ruff format <files>`
- **Import order errors (I001)**: `ruff check --fix` handles these automatically
- **Unused imports (F401)**: `ruff check --fix` handles most
- **Unused variables (F841)**: May need manual fix (`ruff check --fix` only with `--unsafe-fixes`)
- **Line too long (E501)**: Break the line across multiple lines manually
- **Test failures**: Fix the source code, then verify locally before pushing
- **Docker build failures**: Check Dockerfile for syntax errors, missing dependencies

## Branch Strategy

- **`main`**: Production-ready code. Protected branch.
- **Feature branches**: Named descriptively (e.g., `dev-audit-transcript`).
- **PRs target `main`**: Create PRs with `gh pr create --base main --head <branch>`.
- **Merging**: Only merge when all checks pass and `gh pr view <N> --json mergeable` reports `MERGEABLE` with `mergeStateStatus: CLEAN`.

## Environment Notes

- **vLLM primary backend**: Two separate instances at `192.168.50.9` (port 8001 for embeddings, 8000 for generation).
- **API keys**: Never commit literal API keys. Use `${VLLM_*_API_KEY}` env var references in docker-compose and placeholders in `.env` files.
- **Local dev**: Runs on port 5001 (5000 blocked by macOS). Docker Compose: `docker compose -f docker-compose.dev.yml up -d`.
- **YouTube transcript wrapper**: Host-side HTTP wrappers on ports 9876 (playlist) and 9877 (transcript). Container accesses them via `host.docker.internal`.
- **Testing**: `DEV_AUTH_ENABLED=true pytest tests/ -q` (62 tests).

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask app, all routes, auth, vLLM config |
| `summarizer_v2.py` | Generation + embedding logic |
| `youtube_utils.py` | YouTube transcript download (wrapper-based) |
| `yt_dlp_wrapper.py` | Host-side playlist listing wrapper |
| `yt_dlp_transcript.py` | Host-side transcript download wrapper |
| `run_vectorizers.py` | PGAI vectorizer creation |
| `auth_utils.py` | Cloudflare Access JWT / dev-mode auth |
| `docker-compose.dev.yml` | Dev stack (DB + Redis + app) |
| `.github/workflows/pr-checks.yml` | PR quality checks (lint, tests, docker) |
