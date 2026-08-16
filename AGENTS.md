# SummarizeMe agent guide

## Operating principle

Accuracy is more important than output compression. Treat source code, Git state,
targeted tests, CI configuration, and live runtime evidence as authoritative.
README content, code-graph results, and recalled session memory are discovery aids;
they are not proof.

At the start of a task, confirm the repository path, branch, HEAD, and dirty state.
Do not overwrite, revert, stage, commit, push, open a pull request, merge, deploy,
or change remote infrastructure unless the user explicitly asks for that action.

## Repository map

- `app.py`: Flask routes, database sessions, background task orchestration,
  authorization boundaries, chat, and summarization endpoints.
- `db/models.py`: SQLAlchemy data model.
- `summarizer_v2.py`: chunking, prompts, generation, and embedding calls.
- `youtube_utils.py`: YouTube acquisition and transcript normalization.
- `auth_utils.py`: Cloudflare Access JWT handling and explicit development auth.
- `run_vectorizers.py`: PostgreSQL/pgvector embedding backfill; requires a real
  database and embedding endpoint.
- `tests/unit/`: isolated behavior tests. `tests/integration/`: route/database
  contracts. PGAI tests require both the `ai` extension and a reachable embedding
  endpoint.
- `docker-compose.dev.yml`, `Dockerfile*`, and `.github/workflows/`: runtime and
  delivery contracts. Inspect them directly before claiming container or deployment
  behavior.

## Runtime boundaries

- Production uses PostgreSQL. SQLite is valid only for isolated tests and cannot
  establish PostgreSQL, pgvector, or PGAI compatibility.
- vLLM generation and embedding services are distinct endpoints. Unit tests must
  mock them; live endpoint claims require an explicit runtime check.
- YouTube wrappers, Cloudflare authentication, Docker, GitHub, and remote vLLM
  hosts are external side effects. Do not invoke or alter them unless the task
  requires it and the user has authorized the scope.
- Dynamic dispatch, threads, environment-driven selection, SQL text, and template
  rendering require source inspection. Do not infer them from a missing graph edge.

## Validation

Use the smallest relevant gate first, then expand only when the changed boundary
requires it:

1. `.venv/bin/ruff check <changed paths>` and `.venv/bin/ruff format --check <changed paths>`.
2. `.venv/bin/pytest tests/unit/ -q` for isolated Python changes.
3. Run the affected integration tests with `TEST_DATABASE_URL` only when a disposable
   PostgreSQL instance is available.
4. Run `.venv/bin/pyright` for changed Python boundaries; inspect diagnostics rather
   than assuming an empty result.
5. Build or start a container only for packaging/runtime changes.

Report skipped tests, warnings, non-blocking CI jobs, mocks, and unavailable
services as limitations. They are not successful validation.

## Pull Request Code Review Cycle

Every PR must pass a thorough code review before merging. The cycle is:

### Review Process

1. **Prepare the branch.** Ensure the branch is up to date with `main`, all
   local changes are committed, and tests pass locally:
   ```bash
   git fetch origin
   git rebase origin/main  # or merge, as appropriate
   .venv/bin/ruff check . && .venv/bin/ruff format --check .
   .venv/bin/pytest tests/unit/ tests/integration/ -q
   ```

2. **Run parallel review subagents.** Spawn 4–6 review agents in parallel, each
   targeting a specific file or concern. Example agents:
   - `ReviewSummarizerV2` — summarizer_v2.py: exception handling, logging, model names
   - `ReviewAppConfig` — app_config.py: SQL templates, log messages, imports
   - `ReviewChatBlueprint` — blueprints/chat.py: SQL query, error handling, model names
   - `ReviewApiBlueprint` — blueprints/api.py: model defaults, logging, endpoint behavior
   - `ReviewVectorizers` — run_vectorizers.py: UNIQUE constraint, auth token, index
   - `ReviewTestsDocker` — tests/, Docker/, CI: coverage, build, health checks

   Each agent must read the target file(s), identify issues by severity
   (CRITICAL/HIGH/MEDIUM/LOW), and report actionable fixes.

3. **Compile and prioritize findings.** Aggregate all agent outputs. Fix in
   priority order:
   - **CRITICAL** — Must fix before merge (data loss, security, broken functionality)
   - **HIGH** — Should fix (silent failures, code quality, security risks)
   - **MEDIUM** — Nice to fix (maintainability, consistency, edge cases)
   - **LOW** — Deferred (cosmetic, future improvements)

4. **Fix and verify.** Apply fixes, then re-run all gates:
   ```bash
   .venv/bin/ruff check . && .venv/bin/ruff format .
   .venv/bin/pytest tests/unit/ tests/integration/ -q
   docker compose -f docker-compose.dev.yml build app  # if code changed
   docker compose -f docker-compose.dev.yml up -d
   curl -s http://localhost:5001/health  # verify runtime
   ```

5. **Second-pass review.** After fixes, run a second review pass (fewer agents,
   focused on verifying fixes and catching any new issues introduced). Only one
   pass is needed if no issues are found.

6. **Post review comments.** Use `gh pr review` to post a structured review
   comment on the PR. Include:
   - Review status (APPROVED with notes / Changes requested)
   - Checklist of all gates (ruff, pytest, Docker, runtime)
   - Positive findings
   - Remaining issues (with severity and fix suggestions)
   - File change summary
   - Verification results

### Merge Criteria

A PR is ready to merge only when:
- All CRITICAL and HIGH issues are resolved
- All tests pass (ruff, pytest, Docker build)
- Runtime verification passes (health endpoint, key functionality)
- No open findings remain
- Review comment posted on the PR

### Merge Procedure

When all criteria are met:
```bash
git fetch origin
git merge origin/main  # fast-forward if possible
git push origin fix/<branch>  # ensure PR is up to date
# Then squash-merge via `gh pr merge` or GitHub UI
```

**Never merge** a PR with open CRITICAL or HIGH findings. The absence of
blocking issues is the gate — without verification, the PR is not ready.

## Post-Merge Branch Workflow
After a PR is merged to `main`, always switch the local branch back to `main` and
fast-forward it:

```bash
git checkout main
git pull origin main
```

This ensures the local `main` is in sync with the remote and prevents stale
state when starting new work. Never continue development on the merged branch
after the merge — create a new branch from the updated `main`.

## Codebase Memory

Use the graph for initial architecture orientation, caller/callee candidates, and
change-impact candidates. Confirm material paths with source reads, raw Git diff,
tests, and runtime configuration. Missing graph edges mean unknown, not absent.

Record only consequential graph misses, stale results, or false confidence in
`.omp/ACCURACY-LEDGER.md`.
