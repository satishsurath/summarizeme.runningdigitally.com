# Multi-Agent Implementation Checklist & Coordination Board

This checklist serves as the authoritative live-tracking board for multi-agent execution, test validation, risk monitoring, issue tracking, and independent subagent code reviews.

**Status Legend:**
- `[ ] PENDING` — Not started; waiting on prior phase gate
- `[-] IN_PROGRESS` — Claimed by designated agent
- `[!] BLOCKED` — Blocked by dependency or unexpected failure
- `[?] READY_FOR_REVIEW` — Subagent finished; awaiting independent review
- `[x] DONE` — Verified by tests, reviewed by independent subagents, and accepted

---

## Phase 0: Baseline Contracts, Schemas & Probes

### Track 0-A (Agent-Alpha: Contracts & Runtime Probes)
- [x] **Task 0.A1** (`BKG-001`, `RSK-004`): Create `services/contracts.py` with Pydantic models for 9-section summary (`StructuredSummaryV3`, `ExecutiveOverview`, `MainThesis`, `Topic`, `SupportingPoint`, `Chapter`, `ImportantDetail`, `Decision`, `Recommendation`, `ActionItem`, `GlossaryTerm`, `EvidenceReference`, `OpenQuestion`, `Caveat`).
  - *Deliverables*: `services/contracts.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_contracts.py -v` (PASSED)
- [x] **Task 0.A2** (`BKG-001`, `PT-001`): Create streaming event models in `services/contracts.py` (`ReasoningDelta`, `AnswerDelta`, `SourcesPayload`, `UsagePayload`, `DonePayload`).
  - *Deliverables*: `services/contracts.py` (PASSED)
- [x] **Task 0.A3** (`BKG-002`, `PT-008`): Implement `services/runtime_probes.py` with probes for Qwen3.8 served ID (`nemo-qwen3.8-27b-nvfp4`), reasoning syntax, SGLang JSON schema output, and Nomic 768-dim embedding output.
  - *Deliverables*: `services/runtime_probes.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_runtime_probes.py -v` (PASSED)

### Track 0-B (Agent-Beta: Configuration, Baseline Fixtures & Tests)
- [x] **Task 0.B1** (`BKG-003`, `RSK-001`, `RSK-002`, `RSK-006`): Update `app_config.py` with feature flags (`ASYNC_PIPELINE_ENABLED`, `AI_MODEL_REGISTRY_ENABLED`) and resource constants (`GEN_BATCH_CONCURRENCY=2`, `GEN_INTERACTIVE_RESERVE=1`, `YT_MIN_START_INTERVAL_SECONDS=12`, `EMBED_MAX_SEQUENCES=8`, `EMBED_MAX_BATCH_TOKENS=8192`).
  - *Deliverables*: `app_config.py`
  - *Verification*: `.venv/bin/ruff check app_config.py` (PASSED)
- [x] **Task 0.B2**: Create synthetic transcript fixtures in `tests/fixtures/synthetic_transcripts.py` (short, long, technical, multi-speaker).
  - *Deliverables*: `tests/fixtures/synthetic_transcripts.py` (PASSED)
- [x] **Task 0.B3**: Add unit tests for contracts and runtime probe mocks in `tests/unit/test_contracts.py` and `tests/unit/test_runtime_probes.py`.
  - *Deliverables*: `tests/unit/test_contracts.py`, `tests/unit/test_runtime_probes.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_contracts.py tests/unit/test_runtime_probes.py -v` (PASSED: 27/27 tests)

### Phase 0 Independent Review & Synchronization Gate (Lead Orchestrator)
- [x] **Task 0.R1 (ReviewCore Subagent)**: Independent audit of Pydantic models, quote validation, and probe exception handling (`RSK-004`). (ALL CLEAR)
- [x] **Task 0.R2 (ReviewSurfaces Subagent)**: Independent audit of config constants, stream event envelopes, and mock test coverage. (ALL CLEAR)
- [x] **Task 0.R3 (Risk & Issue Audit)**: Verify `risk_register.md` and `issue_tracker_and_backlog.md` are updated for Phase 0 items (`PT-008`, `BKG-001..BKG-003`). (PASSED)
- [x] **Gate 0.Sync**: Run Ruff, Pyright, and unit test suite. (PASSED: 309 unit tests passed, 0 lint errors, 0 type errors)

---

## Phase 1: PostgreSQL Durable Queue & Worker Framework

### Track 1-A (Agent-Alpha: Alembic Migration & JobQueue Service)
- [x] **Task 1.A1** (`BKG-004`, `PT-009`): Create Alembic migration `alembic/versions/e1a2b3c4d5f6_add_processing_pipeline.py` for `jobs`, `work_items`, `resource_limits`, `resource_leases`, `external_rate_limits`.
  - *Deliverables*: `alembic/versions/e1a2b3c4d5f6_add_processing_pipeline.py`, `db/models.py`
  - *Verification*: Model inspection and schema generation (PASSED)
- [x] **Task 1.A2** (`BKG-005`, `RSK-003`, `RSK-007`): Implement `services/job_queue.py` (`create_job`, `claim` with `FOR UPDATE SKIP LOCKED`, `renew`, `complete`, `retry`, `fail`, `recover_expired_leases`, `get_job_progress`).
  - *Deliverables*: `services/job_queue.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_job_queue.py -v` (PASSED: 9/9 tests)
- [x] **Task 1.A3** (`RSK-007`): Create unit/integration tests in `tests/unit/test_job_queue.py` verifying atomic claims, retries, and lease recovery.
  - *Deliverables*: `tests/unit/test_job_queue.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_job_queue.py -v` (PASSED)

### Track 1-B (Agent-Beta: Resource Admission & Worker CLI)
- [x] **Task 1.B1** (`BKG-006`, `RSK-001`, `RSK-002`): Implement `services/resource_admission.py` (`acquire_lease`, `release_lease`, `reserve_external_start`, `open_circuit`, `record_external_success`).
  - *Deliverables*: `services/resource_admission.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_resource_admission.py -v` (PASSED: 6/6 tests)
- [x] **Task 1.B2** (`BKG-007`, `RSK-010`): Implement `workers/main.py` CLI supporting `--resource-class` (`control`, `youtube`, `generation`, `embedding`, `all`), SIGTERM handling, drain, and idle exit (`--idle-exit-seconds`).
  - *Deliverables*: `workers/main.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_worker_cli.py -v` (PASSED: 2/2 tests)
- [x] **Task 1.B3**: Add API status compatibility adapter in `blueprints/api.py` reading from `JobQueue` when `ASYNC_PIPELINE_ENABLED=true`.
  - *Deliverables*: `blueprints/api.py` (PASSED)
- [x] **Task 1.B4**: Add unit tests in `tests/unit/test_resource_admission.py` and `tests/unit/test_worker_cli.py` including fault injection (worker crash recovery, lease timeouts).
  - *Deliverables*: `tests/unit/test_resource_admission.py`, `tests/unit/test_worker_cli.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_resource_admission.py tests/unit/test_worker_cli.py -v` (PASSED)

### Phase 1 Independent Review & Synchronization Gate (Lead Orchestrator)
- [x] **Task 1.R1 (ReviewCore Subagent)**: Independent audit of SQL `SKIP LOCKED` query safety, transaction boundaries ($\le 50\text{ms}$), lease expiration math, and connection pool behavior (`RSK-003`). (ALL CLEAR)
- [x] **Task 1.R2 (ReviewSurfaces Subagent)**: Independent audit of Worker CLI lifecycle, API compatibility adapter, error sanitization, and integration test rigor. (ALL CLEAR)
- [x] **Task 1.R3 (Risk & Issue Audit)**: Verify `PT-009` progress and confirm `RSK-003` & `RSK-007` mitigation status in `risk_register.md`. (PASSED)
- [x] **Gate 1.Sync**: Run Ruff and queue/admission unit test suite.
  - *Verification*: `.venv/bin/ruff check . && .venv/bin/pyright && .venv/bin/pytest tests/unit/ -v` (326 passed, 0 lint errors, 0 type errors)

---

## Phase 2: Timestamped Transcripts & YouTube Acquisition

### Track 2-A (Agent-Alpha: Transcript Segments Schema & Ingest Service)
- [x] **Task 2.A1** (`BKG-008`): Create Alembic migration `alembic/versions/f2b3c4d5e6a7_add_transcript_segments.py` for `transcript_segments` table (`start_seconds`, `end_seconds`, `speaker`, `text`, `normalized_text`, `content_hash`).
  - *Deliverables*: `alembic/versions/f2b3c4d5e6a7_add_transcript_segments.py`, `db/models.py`
  - *Verification*: Schema and model validation (PASSED)
- [x] **Task 2.A2** (`BKG-009`, `PT-003`): Implement `services/youtube_acquisition.py` with `discover_channel_videos(channel_url)` and `fetch_video_transcript(video_id)` preserving SRT/VTT timestamps and segment order.
  - *Deliverables*: `services/youtube_acquisition.py`
- [x] **Task 2.A3**: Implement dual-population of `transcript_segments` and legacy `transcript_no_ts` strings on `Video`.
  - *Deliverables*: `services/youtube_acquisition.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_youtube_acquisition.py -v` (PASSED)
- [x] **Task 2.A4**: Add unit tests in `tests/unit/test_youtube_acquisition.py` with mocked yt-dlp/SRT inputs and corrupted timestamp edge cases.
  - *Deliverables*: `tests/unit/test_youtube_acquisition.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_youtube_acquisition.py -v` (PASSED: 7/7 tests)

### Track 2-B (Agent-Beta: Discovery & Transcript Stage Handlers with Rate Pacing)
- [x] **Task 2.B1**: Implement `workers/stages/discovery.py` stage handler to expand channel into per-video `transcript` work items.
  - *Deliverables*: `workers/stages/discovery.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_transcript_stage.py -v` (PASSED)
- [x] **Task 2.B2** (`BKG-010`, `RSK-002`): Implement `workers/stages/transcript.py` stage handler with YouTube 12s pacing + 3s jitter lease, yt-dlp execution, 429 circuit breaking, and downstream `summarize` / `embed_transcript` enqueueing.
  - *Deliverables*: `workers/stages/transcript.py`
- [x] **Task 2.B3** (`RSK-002`): Add unit tests in `tests/unit/test_transcript_stage.py` for throttle recovery, permanent failure handling (no captions), and circuit breaker tripping.
  - *Deliverables*: `tests/unit/test_transcript_stage.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_transcript_stage.py -v` (PASSED: 4/4 tests)

### Phase 2 Independent Review & Synchronization Gate (Lead Orchestrator)
- [x] **Task 2.R1 (ReviewCore Subagent)**: Independent audit of transcript segment normalization, hash consistency, yt-dlp subprocess security (array args, no shell injection), and timestamp range invariants. (ALL CLEAR)
- [x] **Task 2.R2 (ReviewSurfaces Subagent)**: Independent audit of YouTube start pacing rate enforcement, exponential backoff with jitter, downstream work item creation, and error logging sanitization (`RSK-002`). (ALL CLEAR)
- [x] **Task 2.R3 (Risk & Issue Audit)**: Close `PT-003` in `issue_tracker_and_backlog.md` and verify `RSK-002` mitigation. (PASSED)
- [x] **Gate 2.Sync**: Run Ruff and transcript pipeline unit tests.
  - *Verification*: `.venv/bin/ruff check . && .venv/bin/pyright && .venv/bin/pytest tests/unit/ -v` (337 passed, 0 lint errors, 0 type errors)

---

## Phase 3: Structured Summary Generation & Admission Control

### Track 3-A (Agent-Alpha: 9-Section Summary Engine & SGLang Prompting)
- [x] **Task 3.A1** (`BKG-011`): Create Alembic migration `alembic/versions/b3c4d5e6a7f8_add_summary_runs.py` for `summary_runs` table with JSONB `structured_summary`, `reasoning_output`, `generation_profile_hash`.
  - *Deliverables*: `alembic/versions/b3c4d5e6a7f8_add_summary_runs.py`, `db/models.py`
  - *Verification*: Schema and model validation (PASSED)
- [x] **Task 3.A2** (`BKG-012`, `PT-001`, `RSK-005`): Implement `services/summary_service.py` with single-call 9-section structured generation, reasoning effort controls (`disabled`, `low`, `medium`, `xhigh`), and separate thinking capture.
  - *Deliverables*: `services/summary_service.py`
- [x] **Task 3.A3** (`BKG-013`): Implement quote containment validator and separate reasoning output capture in `services/summary_service.py`.
  - *Deliverables*: `services/summary_service.py`
- [x] **Task 3.A4** (`RSK-004`): Implement evidence validation (`E1 · 12:42`), quote containment checks against source transcripts, and single corrective retry logic.
  - *Deliverables*: `services/summary_service.py`
- [x] **Task 3.A5**: Implement legacy `summaries_v2` table projection write for backward compatibility.
  - *Deliverables*: `services/summary_service.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_summary_service.py -v` (PASSED)
- [x] **Task 3.A6**: Add unit tests in `tests/unit/test_summary_service.py` testing standard, oversized, corrupted JSON, and ungrounded quotation cases.
  - *Deliverables*: `tests/unit/test_summary_service.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_summary_service.py -v` (PASSED: 4/4 tests)

### Track 3-B (Agent-Beta: Summary Worker Stage & Admission Integration)
- [x] **Task 3.B1** (`BKG-014`, `RSK-001`, `RSK-003`): Implement `workers/stages/summary.py` stage handler: acquire batch generation lease (max 2), fetch transcript segments in short DB transaction, invoke `SummaryService`, persist `SummaryRun`, release lease, enqueue `embed_summary`.
  - *Deliverables*: `workers/stages/summary.py`
- [x] **Task 3.B2** (`RSK-001`): Enforce interactive reservation (1 slot reserved, priority over batch work) in `services/resource_admission.py`.
  - *Deliverables*: `services/resource_admission.py`
- [x] **Task 3.B3** (`RSK-001`): Add unit tests in `tests/unit/test_summary_stage.py` verifying generation concurrency limits under simulated load.
  - *Deliverables*: `tests/unit/test_summary_stage.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_summary_stage.py -v` (PASSED: 2/2 tests)

### Phase 3 Independent Review & Synchronization Gate (Lead Orchestrator)
- [x] **Task 3.R1 (ReviewCore Subagent)**: Independent audit of SGLang prompt templates, token budget calculations, hierarchical synthesis logic, quote validation (`RSK-004`), and separate thinking persistence (`RSK-005`). (ALL CLEAR)
- [x] **Task 3.R2 (ReviewSurfaces Subagent)**: Independent audit of generation lease admission (2 batch + 1 interactive) (`RSK-001`), worker failure recovery, legacy projection updates, and retry bounds. (ALL CLEAR)
- [x] **Task 3.R3 (Risk & Issue Audit)**: Close `PT-001` in `issue_tracker_and_backlog.md` and audit `RSK-001`, `RSK-004`, `RSK-005` in `risk_register.md`. (PASSED)
- [x] **Gate 3.Sync**: Run Ruff and summary generation tests.
  - *Verification*: `.venv/bin/ruff check . && .venv/bin/pyright && .venv/bin/pytest tests/unit/ -v` (343 passed, 0 lint errors, 0 type errors)

---

## Phase 4: Batched Embeddings & Unified Content Index

### Track 4-A (Agent-Alpha: Nomic Batch Packer & Embedding Worker)
- [x] **Task 4.A1**: Implement `services/embedding_service.py` with sentence-aware chunking (300–700 tokens, 10–15% overlap) and parent section extraction (1,500–3,000 tokens).
  - *Deliverables*: `services/embedding_service.py`
- [x] **Task 4.A2** (`BKG-015`, `RSK-005`, `RSK-006`): Implement Nomic batch packing ($\le 32$ sequences, $\le 8,192$ aggregate tokens) with `search_document: ` prefix, vector validation, and strict exclusion of model thinking.
  - *Deliverables*: `services/embedding_service.py`
- [x] **Task 4.A3**: Implement `workers/stages/embedding.py` (`embed_transcript` and `embed_summary`) and `workers/stages/finalize.py`.
  - *Deliverables*: `workers/stages/embedding.py`, `workers/stages/finalize.py`
- [x] **Task 4.A4** (`RSK-006`): Add unit tests in `tests/unit/test_embedding_service.py` for batch packing bounds, dimension validation (768), and normalization verification.
  - *Deliverables*: `tests/unit/test_embedding_service.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_embedding_service.py -v` (PASSED: 9/9 tests)

### Track 4-B (Agent-Beta: Unified Content Chunks Schema & Migration Bridge)
- [x] **Task 4.B1** (`BKG-016`): Create Alembic migration `alembic/versions/c4d5e6a7f8a9_add_content_chunks.py` for `content_chunks` table with pgvector HNSW index and GIN tsvector index.
  - *Deliverables*: `alembic/versions/c4d5e6a7f8a9_add_content_chunks.py`, `db/models.py`
  - *Verification*: Schema and model validation (PASSED)
- [x] **Task 4.B2** (`BKG-017`, `RSK-009`): Implement dual-write bridge writing to `content_chunks` and legacy vector tables (`summaries_v2_*_embedding`, `videos_transcript_no_ts_embedding`).
  - *Deliverables*: `services/embedding_service.py`
- [x] **Task 4.B3** (`RSK-009`): Add unit tests in `tests/unit/test_embedding_stage.py` verifying stage handlers and finalization.
  - *Deliverables*: `tests/unit/test_embedding_stage.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_embedding_stage.py -v` (PASSED: 3/3 tests)

### Phase 4 Independent Review & Synchronization Gate (Lead Orchestrator)
- [x] **Task 4.R1 (ReviewCore Subagent)**: Independent audit of Nomic token packing algorithms, sequence limits ($\le 32$), aggregate token limits ($\le 8,192$), vector normalization checks, and thinking exclusion (`RSK-005`, `RSK-006`). (ALL CLEAR)
- [x] **Task 4.R2 (ReviewSurfaces Subagent)**: Independent audit of HNSW/GIN index definitions, dual-write bridge correctness (`RSK-009`), finalize stage job status derivation, and embedding worker lease handling. (ALL CLEAR)
- [x] **Task 4.R3 (Risk & Issue Audit)**: Audit `RSK-006` and `RSK-009` in `risk_register.md`. (PASSED)
- [x] **Gate 4.Sync**: Run Ruff and embedding pipeline unit tests.
  - *Verification*: `.venv/bin/ruff check . && .venv/bin/pyright && .venv/bin/pytest tests/unit/ -v` (355 passed, 0 lint errors, 0 type errors)

---

## Phase 5: Stateful Chat, Hybrid Retrieval & Model Registry

### Track 5-A (Agent-Alpha: Conversational State & Hybrid Retrieval Engine)
- [x] **Task 5.A1** (`BKG-018`): Create Alembic migration `alembic/versions/d5e6a7f8a9b0_add_chat_and_model_registry.py` for `conversations` and `conversation_messages`.
  - *Deliverables*: `alembic/versions/d5e6a7f8a9b0_add_chat_and_model_registry.py`, `db/models.py`
  - *Verification*: Schema and model validation (PASSED)
- [x] **Task 5.A2** (`BKG-019`, `PT-005`): Implement `services/retrieval_service.py` (pgvector cosine + FTS with Reciprocal Rank Fusion, confidence threshold, source diversity, parent expansion).
  - *Deliverables*: `services/retrieval_service.py`
- [x] **Task 5.A3** (`BKG-021`, `PT-007`, `RSK-001`): Update `blueprints/chat.py` with multi-turn history loading, typed SSE streaming (`reasoning_delta`, `answer_delta`, `sources`, `usage`, `done`), interactive generation lease, and separate thinking/answer persistence.
  - *Deliverables*: `blueprints/chat.py`
- [x] **Task 5.A4**: Add unit tests in `tests/unit/test_retrieval_service.py` and `tests/unit/test_streaming_chat.py`.
  - *Deliverables*: `tests/unit/test_retrieval_service.py`, `tests/unit/test_streaming_chat.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_retrieval_service.py tests/unit/test_streaming_chat.py -v` (PASSED: 11/11 tests)

### Track 5-B (Agent-Beta: Admin Model Registry & Qualification Engine)
- [x] **Task 5.B1** (`BKG-018`, `PT-002`, `PT-008`): Create Alembic migration `alembic/versions/d5e6a7f8a9b0_add_chat_and_model_registry.py` for `ai_endpoints`, `ai_models`, `ai_runtime_pools`, `user_ai_preferences`.
  - *Deliverables*: `alembic/versions/d5e6a7f8a9b0_add_chat_and_model_registry.py`, `db/models.py`
  - *Verification*: Schema and model validation (PASSED)
- [x] **Task 5.B2** (`BKG-020`, `RSK-008`): Implement `services/model_registry.py` (`/v1/models` discovery, qualification test runner, profile defaults, pool ceiling enforcement, user preference resolution).
  - *Deliverables*: `services/model_registry.py`
- [x] **Task 5.B3** (`RSK-008`): Implement dynamic model and user preference REST endpoints in `blueprints/api.py` and `blueprints/chat.py`.
  - *Deliverables*: `blueprints/api.py`, `blueprints/chat.py`
- [x] **Task 5.B4** (`RSK-008`): Add unit tests in `tests/unit/test_model_registry.py` and `tests/unit/test_chat_phase5.py`.
  - *Deliverables*: `tests/unit/test_model_registry.py`, `tests/unit/test_chat_phase5.py`
  - *Verification*: `.venv/bin/pytest tests/unit/test_model_registry.py tests/unit/test_chat_phase5.py -v` (PASSED: 7/7 tests)

### Phase 5 Independent Review & Synchronization Gate (Lead Orchestrator)
- [x] **Task 5.R1 (ReviewCore Subagent)**: Independent audit of hybrid search SQL, RRF math, prompt injection guards, untrusted evidence boundary, and interactive reservation priority (`RSK-001`). (ALL CLEAR)
- [x] **Task 5.R2 (ReviewSurfaces Subagent)**: Independent audit of Model Registry REST security (admin RBAC, SSRF protection, secret masking in JSON) (`RSK-008`), SSE stream formatting, and user preference fallback. (ALL CLEAR)
- [x] **Task 5.R3 (Risk & Issue Audit)**: Close `PT-002`, `PT-005`, `PT-007`, `PT-008` in `issue_tracker_and_backlog.md` and audit `RSK-008` in `risk_register.md`. (ALL RESOLVED)
- [x] **Gate 5.Sync**: Run Ruff and chat/registry unit tests.
  - *Verification*: `.venv/bin/ruff check . && .venv/bin/pyright && .venv/bin/pytest tests/unit/ -v` (365 passed, 0 lint errors, 0 type errors)

---

## Phase 6: Next.js Modern Frontend & Interactive UX

### Track 6-A (Agent-Alpha: 9-Section Summary, Timeline & Evidence UX)
- [x] **Task 6.A1** (`BKG-022`, `DEBT-002`): Create `frontend/src/components/SummaryNavigation.tsx` (sticky sidebar / mobile drawer with scroll-spy over all 9 sections).
  - *Deliverables*: `frontend/src/components/SummaryNavigation.tsx`
- [x] **Task 6.A2** (`BKG-023`): Create `frontend/src/components/ChapterTimeline.tsx` (timestamped chapter list linking to YouTube player).
  - *Deliverables*: `frontend/src/components/ChapterTimeline.tsx`
- [x] **Task 6.A3** (`BKG-023`): Create `frontend/src/components/EvidenceDrawer.tsx` (transcript excerpts, speaker, video title, YouTube timestamp link).
  - *Deliverables*: `frontend/src/components/EvidenceDrawer.tsx`
- [x] **Task 6.A4** (`BKG-022`): Create `frontend/src/components/SummaryViewer.tsx` assembling the 9 sections, timeline, and evidence drawer into an integrated responsive layout.
  - *Deliverables*: `frontend/src/components/SummaryViewer.tsx`

### Track 6-B (Agent-Beta: Multi-Turn Chat, Thinking Accordion & Admin Registry UI)
- [x] **Task 6.B1** (`BKG-024`): Create `frontend/src/components/ThinkingBlock.tsx` (collapsed by default, live elapsed time, formatted/raw view).
  - *Deliverables*: `frontend/src/components/ThinkingBlock.tsx`
- [x] **Task 6.B2** (`BKG-024`): Create `frontend/src/components/ReasoningSelector.tsx` (Disabled, Low, Medium, High with tooltips).
  - *Deliverables*: `frontend/src/components/ReasoningSelector.tsx`
- [x] **Task 6.B3**: Create `frontend/src/types/summary.ts` and `frontend/src/types/models.ts` with TypeScript contracts.
  - *Deliverables*: `frontend/src/types/summary.ts`, `frontend/src/types/models.ts`
- [x] **Task 6.B4** (`BKG-025`): Create Admin Model Registry UI in `frontend/src/app/admin/models/page.tsx` and `frontend/src/components/ModelRegistryAdmin.tsx`.
  - *Deliverables*: `frontend/src/app/admin/models/page.tsx`, `frontend/src/components/ModelRegistryAdmin.tsx`

### Phase 6 Independent Review & Synchronization Gate (Lead Orchestrator)
- [x] **Task 6.R1 (ReviewCore Subagent)**: Independent audit of summary rendering security (sanitization of markdown/evidence text) (`DEBT-002`), typed state handling, and YouTube deep-link timestamp accuracy. (ALL CLEAR)
- [x] **Task 6.R2 (ReviewSurfaces Subagent)**: Independent audit of SSE stream consumption in React, auto-scroll behavior, thinking accordion accessibility, and admin UI form validation. (ALL CLEAR)
- [x] **Task 6.R3 (Risk & Issue Audit)**: Close `DEBT-002` in `issue_tracker_and_backlog.md`. (ALL RESOLVED)
- [x] **Gate 6.Sync**: Run Next.js lint and production build.
  - *Verification*: `npm --prefix frontend run lint && npm --prefix frontend run build` (PASSED in 7.8s, 0 lint warnings, 0 type errors)

---

## Phase 7: Autoscaling, Evaluation, Redis Removal & Cutover

### Track 7-A (Agent-Alpha: Worker Compose Topology & Scale-to-Zero Scripts)
- [ ] **Task 7.A1** (`BKG-026`): Update `docker-compose.prod.yml` and `docker-compose.dev.yml` with stage worker services (`worker-control`, `worker-transcript`, `worker-summary`, `worker-embedding`).
  - *Deliverables*: `docker-compose.prod.yml`, `docker-compose.dev.yml`
- [ ] **Task 7.A2** (`BKG-026`, `RSK-010`): Create `scripts/scale_workers.sh` and systemd timer definition for queue-depth polling and scale-to-zero with 5-minute idle grace period.
  - *Deliverables*: `scripts/scale_workers.sh`
- [ ] **Task 7.A3** (`RSK-010`): Verify clean worker drain on SIGTERM with active leases test.

### Track 7-B (Agent-Beta: Quality Corpus Benchmark & Redis Deprecation Cleanup)
- [ ] **Task 7.B1** (`BKG-027`, `RSK-001`, `RSK-004`): Implement and run `tests/evaluation/test_quality_corpus.py` evaluating factuality, evidence accuracy, TTFT, and latency across reasoning levels.
  - *Deliverables*: `tests/evaluation/test_quality_corpus.py`
- [ ] **Task 7.B2** (`BKG-028`, `PT-009`, `DEBT-003`): Remove `services/task_store.py`, remove `redis` service from Compose, and remove `redis` from `requirements.in` / `requirements.txt`.
  - *Deliverables*: `requirements.in`, `requirements.txt`, `docker-compose.prod.yml`
- [ ] **Task 7.B3**: Enable `ASYNC_PIPELINE_ENABLED=true` and `AI_MODEL_REGISTRY_ENABLED=true` by default in `app_config.py`.
  - *Deliverables*: `app_config.py`

### Phase 7 Final Comprehensive Gate (Lead Orchestrator)
- [ ] **Task 7.R1 (ReviewCore Subagent)**: Final codebase audit of concurrency limits, zero Redis remnants, database index hygiene, and crash recovery.
- [ ] **Task 7.R2 (ReviewSurfaces Subagent)**: Final surface audit of production Docker compose builds, health endpoints, evaluation corpus metrics, and documentation sync.
- [ ] **Task 7.R3 (Risk & Issue Closeout Audit)**: Final verification that all problem tickets (`PT-001..PT-009`) and backlog items (`BKG-001..BKG-028`) are resolved, and all risk mitigations in `risk_register.md` are actively enforced.
- [ ] **Gate 7.Final**: Full test suite, ruff, pyright, and container builds.
  - *Command*: `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest tests/unit/ tests/integration/ -v && .venv/bin/pyright && docker compose -f docker-compose.prod.yml build`
