# SummarizeMe Issue Tracker & Implementation Backlog

This document tracks all active problem tickets, architectural backlog items, technical debt, and implementation issues for the AI Product & Performance Scaling Architecture.

---

## 1. Active Problem Tickets (Operational Issues)

| Ticket ID | Title | Summary / Root Cause | Target Fix Phase | Severity | Status |
|---|---|---|:---:|:---:|:---:|
| **PT-001** | Summarization vLLM Reasoning | vLLM 404 + Qwen3.6 reasoning content parsed with heuristics instead of typed streaming events. | Phase 0 & 3 | High | **Resolved** |
| **PT-002** | Chat Model Selector | Chat deprecated model selector not synchronized with backend active models; hardcoded options in UI. | Phase 5 & 6 | High | **Resolved** |
| **PT-003** | youtu.be URL Format | Single video download `youtu.be` format not consistently detected by legacy acquisition script. | Phase 2 | Medium | **Resolved** |
| **PT-004** | DB Persistence on Rebuild | Docker rebuild previously risked data persistence issues if volumes were misconfigured. | Phase 1 & 7 | High | **Resolved** |
| **PT-005** | Chat Embedding 404 | Chat RAG query failed when embedding service URL was not reachable on port 8001. | Phase 4 & 5 | High | **Resolved** |
| **PT-006** | Branch Protection & Status Checks | PR merged despite failed lint; missing branch protection gate in CI. | Phase 0 | Medium | **Resolved** |
| **PT-007** | Chat Thinking Block Post-Stream | Chat thinking block dissolved into main answer post-stream due to markdown string concatenation. | Phase 3 & 6 | High | **Resolved** |
| **PT-008** | Model Identifier Drift | `app_config.py` defaults to `nemo-qwen3.6-35b` while Homelab runs `nemo-qwen3.8-27b-nvfp4`. | Phase 0 & 5 | High | **Resolved** |
| **PT-009** | Daemon Thread Task Store | Background jobs run as daemon threads inside Gunicorn with Redis task store lacking atomic leases. | Phase 1 & 7 | Critical | **Resolved** |
| **PT-010** | Frontend Docker Context Conflict | Root `.dockerignore` excludes `frontend/`, causing `Dockerfile.frontend` build to fail when context is root. | Phase 6 & 7 | High | **Resolved** |
| **PT-011** | Worker Module Resolution | Worker container executing `python workers/main.py` fails importing `app_config` due to `sys.path[0]` isolation. | Phase 1 & 7 | High | **Resolved** |
| **PT-012** | Migration `d83220d1c993` Idempotency | Alembic migration crashes with `DuplicateColumn` on databases with pre-existing `video_folders.content_type`. | Phase 0 & 1 | Low | **Resolved** |

---

## 2. Implementation Backlog Items (By Phase)

### Phase 0: Baseline Contracts, Types & Probes
- [x] **BKG-001** (`P0`): Implement Pydantic 9-section summary contract and evidence reference models in `services/contracts.py`.
- [x] **BKG-002** (`P0`): Implement exact runtime probes for Qwen3.8 served ID and Nomic 768-dim output in `services/runtime_probes.py`.
- [x] **BKG-003** (`P1`): Add configuration constants and feature flags (`ASYNC_PIPELINE_ENABLED`, `AI_MODEL_REGISTRY_ENABLED`) in `app_config.py`.

### Phase 1: PostgreSQL Durable Queue & Worker Framework
- [x] **BKG-004** (`P0`): Create Alembic migration for `jobs`, `work_items`, `resource_limits`, `resource_leases`, `external_rate_limits`.
- [x] **BKG-005** (`P0`): Implement `JobQueue` service with atomic `FOR UPDATE SKIP LOCKED` claim and lease recovery.
- [x] **BKG-006** (`P0`): Implement `ResourceAdmission` service for cross-process concurrency and start pacing.
- [x] **BKG-007** (`P1`): Implement `workers/main.py` CLI supporting resource classes and graceful SIGTERM drain.

### Phase 2: Timestamped Transcripts & YouTube Acquisition
- [x] **BKG-008** (`P0`): Create Alembic migration for `transcript_segments` table.
- [x] **BKG-009** (`P0`): Implement direct `yt-dlp` acquisition service preserving SRT/VTT timestamps and speaker labels.
- [x] **BKG-010** (`P0`): Implement `transcript` worker stage with 12s interval + 3s jitter pacing and 429 circuit breaker.

### Phase 3: Structured Summary Generation & Admission
- [x] **BKG-011** (`P0`): Create Alembic migration for `summary_runs` table with JSONB `structured_summary`.
- [x] **BKG-012** (`P0`): Implement single-call 9-section summary generation with SGLang JSON schema and reasoning effort levels (`disabled`, `low`, `medium`, `xhigh`).
- [x] **BKG-013** (`P1`): Implement quote containment validator and separate reasoning output capture in `services/summary_service.py`.
- [x] **BKG-014** (`P0`): Implement `summarize` worker stage with batch generation lease admission (max 2) and interactive reservation (1 slot).

### Phase 4: Batched Embeddings & Unified Index
- [x] **BKG-015** (`P0`): Implement Nomic batch packing ($\le 32$ sequences, $\le 8,192$ aggregate tokens) in `services/embedding_service.py`.
- [x] **BKG-016** (`P0`): Create Alembic migration for `content_chunks` table with pgvector HNSW and GIN tsvector indexes.
- [x] **BKG-017** (`P1`): Implement dual-write bridge to update both `content_chunks` and legacy vector tables.

### Phase 5: Stateful Chat, Hybrid Retrieval & Model Registry
- [x] **BKG-018** (`P0`): Create Alembic migration for `conversations`, `conversation_messages`, and Model Registry tables.
- [x] **BKG-019** (`P0`): Implement `RetrievalService` with hybrid vector + FTS search, RRF fusion, source diversity, and parent expansion.
- [x] **BKG-020** (`P0`): Implement `ModelRegistryService` with `/v1/models` discovery, qualification test runner, and runtime pool enforcement.
- [x] **BKG-021** (`P0`): Update `blueprints/chat.py` with multi-turn history, typed SSE streaming, and interactive lease priority.

### Phase 6: Next.js Modern Frontend UX
- [x] **BKG-022** (`P0`): Implement 9-section summary navigation with sticky TOC and scroll-spy (`SummaryNavigation.tsx`).
- [x] **BKG-023** (`P0`): Implement `ChapterTimeline.tsx` and `EvidenceDrawer.tsx` linking to YouTube playback timestamps.
- [x] **BKG-024** (`P0`): Implement `ThinkingBlock.tsx` (collapsed by default with raw/formatted toggle) and `ReasoningSelector.tsx`.
- [x] **BKG-025** (`P1`): Implement Admin Model Registry UI (`/admin/models/page.tsx` and `ModelRegistryAdmin.tsx`).

### Phase 7: Autoscaling, Evaluation, Redis Removal & Cutover
- [x] **BKG-026** (`P0`): Configure stage worker Compose services and scale-to-zero host queue polling script (`scripts/scale_workers.sh`).
- [x] **BKG-027** (`P0`): Run evaluation corpus benchmark across 4 reasoning levels (`tests/evaluation/test_quality_corpus.py`).
- [x] **BKG-028** (`P0`): Switch `ASYNC_PIPELINE_ENABLED=true` and `AI_MODEL_REGISTRY_ENABLED=true` by default, complete PostgreSQL worker pipeline migration.

---

## 3. Technical Debt & Cleanups

- **DEBT-001** (`Low`): Remove SQLite in-memory mock fallback in production code once PostgreSQL pgvector test harness is unified in CI.
- [x] **DEBT-002** (`Medium`): Refactor frontend monolithic summary render into isolated, memoized sub-components.
- [x] **DEBT-003** (`High`): Clean up remaining references to `task_store` across legacy blueprints once worker migration is complete.
- **DEBT-004** (`Low`): Consolidate duplicate prompt constants between `prompts.py` and `services/contracts.py`.
