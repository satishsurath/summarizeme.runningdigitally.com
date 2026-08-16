# Phase 1 Planning — Maturity Assessment Remediation

**Date:** 2026-08-15
**Branch:** dev-phase1-maturity
**Source:** .omp/maturity-assessments/2026-08-15/consolidated-maturity-assessment.md

## Phase 1: Blockers (5 tasks)

### Task 1 — Fix DATABASE_URL crash-on-import (S, order 1)
- **Root cause:** `app.py` line 36 accesses `os.environ["DATABASE_URL"]` before `load_dotenv()` on line 48 → KeyError on import when .env is the only source
- **Fix:** Move `load_dotenv()` to top of app.py, or use `os.getenv()` with fallback
- **Dependencies:** None
- **Risk:** Low — straightforward fix

### Task 3 — Production Dockerfile (S, order 2, parallel with Task 1)
- **Current state:** Existing Dockerfile is minimal but functional
- **Needs:** Non-root user, HEALTHCHECK route, multi-stage refinement
- **Dependencies:** Task 1 (needs /health route in app.py)
- **Risk:** Low — additive changes

### Task 4 — Alembic migrations (M, order 3, depends on Task 1)
- **Current state:** 5 clean SQLAlchemy models in db/models.py
- **Needs:** Alembic setup, autogenerate initial migration, idempotent for existing prod DBs
- **Dependencies:** Task 1 (app.py config changes)
- **Risk:** Medium — existing prod DBs already have `original_playlist_id` from update_db.py

### Task 2 — Add missing route tests (M, order 4, depends on Task 1)
- **Current state:** 14 untested routes (chat, channel CRUD, admin)
- **Needs:** Tests for all untested routes, per-test DB isolation, background thread handling
- **Dependencies:** Task 1 (app.py config changes affect test fixtures)
- **Risk:** Medium — in-memory status dicts leak between tests

### Task 5 — Structured logging (M, order 5, depends on Task 1)
- **Current state:** 18+ print() statements across 6 files
- **Needs:** Replace print() with logging, add request IDs via @app.before_request, handle background thread context
- **Dependencies:** Task 1 (app.py changes)
- **Risk:** Medium — background threads won't inherit request context

## Dependency Graph

```
Task 1 ──→ Tasks 2, 3, 4, 5 (all import app)
Task 3 ──→ standalone (can run in parallel with Task 1)
```

## Recommended Execution Order

1. **Task 1** (DATABASE_URL fix) — no deps, S effort
2. **Task 3** (Production Dockerfile) — can run parallel with Task 1, S effort
3. **Task 4** (Alembic) — depends on Task 1, M effort
4. **Task 2** (Route tests) — depends on Task 1, M effort
5. **Task 5** (Structured logging) — depends on Task 1, M effort
