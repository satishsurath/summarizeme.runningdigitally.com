# SummarizeMe Issue Tracker and Implementation Backlog

This is the authoritative local tracker for product, AI, data, concurrency, and
operational gaps discovered in SummarizeMe. A checked-in class or component is
not considered complete until it is wired into the user-visible path and its
acceptance criteria are verified.

## Audit record

- **Audit date:** 2026-08-27
- **Repository:** `summarizeme.runningdigitally.com`
- **Branch / commit reviewed:** `feat/ai-architecture-phase0` / `d32c268`
- **Live surface reviewed:** the local Next.js application at
  `http://localhost:3000/`, including Home, channel/video chat, summaries,
  transcripts, Status, Admin, and the hidden `/admin/models` route
- **Source reviewed:** Next.js UI and API client, Flask routes, model registry,
  summary and embedding services, retrieval, workers, queue/admission services,
  migrations, Compose, autoscaling script, tests, CI, and architecture documents
- **User evidence:** three screenshots supplied with this audit
- **Runtime boundary:** read-only browser and local API inspection only. No YouTube
  acquisition or Nemo generation/embedding workload was invoked.

### Status meanings

- **Open:** confirmed defect or missing capability with no adequate implementation.
- **Partial:** useful scaffolding exists, but the end-to-end acceptance criteria are
  not met.
- **Blocked:** implementation cannot proceed without an external decision or
  dependency.
- **Resolved:** acceptance criteria were verified on the real user path; the mere
  presence of code or a mocked test does not qualify.

## Active issue inventory

| ID | Severity | Issue | Status | Primary area |
|---|---|---|---|---|
| PT-013 | High | Chat cannot select Transcript and still exposes legacy summary-source choices | Resolved | Chat UX / grounding |
| PT-014 | High | Model choices are stale, hardcoded, and bypass the registry | Resolved | Model selection |
| PT-015 | High | Reasoning level and persisted per-operation preference are absent from the live UX | Resolved | Reasoning UX |
| PT-016 | High | Chat is stateless and streams an obsolete, untyped protocol | Resolved | Chat architecture |
| PT-017 | High | Admin does not expose model management; hidden model screen is not functional management | Resolved | Admin UX |
| PT-018 | Critical | Model registry lacks safe lifecycle, qualification, profiles, and enforcement | Resolved | Model control plane |
| PT-019 | High | Structured nine-section summary viewer is unwired and contract-incompatible | Resolved | Summary UX |
| PT-020 | Critical | Invalid or weakly grounded structured summaries can be persisted as completed | Resolved | AI trust / evidence |
| PT-021 | High | Long transcripts have no token-aware hierarchical summarization path | Resolved | Summarization |
| PT-022 | High | Transcript timestamps and speakers are discarded from the user experience | Resolved | Transcript UX |
| PT-023 | Critical | Embeddings are JSON, with no real pgvector or full-text index implementation | Resolved | PostgreSQL / retrieval |
| PT-024 | Critical | Retrieval performs brute-force scoring in application memory | Resolved | RAG performance |
| PT-025 | Critical | Embedding batching can violate the documented Nemo hard limits | Resolved | Nemo capacity safety |
| PT-026 | High | Durable PostgreSQL jobs are invisible on the Status screen | Resolved | Operations UX |
| PT-027 | High | Redis and daemon-thread task execution remain in active paths | Resolved | Runtime architecture |
| PT-028 | Critical | Scale-to-zero controller is unsafe and cannot provide the planned parallelism | Resolved | Autoscaling |
| PT-029 | High | Worker DB connection budgets and job/resource lease heartbeats are incomplete | Resolved | Concurrency safety |
| PT-030 | High | YouTube concurrency limit is configured but not enforced cross-process | Resolved | External rate limiting |
| PT-031 | High | Qwen model identifiers drift across UI, APIs, and Compose services | Resolved | Configuration |
| PT-032 | High | One-hundred-video batch workflow lacks usable selection, progress, retry, and cancellation | Resolved | Batch UX |
| PT-033 | High | Custom Markdown/SVG sanitization is overly permissive and untested | Resolved | Frontend security |
| PT-034 | High | Tests and the former tracker create false confidence about end-to-end completion | Resolved | Verification |
| PT-035 | Medium | Core UI errors are swallowed and navigation is inconsistent | Resolved | General UX |
| PT-036 | Medium | Authorization is inconsistent across read APIs and Next.js admin routes | Resolved | Authorization |

## Detailed active issues

### PT-013 — Chat cannot select Transcript and still exposes legacy summary-source choices

**Problem:** The agreed chat grounding choices are not available. Both channel and
video chat expose only `Comprehensive Notes`, `Concise Summary`, `Key Topics`, and
`Important Takeaways`. The user cannot explicitly ground a question in the
transcript, and the labels are tied to the legacy four-summary data model.

**Evidence:** Reproduced in the live UI and supplied screenshot. Options are
hardcoded in `frontend/src/app/chat/channel/[channelName]/page.tsx` and
`frontend/src/app/chat/video/[videoId]/page.tsx`. The backend already recognizes a
`transcript` source, so the visible client and server capabilities disagree.

**Required fix:** Replace the duplicated hardcoded lists with a shared source
contract. Provide `Automatic` as the recommended default plus explicit
`Transcript`, structured-summary sections, and other supported indexed sources.
Show the chosen source in responses and make unavailable sources visibly disabled
with an explanation.

**Acceptance:** Transcript can be selected on both chat screens; the request carries
the selected source; the response identifies the actual sources used; channel and
video behavior have functional tests.

### PT-014 — Model choices are stale, hardcoded, and bypass the registry

**Problem:** Chat advertises Qwen 3.6 35B and Qwen 2.5 72B even though the live
`/api/models` response reports Qwen 3.8 27B. A registry cannot be authoritative
while clients maintain independent lists and defaults.

**Evidence:** Reproduced in the live UI and supplied screenshot. Hardcoded model
lists and Qwen 3.6 defaults exist in both chat pages and
`frontend/src/lib/api.ts`. `/api/models` returned only
`nemo-qwen3.8-27b-nvfp4` during the audit.

**Required fix:** Populate every model selector from the enabled, qualified models
returned by the registry for that operation. Resolve removed or unhealthy saved
choices safely, display availability, and eliminate frontend model constants.

**Acceptance:** Adding, disabling, or changing a registry model changes all relevant
selectors without a frontend build; only operation-compatible qualified models can
be submitted; stale preferences fall back visibly and deterministically.

### PT-015 — Reasoning level and persisted per-operation preference are absent from the live UX

**Problem:** Users cannot choose the model-supported reasoning level. The agreed
behavior—user agency, Medium on first use, then last-used per user and operation—is
not connected to chat or summary actions. Thinking content is not reliably separate
or collapsed by default.

**Evidence:** No reasoning control appears in the live chat, summary, or batch UI.
`ReasoningSelector.tsx` is unused. The client does not send `reasoning_effort` or
read/write operation-scoped preferences. `ThinkingBlock.tsx` expands automatically
while streaming. The preference API and schema store one global choice rather than
independent chat/summary choices.

**Required fix:** Wire a capability-aware reasoning selector into interactive chat,
single summary, and batch summary actions. Persist last-used preferences per user,
operation, and compatible model. Keep reasoning in a separate disclosure that is
collapsed by default, including during streaming.

**Acceptance:** A new user sees Medium; a changed selection survives reload for the
same operation without overriding other operations; unsupported levels cannot be
submitted; thinking is available but collapsed by default and never mixed into the
answer.

### PT-016 — Chat is stateless and streams an obsolete, untyped protocol

**Problem:** The conversation tables and typed event schemas are scaffolding only.
The live client sends only the newest question, messages are local component state,
and the route returns legacy generic deltas. Reasoning and answer text are separated
with heuristics instead of protocol guarantees.

**Evidence:** `blueprints/chat.py` does not persist or load conversation history and
does not use the typed stream event contracts in `services/contracts.py`.
`frontend/src/lib/api.ts` understands only the legacy delta/answer shapes and sends
no `conversation_id`. The `/api/conversations` endpoints are not used by either chat
page.

**Required fix:** Make conversations durable, enforce ownership, include bounded
history, and stream typed events such as `reasoning_delta`, `answer_delta`,
`sources`, `usage`, `error`, and `done`. Add reconnect/idempotency behavior and use
explicit protocol fields rather than parsing `<think>` markers.

**Acceptance:** Reloading resumes the same conversation; follow-up questions use
prior turns; reasoning, answer, citations, usage, error, and completion are distinct
events; both chat scopes have end-to-end streaming tests.

### PT-017 — Admin does not expose model management; hidden model screen is not functional management

**Problem:** The visible Admin page manages only channels. `/admin/models` exists
but has no navigation entry and presents a largely static display rather than the
model management capability previously agreed.

**Evidence:** Reproduced in the live Admin page and supplied screenshot.
`frontend/src/app/admin/page.tsx` contains channel actions only.
`ModelRegistryAdmin.tsx` hardcodes Nemo endpoint addresses, pool values, `Online`,
and `Qualified` badges, and offers only a probe action.

**Required fix:** Add a clear Models section to Admin and implement accessible,
truthful list/add/edit/discover/probe/qualify/enable/disable/profile workflows.
Display real health and qualification evidence, confirmation for impactful changes,
and clear failure feedback.

**Acceptance:** An authorized admin can manage the model lifecycle without editing
environment files; status badges derive from server state; a newly enabled qualified
model appears in the correct user selectors; unauthorized users cannot see or call
the controls.

### PT-018 — Model registry lacks safe lifecycle, qualification, profiles, and enforcement

**Problem:** The backend registry is an environment bootstrap and listing layer, not
an authoritative model control plane. Arbitrary requested or stored model IDs and
reasoning values can bypass the intended compatibility and safety checks.

**Evidence:** `services/model_registry.py` implements environment bootstrap, list,
raw probe, and global preferences. It has no complete CRUD lifecycle, capability
discovery, supported-effort validation, qualification suite, enable gate, health
history, operation profiles, secret references, or audit trail. Registry pool
values do not control `ResourceAdmission`, and `AI_MODEL_REGISTRY_ENABLED` is not a
meaningful cutover switch.

**Required fix:** Define model deployments, capabilities, supported reasoning
levels, health, qualification runs/results, operation profiles, resource class,
enabled state, secret references, and audited admin mutations. Resolve every AI
request through an operation profile and reject unqualified/incompatible choices.

**Acceptance:** No request can invoke an unregistered, disabled, unqualified, or
operation-incompatible model; qualification exercises structured output, streaming,
context, reasoning, and embeddings as applicable; changes are audited; admission
limits use the active profile.

### PT-019 — Structured nine-section summary viewer is unwired and contract-incompatible

**Problem:** Users still receive the legacy four-summary presentation rather than
the deterministic nine-section contract. The newer viewer components are not on the
route used by the application and do not match the backend JSON shape.

**Evidence:** `blueprints/main.py` exposes legacy `SummariesV2`, and
`frontend/src/app/summaries/[id]/page.tsx` renders the legacy view.
`SummaryViewer.tsx` is unused. Its topics expect fields such as `topic`,
`importance`, and `bullets`, while the backend emits `title`, `supporting_points`,
`summary`, and `key_points`. It merges required sections and numbers model
reasoning as section 9 even though evidence references are the required ninth
section and thinking must remain separate.

**Required fix:** Establish one versioned generated client contract and route the
summary page to it. Render all nine sections—executive overview, thesis, topics,
timeline, facts, decisions/actions, glossary, open questions/caveats, and timestamped
evidence—with sticky navigation. Present thinking separately, collapsed by default.

**Acceptance:** A completed `SummaryRun` renders without field adapters or missing
sections; navigation and timestamp links work on desktop and mobile; invalid/legacy
records have an explicit migration or fallback state; contract tests prevent drift.

### PT-020 — Invalid or weakly grounded structured summaries can be persisted as completed

**Problem:** Evidence integrity and quote-containment failures are logged as warnings
but the run can still be marked completed. The implemented timestamp validator is
not part of the completion gate, and there is no bounded corrective retry.

**Evidence:** `services/summary_service.py` logs validation failures before writing
a completed `SummaryRun`. Timestamp validation is defined but not invoked in the
generation path. The model supplies its own `youtube_url`, which the viewer trusts,
instead of the application deriving the link from video identity and validated
timestamps.

**Required fix:** Validate schema, section completeness, quote containment,
timestamp ranges, evidence-to-transcript grounding, and URL derivation before
completion. Run one bounded correction pass with validation feedback; otherwise
persist an explicit failed/review-required state and retain diagnostics.

**Acceptance:** A summary with an invented quote, impossible timestamp, wrong video
URL, missing section, or malformed evidence cannot be marked completed; valid
summaries pass a deterministic validator; correction behavior and failure states
have tests.

### PT-021 — Long transcripts have no token-aware hierarchical summarization path

**Problem:** The service sends the entire transcript in one generation call. Long
videos can exceed the real context or output budget, fail unpredictably, or degrade
quality. The database transaction/session is also held across external inference.

**Evidence:** `services/summary_service.py` has no model tokenizer-based ceiling,
map/reduce hierarchy, continuation strategy, or checkpointed intermediate artifacts.
The generation call occurs while the worker owns the same SQLAlchemy session used
for persistence.

**Required fix:** Estimate with the deployed tokenizer, reserve prompt/output
headroom, and choose single-pass only when safe. For oversized inputs, summarize
timestamp-aligned chapters in parallel within Nemo admission limits, then synthesize
the deterministic contract. Commit/checkpoint around external calls rather than
holding an open transaction.

**Acceptance:** Representative short and oversized transcripts complete without
context overflow; hierarchy preserves evidence provenance; retries resume from
checkpointed work; no DB transaction is held during model inference.

### PT-022 — Transcript timestamps and speakers are discarded from the user experience

**Problem:** Timestamped segments may exist in the database, but users see an
untimestamped text blob split into arbitrary 3,000-character blocks. The output is
hard to navigate, cite, inspect, or export and visible words can run together.

**Evidence:** The transcript API returns `transcript_no_ts`. The Next.js transcript
page applies character slicing and does not render segment time ranges or speaker
labels. The live page showed very large paragraphs and collapsed word spacing.

**Required fix:** Return paginated transcript segments with start/end times and
speaker where available. Render searchable timestamp rows, clickable YouTube links,
copy/export controls, and accessible virtualized navigation for long transcripts.

**Acceptance:** The displayed text preserves word boundaries; every available
segment timestamp is visible and seekable; search and deep links work; large
transcripts remain responsive; plain-text and timestamped export are available.

### PT-023 — Embeddings are JSON, with no real pgvector or full-text index implementation

**Problem:** The documented PostgreSQL hybrid index is not implemented. Embeddings
stored as JSON cannot use vector operators or HNSW, and no generated/search vector
with a GIN index supports full-text retrieval.

**Evidence:** `db/models.py` and the migration define `ContentChunk.embedding` as
JSON. The migration does not create `vector(768)`, HNSW, `tsvector`, or GIN indexes,
despite BKG-016 formerly being checked complete.

**Required fix:** Add a PostgreSQL/pgvector migration with the exact 768-dimensional
type, appropriate cosine index, normalized full-text column/index, embedding model
and version metadata, and a safe backfill/cutover/rollback plan.

**Acceptance:** `EXPLAIN` on representative vector and text queries uses the intended
indexes; dimensions are constrained; backfill is resumable and observable; real
PostgreSQL integration tests cover migration and query behavior.

### PT-024 — Retrieval performs brute-force scoring in application memory

**Problem:** Each query loads as many as 5,000 rows and JSON embeddings, computes
cosine and word overlap in Python, then sorts in memory. This defeats the performance
and scale goals and produces only a superficial approximation of hybrid retrieval.

**Evidence:** `services/retrieval.py` performs the bounded table load, embedding
deserialization, scoring, and sort in the application. It lacks database vector/FTS
queries, rank fusion, score thresholds, source diversity, parent expansion, and a
model-aware context token budget. A DB session remains involved while query
embedding is requested.

**Required fix:** Execute vector and FTS candidate searches in PostgreSQL, fuse ranks
deterministically, deduplicate/diversify sources, expand parents as needed, apply
quality thresholds, and pack context to the chosen model's token budget. Release DB
work before external embedding calls.

**Acceptance:** Query plans use indexes; retrieval latency and memory remain bounded
as the corpus grows; result provenance and scores are inspectable; evaluation covers
recall, grounding, diversity, and empty/low-confidence behavior.

### PT-025 — Embedding batching can violate the documented Nemo hard limits

**Problem:** The active batcher can submit up to 32 sequences while configuration
and the architecture's Nemo constraint specify a maximum of 8 sequences and 8,192
aggregate tokens with one embedding request in flight. Individual oversize inputs
are not safely rejected or split.

**Evidence:** `app_config.py` defines `EMBED_MAX_SEQUENCES=8`, but
`services/embedding_service.py` hardcodes 32 and its unit tests assert 32. Token
counts use a `characters / 4` estimate, and no-segment fallback embeds only the first
1,500 transcript characters. Configuration is therefore disconnected from the
actual request boundary.

**Required fix:** Treat the documented Nemo limits as hard runtime admission values,
use a compatible tokenizer or conservative validated accounting, split/reject an
oversize item deterministically, enforce aggregate limits and one in-flight request
across processes, and never silently truncate content.

**Acceptance:** Tests prove no emitted batch exceeds configured sequence or token
limits, including Unicode and single-oversize cases; live qualification verifies the
deployed embedding endpoint's exact limit and 768 dimensions; full transcripts are
covered without silent truncation.

### PT-026 — Durable PostgreSQL jobs are invisible on the Status screen

**Problem:** New worker jobs and the user-visible Status page use different sources
of truth. A large batch can run while Status reports no tasks.

**Evidence:** The live `/api/active-tasks` and `/api/all-tasks` responses were empty.
Those routes and the Status client use legacy `TaskStore`/Redis data, while channel
start and summarize can enqueue PostgreSQL `JobQueue` records. The UI also assumes
legacy status names and timestamp shapes.

**Required fix:** Expose authorized job/work-item progress from PostgreSQL with
stage, counts, timestamps, retry/error information, throughput, and cancellation
state. Make Status and inline batch progress use this single API.

**Acceptance:** A queued 100-video job appears immediately, updates through each
stage, survives restarts, exposes retryable failures, and reaches a truthful terminal
state; pagination and authorization are tested.

### PT-027 — Redis and daemon-thread task execution remain in active paths

**Problem:** The intended PostgreSQL-only cutover is incomplete. Channel refresh
still starts a daemon thread and writes to `TaskStore`; Redis remains a deployed app
dependency and can consume memory while idle.

**Evidence:** Refresh routes use `TaskStore` plus daemon threads even when the async
pipeline is enabled. `docker-compose.dev.yml` and production Compose still define
Redis, app dependencies, and a memory allowance. `TaskStore` is instantiated at
import time and has an in-memory fallback. This contradicts PT-009/BKG-028's former
resolved state.

**Required fix:** Move every acquisition, refresh, summarize, embedding, retry, and
status path to PostgreSQL jobs/work items. Remove runtime Redis dependencies and
daemon execution after a tested compatibility cutover; fail clearly if the durable
queue is unavailable.

**Acceptance:** No application path imports or writes `TaskStore`; Compose starts
without Redis; restart tests prove jobs are durable and not duplicated; idle memory
measurements exclude Redis.

### PT-028 — Scale-to-zero controller is unsafe and cannot provide the planned parallelism

**Problem:** The scaling script neither computes desired per-stage replicas nor
protects in-flight work. It can treat DB errors as an empty queue and stop all
workers, while production Compose normally keeps all workers running permanently.

**Evidence:** `scripts/scale_workers.sh` queries `pending` and nonexistent `running`
statuses, missing actual `retry` and `leased` records. On a query error it substitutes
zero. It only starts one copy of each service and stops every worker without checking
active leases. No checked-in systemd unit/timer invokes it. Production worker
services use `restart: unless-stopped` and do not idle-exit.

**Required fix:** Implement a fail-safe controller that derives stage-specific
desired replicas (including the planned 0–2 generation workers and Nemo admission
ceiling), distinguishes pending/retry/leased work, refuses scale-down on DB ambiguity,
drains workers, and preserves active leases. Install/document one real scheduler or
use a self-idling worker design.

**Acceptance:** A 100-item test scales out to allowed parallelism, never exceeds
Nemo/resource/external limits, drains safely, reaches zero when idle, wakes for new
work, and survives controller/DB failure without killing active jobs. Idle and load
memory are measured.

### PT-029 — Worker DB connection budgets and job/resource lease heartbeats are incomplete

**Problem:** Multiple API and worker processes use default SQLAlchemy pooling rather
than an explicit global connection budget. Workers claim leased work but do not
renew job or resource leases during long external operations.

**Evidence:** The common engine is created with default pool behavior across process
types. `JobQueue.renew` exists, but the worker loop does not call it, and acquired
resource leases have no long-operation renewal path. External calls can outlive lease
TTL while the process still works.

**Required fix:** Configure role-specific small pools and timeouts within a documented
PostgreSQL connection budget. Heartbeat both job and resource leases independently
of the work call, use ownership tokens, and fence late results after lease loss.

**Acceptance:** Maximum replicas remain within the connection budget; a task longer
than the lease TTL is not reclaimed while healthy; a killed worker is reclaimed once;
late/fenced workers cannot commit; concurrency tests cover these cases.

### PT-030 — YouTube concurrency limit is configured but not enforced cross-process

**Problem:** Start pacing is reserved, but the configured maximum in-flight YouTube
requests is not acquired as a durable cross-process concurrency lease. Parallel
transcript workers can therefore exceed the agreed external-call boundary.

**Evidence:** The transcript worker calls the pacing reservation but does not acquire
the YouTube concurrency resource. The configured maximum of two is not enforced by
the active acquisition path. Some error/429 cases can degrade into empty transcript
or no-captions behavior rather than a retryable external-limit state.

**Required fix:** Combine durable concurrency admission with global start pacing,
jitter, Retry-After handling, bounded exponential backoff, and an explicit circuit
breaker. Classify no-caption, unavailable/private, quota/rate-limit, and transient
network outcomes separately.

**Acceptance:** Multi-process tests prove at most two acquisitions in flight and the
minimum global start interval; 429s pause new starts and retry durably; terminal
content conditions are distinguishable from transient failures.

### PT-031 — Qwen model identifiers drift across UI, APIs, and Compose services

**Problem:** The live deployment has several simultaneous default-model truths,
causing selectors and operation paths to disagree.

**Evidence:** The registry and `app_config.py` report Qwen 3.8 27B, chat and shared
client code show Qwen 3.6/Qwen 2.5, the production app Compose environment still
contains Qwen 3.6, and worker configuration contains Qwen 3.8. The Videos page also
displays a Qwen 3.6 model pill.

**Required fix:** Remove image/build-time model defaults from user-facing clients
and operation code. Bootstrap the registry once, then resolve served IDs and labels
through enabled operation profiles. Add startup diagnostics for conflicting legacy
variables until they are deleted.

**Acceptance:** A repository search finds no active hardcoded legacy model choice;
all processes resolve the same profile; qualification proves the exact served ID;
UI and recorded runs show the actual model used.

### PT-032 — One-hundred-video batch workflow lacks usable selection, progress, retry, and cancellation

**Problem:** The batch interface does not make the performance-oriented workflow
operable. Selection is limited to the current 50-item page, and the user cannot
choose all matching/missing items or understand stage-level progress and capacity.

**Evidence:** The Videos page uses `pageSize=50`, current-page select-all, generic
spinners, and `window.open` actions. It has no model/reasoning selection, all-results
selection, missing-summary filter, per-stage progress, retry, cancel, ETA/throughput,
or clear partial-failure handling.

**Required fix:** Add server-side filtered selection (`all matching`, `missing`,
explicit), batch model/reasoning confirmation, a durable job detail view, stage and
item counts, concurrency/capacity explanation, safe cancellation, retry-failed, and
links to completed artifacts.

**Acceptance:** A user can submit and monitor 100 videos without selecting pages one
by one; the UI remains responsive; progress matches PostgreSQL work items; partial
failures are actionable; cancellation stops unclaimed work and drains claimed work.

### PT-033 — Custom Markdown/SVG sanitization is overly permissive and untested

**Problem:** AI-generated Markdown is rendered through custom sanitation logic whose
attribute policy permits all attributes for allowed tags without an explicit tag
map. Broad SVG and data-image handling increases the XSS and deceptive-content
surface.

**Evidence:** `frontend/src/lib/sanitize.ts` accepts an attribute whenever a tag has
no explicit allowlist entry, and permits SVG/data-image content. The new AI viewers
and their renderer have no focused adversarial security tests.

**Required fix:** Prefer a maintained, configured sanitizer or implement strict
tag/attribute/protocol allowlists. Remove dangerous SVG/event/style/URL behaviors,
derive YouTube links in the application, and test malicious model output.

**Acceptance:** A security test corpus blocks scripts, event handlers, unsafe URLs,
SVG payloads, CSS injection, encoded bypasses, and untrusted data URIs while retaining
required Markdown; dependency/security review is documented.

### PT-034 — Tests and the former tracker create false confidence about end-to-end completion

**Problem:** Many Phase 5–7 items were marked complete because files or mocked tests
exist, although the live paths remain legacy or disconnected. The evaluation suite
does not measure the deployed Nemo model or performance objectives.

**Evidence:** `tests/evaluation/test_quality_corpus.py` returns the same mocked fixture
for four reasoning labels and does not test live quality, latency, TTFT, context,
grounding, or coexistence. Chat route tests assert the legacy stream. Frontend tests
target Flask templates/static assets rather than Next.js behavior. CI type-checks and
builds Next.js but has no functional browser suite. The former tracker marked all
BKG-001 through BKG-028 complete.

**Required fix:** Separate unit/schema tests from PostgreSQL integration, Next.js
component/functional tests, browser E2E, and explicitly gated Nemo qualification and
performance runs. Require evidence for each acceptance criterion and keep tracker
states aligned with the live route.

**Acceptance:** Critical user journeys have automated functional coverage; real
PostgreSQL verifies queue/vector behavior; an opt-in live Nemo suite records model,
hardware, reasoning, TTFT, latency, quality, and limit compliance; tracker closeouts
link to dated evidence.

### PT-035 — Core UI errors are swallowed and navigation is inconsistent

**Problem:** Several pages silently ignore request failures, leaving empty or stale
states indistinguishable from success. Deep pages often offer only a Home link and
native controls/layouts vary between screens.

**Evidence:** Empty `catch` or equivalent paths occur in core Next.js screens,
including status/admin flows. During audit, the user-visible model screen displayed
confident status labels that were not backed by the API. Chat select menus use native
controls with awkward clipping/spacing, as visible in the supplied screenshots.

**Required fix:** Standardize loading, empty, degraded, permission, and retryable
error states; use shared navigation/breadcrumbs and accessible form controls; add
responsive/focus/keyboard review for the core flows.

**Acceptance:** API failures produce actionable non-secret errors; permission errors
are distinct from empty data; all core screens are keyboard usable and responsive;
navigation does not require returning Home between related tasks.

### PT-036 — Authorization is inconsistent across read APIs and Next.js admin routes

**Problem:** Some data/status routes lack explicit role decorators, and Next.js admin
screens are not themselves role-gated. Relying on scattered downstream failures
creates accidental exposure and poor user feedback.

**Evidence:** Read routes including channel video data, individual summaries, and
all-task data do not consistently apply the same role boundary as protected mutation
routes. `/api/vllm/models` exposes raw served-model records to general members.
Next.js admin pages render before protected calls fail, often silently.

**Required fix:** Define a route authorization matrix for member/admin ownership and
apply it centrally. Gate admin navigation/pages and APIs, minimize model/runtime
metadata exposed to members, and return consistent 401/403 behavior.

**Acceptance:** Automated authorization tests cover every API and page role; users
cannot access another user's conversation/artifact; non-admins cannot view or mutate
admin state; the UI renders a clear access-denied state.

## Historical tickets and corrected status

The following records predate this audit. Statuses were corrected where the current
live route regressed or only partial scaffolding exists.

| ID | Historical issue | Corrected status | Follow-up |
|---|---|---|---|
| PT-001 | Summarization vLLM reasoning failure | Partial | PT-016, PT-020 |
| PT-002 | Chat model selector | Regressed | PT-014, PT-031 |
| PT-003 | `youtu.be` URL recognition | Resolved | — |
| PT-004 | Database persistence on rebuild | Resolved | — |
| PT-005 | Chat embedding endpoint failure | Resolved for original incident | PT-024, PT-025 cover current architecture |
| PT-006 | Branch protection/status checks | Resolved for original incident | PT-034 covers product verification |
| PT-007 | Thinking block mixed into answer | Partial | PT-015, PT-016 |
| PT-008 | Model identifier drift | Regressed | PT-031 |
| PT-009 | Daemon task store | Partial | PT-027, PT-028 |
| PT-010 | Frontend Docker context | Resolved | — |
| PT-011 | Worker module resolution | Resolved | — |
| PT-012 | Migration idempotency | Resolved | — |

## Corrected implementation backlog

Checked items below are limited to foundations that were found in source and remain
useful. Reopened items require the linked end-to-end issue acceptance criteria.

### Phase 0 — Contracts, configuration, and probes

- [x] **BKG-001** (`P0`): Add the nine-section Pydantic summary/evidence schemas.
- [x] **BKG-002** (`P0`): Add generation and embedding runtime probe primitives.
- [x] **BKG-003** (`P1`): Add architecture feature flags and configuration fields.
- [ ] **BKG-029** (`P0`): Generate and enforce one versioned backend/frontend AI
  contract for summaries, chat events, model capabilities, and sources. See PT-013,
  PT-016, and PT-019.

### Phase 1 — PostgreSQL durable queue and workers

- [x] **BKG-004** (`P0`): Add jobs, work items, resource limits/leases, and external
  rate-limit tables.
- [x] **BKG-005** (`P0`): Implement atomic PostgreSQL work claiming and lease
  recovery primitives.
- [x] **BKG-006** (`P0`): Implement resource admission and start-pacing primitives.
- [ ] **BKG-007** (`P0`): Complete worker heartbeats, lease fencing, graceful drain,
  and connection budgets. See PT-029.

### Phase 2 — Timestamped transcripts and YouTube acquisition

- [x] **BKG-008** (`P0`): Add timestamped transcript segment storage.
- [x] **BKG-009** (`P0`): Add direct caption acquisition and timestamp parsing.
- [ ] **BKG-010** (`P0`): Enforce cross-process YouTube concurrency, pacing,
  circuit breaking, and durable error classification. See PT-030.
- [ ] **BKG-030** (`P1`): Ship timestamped/searchable transcript APIs and UI. See
  PT-022.

### Phase 3 — Structured summary generation

- [x] **BKG-011** (`P0`): Add `summary_runs` and structured-summary persistence.
- [ ] **BKG-012** (`P0`): Complete token-aware single/hierarchical generation with
  operation profiles and checkpointing. See PT-021.
- [ ] **BKG-013** (`P0`): Make evidence, quote, timestamp, URL, and completeness
  validation a completion gate with correction retry. See PT-020.
- [x] **BKG-014** (`P0`): Add summarize-stage admission primitives; runtime safety
  still depends on PT-018, PT-028, and PT-029.

### Phase 4 — Batched embeddings and unified index

- [ ] **BKG-015** (`P0`): Enforce the real Nemo embedding batch/context limits and
  remove silent truncation. See PT-025.
- [ ] **BKG-016** (`P0`): Implement and prove pgvector HNSW plus PostgreSQL FTS/GIN.
  See PT-023.
- [ ] **BKG-017** (`P1`): Build a resumable backfill/dual-write/cutover with model
  versioning and rollback after BKG-016.

### Phase 5 — Stateful chat, hybrid retrieval, and model registry

- [x] **BKG-018** (`P0`): Add conversation and registry foundation tables.
- [ ] **BKG-019** (`P0`): Implement indexed hybrid retrieval, rank fusion, diversity,
  provenance, and token-budget packing. See PT-024.
- [ ] **BKG-020** (`P0`): Complete the authoritative registry lifecycle,
  qualification, profiles, capability validation, and admission integration. See
  PT-018.
- [ ] **BKG-021** (`P0`): Cut chat over to durable multi-turn conversations and typed
  streaming. See PT-013 and PT-016.

### Phase 6 — Next.js product UX

- [ ] **BKG-022** (`P0`): Wire the contract-compatible nine-section summary viewer
  into the real route. See PT-019.
- [ ] **BKG-023** (`P0`): Wire chapter/evidence navigation to validated transcript
  timestamps and application-derived YouTube links. See PT-019, PT-020, PT-022.
- [ ] **BKG-024** (`P0`): Wire operation-aware reasoning selection and a separately
  collapsed thinking disclosure. See PT-015.
- [ ] **BKG-025** (`P0`): Replace the hidden/static model page with a real admin
  management workflow. See PT-017 and PT-018.
- [ ] **BKG-031** (`P0`): Implement the durable 100-video batch control/progress UX.
  See PT-026 and PT-032.

### Phase 7 — Scale-to-zero, cutover, and verification

- [ ] **BKG-026** (`P0`): Implement and install a fail-safe, lease-aware stage
  scaler or self-idling worker design. See PT-028 and PT-029.
- [ ] **BKG-027** (`P0`): Replace fixture-only evaluation with versioned quality,
  grounding, TTFT, latency, throughput, memory, and coexistence evidence on the
  actual Nemo endpoints. See PT-034.
- [ ] **BKG-028** (`P0`): Finish the PostgreSQL-only cutover and remove Redis/daemon
  paths. See PT-026 and PT-027.

## Technical debt

- [ ] **DEBT-001** (`Low`): Remove production SQLite fallbacks after PostgreSQL test
  infrastructure is authoritative.
- [ ] **DEBT-002** (`Medium`): Finish replacing legacy summary rendering rather than
  counting unused components as a refactor. See PT-019.
- [ ] **DEBT-003** (`High`): Remove all `TaskStore`/Redis references after durable
  job cutover. See PT-027.
- [ ] **DEBT-004** (`Low`): Consolidate duplicate prompt and schema constants into
  versioned operation contracts.
- [ ] **DEBT-005** (`High`): Replace permissive custom AI-output sanitation with a
  reviewed and adversarially tested policy. See PT-033.
- [ ] **DEBT-006** (`Medium`): Standardize frontend data fetching, error states,
  navigation, accessibility, and test utilities. See PT-034 and PT-035.

## Recommended fix order

1. **Protect hard runtime and trust boundaries:** PT-025, PT-029, PT-030, PT-020,
   and PT-033.
2. **Create authoritative data/control planes:** PT-023, PT-024, PT-018, PT-031,
   PT-026, and PT-027.
3. **Complete safe parallel execution:** PT-028 and PT-021.
4. **Cut over the product experience:** PT-014, PT-015, PT-016, PT-013, PT-019,
   PT-022, PT-017, and PT-032.
5. **Close verification and consistency gaps:** PT-034, PT-035, and PT-036.

## Closure rule

An item can move to **Resolved** or be checked complete only when all applicable
evidence exists:

1. The implementation is wired into the actual user-visible/API/worker path, not
   merely present in an unused component or service.
2. Focused unit tests pass, plus real PostgreSQL integration tests for database,
   queue, lease, vector, or authorization behavior.
3. Next.js product changes have functional/component coverage and a core browser
   journey; a successful TypeScript build alone is insufficient.
4. Nemo/YouTube/runtime claims are backed by an explicitly authorized, dated live
   check that records exact model IDs, limits, hardware, and relevant measurements.
5. Failure, retry, restart, authorization, accessibility, and observability behavior
   are verified in proportion to risk.
6. Documentation and this tracker are updated with the evidence and any limitations.
