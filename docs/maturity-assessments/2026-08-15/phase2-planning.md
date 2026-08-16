# Phase 2 Planning — Stability Improvements

**Date:** 2026-08-15
**Source:** .omp/maturity-assessments/2026-08-15/consolidated-maturity-assessment.md

## Phase 2: Stability (2-3 weeks)

### Task 6 — Persist task status (M)
- **Current state:** `download_statuses` and `summarize_v2_statuses` are in-memory dicts (app.py lines 90-91)
- **Needs:** Create `task_statuses` DB table, migrate all status reads/writes to DB
- **Dependencies:** None (can be done in parallel with other tasks)
- **Risk:** Medium — requires DB migration, all status endpoints need update

### Task 7 — Split app.py into blueprints (L)
- **Current state:** Single 1100+ line app.py with all routes
- **Needs:** Create blueprint structure:
  - `blueprints/main.py` — index, status, health, videos page, summaries view, transcript view
  - `blueprints/api.py` — all /api/* routes
  - `blueprints/chat.py` — chat-channel, chat-video routes
  - `blueprints/admin.py` — admin-settings, admin-update-role, admin-add-user
  - `blueprints/auth.py` — require_role decorator, auth helpers
- **Dependencies:** None (mechanical refactoring)
- **Risk:** Low — no behavior change, all tests should pass

### Task 8 — Add type hints (M)
- **Current state:** No type hints in app.py, summarizer_v2.py, youtube_utils.py
- **Needs:** Add type hints to core routes, run pyright in CI, fix errors
- **Dependencies:** Task 7 (blueprints make type annotations cleaner)
- **Risk:** Medium — may require fixing type errors in dependencies

### Task 9 — Fix bare except Exception (S)
- **Current state:** 16 bare `except Exception` across 4 files
- **Needs:** Replace with specific exception types:
  - `requests.exceptions.RequestException` for HTTP calls
  - `sqlite3.Error` / `sqlalchemy.exc.SQLAlchemyError` for DB
  - `json.JSONDecodeError` for JSON parsing
  - `ValueError` / `KeyError` for dict access
- **Dependencies:** None
- **Risk:** Low — targeted replacements

### Task 10 — Add .dockerignore (S)
- **Current state:** No .dockerignore file
- **Needs:** Exclude `.env*`, `.venv`, `__pycache__`, `.git`, `*.pyc`, `node_modules`
- **Dependencies:** None
- **Risk:** Low — additive change

### Task 11 — Pin all dependencies (M)
- **Current state:** requirements.txt has some pinned versions, some not
- **Needs:** Adopt pip-tools:
  - Create `requirements.in` with top-level deps
  - Run `pip-compile` to generate pinned `requirements.txt`
  - Add `pip-compile` to CI
- **Dependencies:** None
- **Risk:** Medium — may need to adjust for transitive deps

## Dependency Graph

```
Task 10 (dockerignore) ──→ standalone
Task 11 (pin deps) ──→ standalone
Task 9 (bare except) ──→ standalone (can run parallel)
Task 7 (blueprints) ──→ standalone (mechanical refactoring)
Task 6 (persist task status) ──→ standalone
Task 8 (type hints) ──→ depends on Task 7
```

## Recommended Execution Order

1. **Task 10** (.dockerignore) — standalone, S effort
2. **Task 11** (pin deps) — standalone, M effort
3. **Task 9** (bare except) — standalone, S effort, can run parallel with 10/11
4. **Task 7** (blueprints) — standalone, L effort, can run parallel with 10/11/9
5. **Task 6** (persist task status) — standalone, M effort
6. **Task 8** (type hints) — depends on Task 7, M effort
