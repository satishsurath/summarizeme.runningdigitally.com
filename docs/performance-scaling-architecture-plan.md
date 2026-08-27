# Performance-First Elastic Processing Architecture Plan

**Status:** Proposed
**Date:** 2026-08-27
**Design depth:** D2 — structural architecture change
**Implementation state:** Planning only; no runtime or schema changes have been made
**Related plan:** `docs/ai-product-and-model-management-architecture-plan.md`

## 1. Decision Summary

SummarizeMe will be redesigned around a durable, PostgreSQL-backed processing
pipeline. Channel discovery will produce independently claimable per-video work
items for transcript acquisition, summarization, and embedding. Stage-specific
workers will process those items concurrently while global admission controls
protect YouTube and the shared Nemo inference services.

The target architecture optimizes for:

- the shortest safe end-to-end processing time for channels containing tens or
  hundreds of videos;
- horizontal and vertical worker scaling;
- interactive chat responsiveness while batch work is active;
- crash-safe, idempotent processing without Redis;
- explicit adherence to the current Nemo generation and embedding envelopes;
- a small idle footprint, including the ability to scale batch workers to zero.

PostgreSQL remains the application database, pgvector store, durable work queue,
and cross-process admission-control authority. Redis will be removed.

The AI product, structured-summary, reasoning, evidence, retrieval, and model
registry contracts are defined in
`docs/ai-product-and-model-management-architecture-plan.md`. This plan governs
how those contracts are scheduled and admitted.

## 2. Goals And Non-Goals

### 2.1 Goals

1. Process independent videos concurrently.
2. Pipeline transcript, summary, and embedding stages instead of waiting for an
   entire channel to finish one stage before starting the next.
3. Support multiple worker processes or containers without duplicate results.
4. Keep all external concurrency within configurable hard limits.
5. Prioritize interactive chat over background summarization.
6. Recover safely from worker crashes, timeouts, and application restarts.
7. Make progress and failure state durable and inspectable.
8. Batch embedding inputs efficiently within the Nomic token and sequence
   envelope.
9. Reduce Qwen work by producing all summary sections in one structured call
   when the transcript fits the model context.
10. Scale batch workers down to zero after an idle interval.
11. Preserve each user's selected reasoning effort while enforcing the same
    global Nemo admission limits.
12. Carry timestamped evidence, model thinking, and versioned structured
    summaries through durable jobs without mixing reasoning into retrieval.

### 2.2 Non-Goals

- Replacing Flask or Next.js solely for throughput. They are not the primary
  processing bottlenecks.
- Adding Kubernetes, Redis, RabbitMQ, Celery, or another standing broker.
- Increasing or reconfiguring Nemo capacity as part of this application change.
- Bypassing YouTube throttling, rotating identities, or using additional source
  addresses to evade rate controls.
- Claiming Nomic workload throughput before a SummarizeMe-specific benchmark.
- Reworking the vector-table layout in the first work-queue delivery slice. The
  target AI architecture uses a unified versioned content index, but migration
  occurs only after retrieval parity, index, and rollback gates pass.
- Automatically granting the API container access to the Docker socket or host
  service manager.
- Downloading, loading, unloading, or restarting Nemo models from the
  SummarizeMe model-registry UI.

## 3. Current-State Constraints And Bottlenecks

### 3.1 Background execution

The API currently starts daemon threads inside the Flask/Gunicorn process. Task
state is stored in Redis with an in-memory fallback. This does not provide a safe
multi-process work-claim contract, durable retries, or scale-to-zero workers.

### 3.2 Transcript acquisition

`youtube_utils.download_channel_transcripts()` loops over every video
sequentially. The host playlist and transcript wrappers use Python's
single-threaded `HTTPServer`, so additional application threads do not create
real transcript concurrency through those wrappers.

The application uses yt-dlp web extraction rather than the quota-metered
YouTube Data API for transcript acquisition. Safe throughput therefore requires
global pacing, jitter, adaptive backoff, and circuit breaking rather than only
an API-key quota counter.

### 3.3 Summarization

The current summarization route:

- accepts no more than 50 video IDs per request;
- processes videos sequentially;
- holds one SQLAlchemy session across long-running model calls;
- divides longer transcripts into approximately 4,000-word chunks;
- makes four sequential Qwen calls per chunk for concise summary, topics,
  takeaways, and comprehensive notes.

For 100 single-chunk videos, the existing shape requires approximately 400
generation calls before retries. Repeatedly prefilling the same transcript also
wastes model capacity.

### 3.4 Embedding

`run_vectorizers.py` submits one chunk per embedding request and processes source
columns serially. Embeddings are built as a separate backfill rather than as an
automatic per-video pipeline stage, so content may remain unavailable to RAG
after its transcript or summary is already stored.

### 3.5 Configuration drift

The application and production Compose file default to
`nemo-qwen3.6-35b-a3b-nvfp4`. Current Homelab authority identifies the active
served model as `nemo-qwen3.8-27b-nvfp4`. The redesigned application resolves
enabled/default models through the qualified database registry, verifies the
served identity at readiness and request time, and fails visibly when the
registry, endpoint, or served identity is incompatible.

## 4. Authoritative Nemo Capacity Boundary

The capacity values in this section are application design inputs, not authority
to change Nemo.

### 4.1 Generation

The current Homelab service page, reviewed 2026-08-27, and completed
CR-2026-0821-14 record the active Qwen3.8 SGLang posture as:

- served model: `nemo-qwen3.8-27b-nvfp4`;
- maximum running requests: `4`;
- maximum prompt plus output per request: `262144` tokens;
- shared token pool: `1114112` tokens;
- ReplaySSM/EAGLE and `qwen3_coder` retained.

An older canonical serving-profile object still describes the superseded
five-stream target. The newer service page and completed four-stream correction
govern this design. The discrepancy should be corrected in Homelab documentation
through separate authorized work; SummarizeMe must not assume five streams.

SummarizeMe will initially allocate no more than:

| Admission class | Default | Purpose |
| --- | ---: | --- |
| Batch summary requests | 2 | Background per-video summaries |
| Interactive reserve | 1 | Video/channel chat |
| SummarizeMe total generation requests | 3 | Leaves one Nemo server slot outside this application's client budget |
| Nemo server hard maximum | 4 | Enforced by the shared Nemo runtime |

The Nemo server remains the final global enforcement point because other
applications also consume it. SummarizeMe admission limits do not claim control
over those consumers.

### 4.2 Embeddings

The Nomic service profile records:

- model: `nemo-nomic-embed-text-v1.5`;
- maximum input context: `8192` tokens;
- maximum sequences: `32`;
- maximum aggregate batched tokens: `8192`;
- output: normalized 768-dimensional vectors;
- caller-provided `search_document: ` and `search_query: ` prefixes.

Protocol and bounded co-residency are proven, but application throughput and
long-input behavior remain unqualified. The embedding batch size is therefore a
measured tuning parameter, not an automatic value of 32.

### 4.3 Canonical Homelab sources

- `Homelab-Documentation/services/ai-inference-and-translation-platform.md`
- `Homelab-Documentation/change-management/2026-08-21-nemo-voice-identity-continuity.md`
- `Homelab-Documentation/ai/objects/serving-profiles/nemo-qwen38-radixark-sglang-262k-replayssm-mtp-five-stream-candidate.md`
- `Homelab-Documentation/ai/objects/serving-profiles/nemo-nomic-embed-text-vllm-8k.md`

## 5. Target Architecture

```text
                              ┌───────────────────────┐
Browser ──► Next.js ──► Flask │ API + interactive chat│
                              └───────────┬───────────┘
                                          │ short transactions
                                          ▼
                              ┌───────────────────────┐
                              │ PostgreSQL + pgvector │
                              │ data + jobs + leases  │
                              └───────────┬───────────┘
                                          │
                 ┌────────────────────────┼────────────────────────┐
                 ▼                        ▼                        ▼
        discovery/transcript       summary workers         embedding workers
             workers                 0..2 replicas             0..1 replica
          0..2 replicas                   │                         │
                 │                        ▼                         ▼
                 ▼                  Nemo Qwen :8000           Nemo Nomic :8001
          YouTube / yt-dlp

                        workers scale to zero when idle
```

### 5.1 Processing DAG

```text
discover_channel
       │
       ├── transcript(video-1) ──┬── summarize(video-1) ──► embed_summary(video-1)
       │                         └── embed_transcript(video-1)
       ├── transcript(video-2) ──┬── summarize(video-2) ──► embed_summary(video-2)
       │                         └── embed_transcript(video-2)
       └── ...

finalize_job runs when all required terminal work items are complete or failed.
```

Downstream items are inserted as soon as their dependency succeeds. This allows
all stages to overlap and makes the first processed videos searchable before the
entire channel finishes.

## 6. PostgreSQL Work Queue Design

### 6.1 `jobs`

One row represents an operator request such as channel download, refresh,
summarization, embedding rebuild, or combined ingest.

Proposed fields:

| Field | Purpose |
| --- | --- |
| `id UUID PRIMARY KEY` | Stable externally visible job ID |
| `job_type TEXT` | `channel_ingest`, `refresh`, `summarize`, `reindex` |
| `status TEXT` | `pending`, `running`, `completed`, `partial`, `failed`, `cancelled` |
| `priority INTEGER` | Job-level scheduling priority |
| `requested_by TEXT` | Authenticated user identity |
| `request_payload JSONB` | Normalized immutable request parameters |
| `idempotency_key TEXT UNIQUE` | Prevent accidental duplicate submissions |
| `total_items`, `completed_items`, `failed_items` | Durable progress counters |
| timestamps | Creation, start, update, and completion times |

### 6.2 `work_items`

One row represents one independently retryable unit.

| Field | Purpose |
| --- | --- |
| `id BIGSERIAL PRIMARY KEY` | Internal work identity |
| `job_id UUID REFERENCES jobs` | Parent request |
| `stage TEXT` | `discover`, `transcript`, `summarize`, `embed_transcript`, `embed_summary`, `finalize` |
| `resource_class TEXT` | `youtube`, `generation`, `embedding`, `control` |
| `item_key TEXT` | Usually the video ID |
| `status TEXT` | `pending`, `leased`, `completed`, `retry`, `failed`, `cancelled` |
| `priority INTEGER` | Stage/item priority |
| `payload JSONB` | Stage-specific input |
| `attempt_count`, `max_attempts` | Retry control |
| `available_at TIMESTAMPTZ` | Scheduled retry/backoff |
| `lease_owner TEXT` | Worker identity |
| `lease_expires_at TIMESTAMPTZ` | Crash recovery |
| `last_error_code`, `last_error_message` | Sanitized diagnostic state |
| timestamps | Creation, claim, update, and completion times |

Required uniqueness:

```text
UNIQUE (job_id, stage, item_key)
```

The uniqueness rule, together with existing source-data constraints, provides
at-least-once execution without duplicate stored results.

### 6.3 Claim operation

Workers claim work using one short transaction shaped like:

```sql
WITH candidate AS (
    SELECT id
    FROM work_items
    WHERE status IN ('pending', 'retry')
      AND available_at <= now()
      AND resource_class = :resource_class
    ORDER BY priority DESC, available_at, id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE work_items wi
SET status = 'leased',
    lease_owner = :worker_id,
    lease_expires_at = now() + :lease_duration,
    attempt_count = attempt_count + 1,
    updated_at = now()
FROM candidate
WHERE wi.id = candidate.id
RETURNING wi.*;
```

No database session or transaction may remain open during YouTube, Qwen, or
Nomic calls.

### 6.4 Lease recovery

- Workers heartbeat only while a long request is demonstrably active.
- Expired leases return to `retry` when attempts remain.
- Ambiguous model timeouts must be reconciled before retrying when a duplicate
  result could be expensive.
- Permanent errors, such as unavailable captions, become terminal item failures.
- A job may complete as `partial` when some videos legitimately cannot be
  processed.

### 6.5 Resource admission

Cross-process limits use PostgreSQL rows and expiring leases rather than local
thread semaphores. The transaction that obtains a work item must also prove
that its resource class has capacity, or release the item immediately.

YouTube start pacing additionally maintains a transactional
`next_allowed_at`/`backoff_until` record shared by all transcript workers.

Proposed persistent controls:

| Table | Key fields | Purpose |
| --- | --- | --- |
| `resource_limits` | `resource_class`, `max_in_flight`, `updated_at` | Configured application ceiling for generation, embedding, and YouTube work |
| `resource_leases` | `resource_class`, `lease_id`, `owner`, `expires_at` | Countable, expiring cross-process capacity claims |
| `external_rate_limits` | `provider_key`, `next_allowed_at`, `backoff_until`, `failure_count` | Global external start pacing and circuit-breaker state |

Lease acquisition locks the applicable limit row, removes expired leases,
counts active leases, and inserts a new lease only when capacity remains. Lease
release is idempotent. Configuration changes cannot raise a limit above the
hard application ceiling compiled or validated for that resource.

## 7. Stage Design

### 7.1 Channel discovery

- Exactly one discovery item runs per job.
- It resolves the immutable playlist/channel identity and video inventory.
- It bulk-inserts idempotent transcript work items.
- Discovery does not download all transcripts itself.
- A 100-video channel is represented by 100 database work items, not a single
  API payload limited to 50 IDs.

### 7.2 Transcript acquisition

Preferred production design:

- Install and invoke yt-dlp directly in the transcript-worker image.
- Do not make the API depend on host-only HTTP wrappers.
- Keep an optional bounded wrapper for local macOS development if still needed.
- If retained, replace `HTTPServer` with `ThreadingHTTPServer` and protect the
  subprocess path with the same global concurrency contract.

Initial admission values:

| Setting | Initial value |
| --- | ---: |
| Maximum transcript subprocesses | 2 |
| Minimum global start interval | 12 seconds |
| Random jitter | 0–3 seconds |
| Initial retry delay | 60 seconds |
| Later retry delays | 5 minutes, then 15 minutes |

The 12-second start interval follows yt-dlp's approximate guest-session posture
of 300 videos per hour. It is a starting guardrail, not a guaranteed YouTube
contract. Two requests may overlap, but the shared start-rate gate prevents
worker count from multiplying the external request rate.

On `429`, temporary-unavailable, CAPTCHA, or equivalent throttling evidence:

1. Open the shared YouTube circuit breaker.
2. Stop new admissions.
3. Apply exponential backoff with jitter.
4. Reduce active concurrency to one.
5. Preserve the exact sanitized failure class for operator visibility.

The design must never rotate accounts, cookies, visitor identities, or source
addresses merely to evade throttling.

Reference:

- <https://github.com/yt-dlp/yt-dlp/wiki/Extractors>
- <https://developers.google.com/youtube/v3/determine_quota_cost>

### 7.3 Summarization

The new summarizer operates at video granularity and implements the canonical
nine-section contract in
`docs/ai-product-and-model-management-architecture-plan.md`:

1. executive overview;
2. main thesis;
3. topics and supporting points;
4. chapter or timeline sections;
5. important facts and technical details;
6. decisions, recommendations, and action items;
7. definitions or glossary;
8. open questions and caveats;
9. timestamped evidence references.

For a transcript that fits within the configured safe input budget, one request
produces the complete validated JSON object. The safe budget reserves system
prompt, instructions, selected reasoning effort, structured output, generation,
and safety headroom beneath the 262,144-token hard limit. Word counts are not
sufficient; the worker must use the serving model's tokenizer or a
conservatively validated compatible tokenizer.

For an oversized transcript:

1. Split on token-aware semantic, speaker, and timestamp boundaries.
2. Extract typed evidence packets within the batch concurrency limit.
3. Synthesize the packets in one final structured request.
4. Validate final evidence IDs against the original transcript spans.

Map outputs are not final summaries and must not be concatenated into user
content. One bounded corrective retry may repair a schema-invalid response; a
second invalid result is an explicit failure.

The immutable work-item payload includes the user's selected reasoning effort.
First use defaults to Medium; later jobs default to that user's last successful
summary choice. Direct, Low, Medium, and Deep all consume the same batch
generation leases. Returned thinking is stored separately from the summary,
shown collapsed by default, and never embedded.

Initial admission values:

```text
GEN_BATCH_CONCURRENCY=2
GEN_INTERACTIVE_RESERVE=1
GEN_APP_MAX_IN_FLIGHT=3
GEN_MAX_REQUEST_TOKENS=262144
```

Interactive requests receive higher priority. When the interactive reserve is
unused, a later measured policy may temporarily lend it to batch work, but the
first implementation should keep the reservation strict.

### 7.4 Embedding

Transcript and summary embeddings become automatic work items rather than a
deployment-time global backfill.

The worker will:

1. Create deterministic sentence-aware chunks.
2. Apply the correct Nomic task prefix.
3. Estimate tokens for every input.
4. Pack a batch with no more than 32 sequences and no more than 8,192 aggregate
   tokens.
5. Submit the input array in one embeddings request.
6. Validate count, dimension, finite values, and normalization.
7. Write the batch in one short database transaction.

Initial application posture:

```text
EMBED_IN_FLIGHT_BATCHES=1
EMBED_MAX_SEQUENCES=8       # initial value; benchmark upward
EMBED_MAX_BATCH_TOKENS=8192 # hard ceiling
```

Benchmark batch sizes 1, 4, 8, 16, and 32. Increase the configured sequence
count only when the exact SummarizeMe workload proves better throughput without
Qwen latency, host-pressure, or embedding-quality regression.

The existing vector tables remain authoritative in the first queue and worker
slices. The accepted target is the unified, versioned `content_chunks` design in
the AI product plan, containing transcript/summary source type, source hash,
model revision, parent section, and timestamp bounds. Migration occurs only
after filtered retrieval quality, hybrid-search behavior, index size, write
amplification, migration correctness, and query latency meet the documented
parity gates. Model thinking is never included in embedding work.

## 8. Worker Processes And Autoscaling

### 8.1 Worker services

Production defines independent worker services:

| Service | Initial maximum replicas | Resource controlled |
| --- | ---: | --- |
| `worker-control` | 1 | discovery/finalization |
| `worker-transcript` | 2 | yt-dlp subprocesses and YouTube pacing |
| `worker-summary` | 2 | Nemo Qwen generation |
| `worker-embedding` | 1 | Nomic packed batches |

Each service uses the same application image where practical, selecting its
resource class through the command line. Development may run one combined
worker for convenience, but production evidence must use the deployed topology.

### 8.2 Scale-up policy

Desired replicas are based on runnable queue depth and capped by the stage's
hard maximum. An initial policy may be:

```text
control:    1 when control work exists, otherwise 0
transcript: min(2, ceil(runnable_transcripts / 10))
summary:    min(2, ceil(runnable_summaries / 5))
embedding:  1 when embedding work exists, otherwise 0
```

Global resource leases remain authoritative even if more containers are
accidentally started.

### 8.3 Scale-to-zero

A small host-side systemd timer may inspect queue depth every 15–30 seconds and
invoke a checksum-controlled Compose scaling script. A timer has no continuously
resident autoscaler process.

Scale-down requirements:

- no runnable work for the stage during the idle grace period;
- no unexpired leases owned by the replica being removed;
- worker stops claiming new work before exit;
- active work drains or its lease is safely relinquished;
- zero replicas after the default five-minute idle grace period.

The Flask API must not mount the Docker socket or receive host service-management
authority. Autoscaling is a separate host integration with a bounded interface.

## 9. Application And Database Runtime

### 9.1 API server

The API is primarily coordinating short database transactions and interactive
streaming. Four independent Gunicorn processes are not required for two users
and complicate local in-memory state.

Initial target:

```text
1 Gunicorn process
4–8 threads, selected through load testing
no batch execution inside the API process
```

### 9.2 Connection pools

Configure pools explicitly rather than relying on one default engine for every
process.

Initial budget:

| Consumer | Suggested pool |
| --- | --- |
| API | `pool_size=5`, `max_overflow=5` |
| Each worker replica | `pool_size=1` or `2`, small overflow |
| Migrations/maintenance | Reserved headroom |
| Total application budget | Keep below approximately 30 connections initially |

No worker may reserve a database connection while waiting for an external
service.

### 9.3 PostgreSQL idle footprint

Postgres remains resident because it owns user data, vectors, queue state, and
the wake-up signal for future work. Start with a modest memory posture, such as
128–256 MB `shared_buffers`, and tune from measured data/index size and query
latency. Compose reservations should represent actual need rather than the old
1-GiB minimum assumption.

PgBouncer is not initially required. Reconsider it only if measured worker
replica counts or connection churn create a real limit.

## 10. API And UI Compatibility

Existing channel, summarize, refresh, and status routes should become adapters
over the durable job model.

Compatibility requirements:

- Existing task IDs may become UUID job IDs without changing the UI concept.
- Status responses continue to expose `status`, `processed`, `total`, and
  errors, with optional stage-level detail.
- Requests may contain more than 50 videos because the server expands work in
  the database rather than retaining the full list inside one background thread.
- Cancelling a job prevents new claims; it does not terminate an ambiguous
  external request unsafely.
- The UI should show per-stage progress and distinguish failed/unavailable
  captions from transient retries.
- Summary requests include the selected model/profile and reasoning effort in
  an immutable normalized payload.
- Chat requests include bounded conversation history and a reasoning choice;
  the backend streams thinking and final-answer events separately.
- The UI restores the last model/reasoning choice for the authenticated user and
  operation, subject to current qualification and enablement.
- Summary pages render the nine-section structured contract, chapter timeline,
  timestamped evidence, versions, and a thinking panel collapsed by default.
- Ordinary users select only qualified models. Model discovery, qualification,
  defaults, and runtime-pool configuration remain admin-only.

Detailed request, artifact, model-registry, and UI contracts are governed by
`docs/ai-product-and-model-management-architecture-plan.md`.

## 11. Reliability And Idempotency

### 11.1 Delivery semantics

The system uses at-least-once work execution with idempotent persistence.
Exactly-once external execution is not assumed.

Required guards include:

- idempotent summary-run identity derived from video, transcript version, model
  profile, reasoning effort, prompt, schema, and sampling configuration;
- unique channel/video associations;
- unique work-item identity per job/stage/video;
- deterministic embedding source and chunk hashes;
- upsert behavior for vector rows;
- retry classification by failure type;
- lease expiry and reconciliation after worker death.

### 11.2 Retry policy

| Failure class | Default treatment |
| --- | --- |
| YouTube throttle/transient network | Delayed retry through shared circuit breaker |
| Captions unavailable/private/deleted | Permanent item failure |
| Qwen explicit 429/5xx before response | Bounded retry with jitter |
| Qwen ambiguous timeout | Reconcile stored result/request state before retry |
| Invalid structured output | One corrective retry, then explicit failure |
| Nomic transient error | Bounded batch retry; split batch if diagnosis requires |
| Database serialization/deadlock | Short bounded transaction retry |
| Worker crash | Lease expiry and reclaim |

Retry storms must not consume every external slot. Retried work has lower
priority than new interactive traffic and may have lower priority than first
attempts.

## 12. Observability And Adaptive Control

Application metrics should expose:

- queue depth and oldest runnable age by stage;
- active leases by resource class;
- job duration and time to first ready video;
- per-stage throughput and p50/p95 latency;
- retry and permanent-failure counts by sanitized reason;
- YouTube start rate, throttle events, and circuit-breaker state;
- Qwen in-flight batch and interactive counts;
- Qwen request prompt/output tokens, TTFT, total duration, and timeout count;
- Qwen reasoning effort, reasoning tokens, first-reasoning/first-answer timing,
  structured-output validation, and corrective-retry count;
- embedding batch items, aggregate tokens, and vectors per second;
- database pool usage and claim latency;
- worker desired/current replica count and idle shutdowns.

Where the private Nemo metrics endpoint is available, batch admission may pause
or contract when server queue depth, TTFT, or host-pressure signals cross a
reviewed threshold. The first implementation must remain correct without
assuming that metrics can identify every external consumer request.

Logs must not include complete transcripts, prompts, responses, bearer values,
model thinking, or user credentials.

## 13. Security Boundaries

- Preserve Cloudflare/JWT authorization at the API boundary.
- Record the authenticated requester on each job.
- Workers receive only the database and external-service credentials required
  by their stage.
- Keep Nemo routes private and use existing credential custody.
- Restrict endpoint/model/profile/runtime-pool administration to administrators.
- Store endpoint secret references rather than plaintext secrets in PostgreSQL.
- Restrict endpoint URLs to approved schemes and networks and perform all model
  discovery and tests server-side.
- Do not publish worker control, queue, or model endpoints publicly.
- Do not mount the Docker socket into API or worker containers.
- Validate channel/video identifiers before including them in subprocess
  arguments.
- Invoke yt-dlp with argument arrays, not shell interpolation.
- Retain sanitized error excerpts with bounded length.
- Treat transcript/retrieved text as untrusted prompt data rather than
  instructions.
- Render thinking and final output through the same maintained safe content
  pipeline while keeping them separate fields.

## 14. Implementation Slices

### Slice 0 — Baseline and contracts

Deliverables:

- Record baseline timings for a small mocked/synthetic batch.
- Freeze job states, stage names, retry classes, and configuration names.
- Add startup model-identity checks.
- Add token-budget calculation and tests for the nine-section summary, evidence,
  reasoning, thinking-stream, and model-profile contracts from the AI product
  plan.

Acceptance:

- Current behavior remains unchanged behind the default-disabled pipeline flag.
- Model drift is reported without exposing credentials.

### Slice 1 — PostgreSQL jobs and worker skeleton

Deliverables:

- Alembic migration for jobs, work items, and resource leases.
- Queue repository/service with atomic claim, heartbeat, completion, retry, and
  expired-lease recovery.
- Worker command supporting one resource class.
- API status compatibility adapter.

Acceptance:

- Multiple workers claim 100 test items with no duplicate successful ownership.
- Worker termination and lease expiry recover safely.
- Queue correctness is validated on disposable PostgreSQL, not SQLite alone.

### Slice 2 — Parallel transcript pipeline

Deliverables:

- Discovery creates per-video transcript items.
- Direct worker-side yt-dlp execution or bounded concurrent wrapper.
- Global start-rate limiter, jitter, backoff, and circuit breaker.
- Idempotent transcript persistence.

Acceptance:

- Two workers overlap slow transcript requests without exceeding the configured
  global start rate.
- Synthetic throttle events stop admission and recover after backoff.
- Existing videos are skipped or associated without duplicate rows.

### Slice 3 — Generation pipeline

Deliverables:

- One-call nine-section structured per-video summary generation.
- Token-aware full-context and hierarchical paths.
- PostgreSQL generation leases with batch and interactive classes.
- Durable result validation and retry classification.
- User-selected reasoning effort in immutable work payloads.
- Separate thinking/final-answer capture and typed stream behavior.

Acceptance:

- No more than two batch calls and three total SummarizeMe generation calls are
  concurrently admitted.
- Interactive chat obtains its reserved capacity during a batch run.
- One ordinary video produces all nine required summary sections in one
  validated request.
- Direct, Low, Medium, and Deep choices use the same admission path and are
  retained in artifact provenance.
- Thinking is stored separately, displayed collapsed by default, and is not
  embedded.
- The request token budget never exceeds the configured hard ceiling.

### Slice 4 — Batched embedding pipeline

Deliverables:

- Automatic transcript and summary embedding work items.
- Token-aware batch packing and vector validation.
- Batched PostgreSQL upserts.
- Compatibility with existing RAG queries and embedding tables.
- Additive preparation for the versioned unified content index defined by the AI
  product plan.

Acceptance:

- No request exceeds 32 sequences or 8,192 aggregate tokens.
- Returned vector count and dimension match the request.
- A completed video becomes searchable without a global backfill command.
- No thinking output is present in the content index.

### Slice 4A — AI experience and model registry

This slice follows the detailed AI Slices D–F in
`docs/ai-product-and-model-management-architecture-plan.md` and may overlap
performance Slice 4 after the generation and embedding contracts stabilize.

Deliverables:

- Nine-section summary navigation, chapter timeline, evidence drawer, versions,
  and collapsed thinking panel.
- Persisted multi-turn chat with separate reasoning/answer streams.
- Admin-managed endpoints, models, operation profiles, shared runtime pools,
  user preferences, and configuration audit records.
- Removal of hard-coded frontend model options and transition of environment
  model IDs to bootstrap-only behavior.

Acceptance:

- Last-used reasoning and qualified model preferences restore per user and
  operation.
- Model discovery cannot bypass qualification or runtime-pool ceilings.
- Summary and chat evidence open the correct timestamped source.
- Thinking remains visible on demand but excluded from retrieval and default
  exports.

### Slice 5 — Autoscaling and idle reduction

Deliverables:

- Stage-specific Compose worker services.
- Read-only queue-depth probe and bounded host-side scaling script.
- systemd timer, idle grace, drain, and lease-safe shutdown behavior.

Acceptance:

- Queue growth scales only the required stage.
- Workers return to zero after the idle grace period.
- Active work is never terminated by ordinary scale-down.
- API and workers have no Docker-socket access.

### Slice 6 — Cutover and Redis removal

Deliverables:

- Enable the PostgreSQL pipeline by default.
- Remove daemon-thread task execution.
- Remove Redis task-store and rate-limit dependencies and Compose service.
- Update architecture, deployment, environment, and recovery documentation.

Acceptance:

- All supported operations use durable jobs.
- Restarting API or workers does not lose job state.
- No Redis runtime dependency remains.
- Rollback to the prior application image/schema compatibility point is
  documented and tested.

## 15. Validation Strategy

### 15.1 Automated tests

- Unit tests for state transitions, retry classification, token packing, and
  rate calculations.
- PostgreSQL integration tests for `SKIP LOCKED`, lease expiry, idempotency,
  constraints, and concurrent writes.
- Mocked external-service tests for YouTube throttling, Qwen failure modes, and
  partial Nomic batches.
- API compatibility tests for submit, status, cancel, and progress responses.
- Load test with two interactive users while background jobs are active.

### 15.2 Controlled performance qualification

Use synthetic/provided transcripts before making live YouTube or Nemo claims.
Live qualification requires separately authorized external calls.

Suggested progression:

1. 3-video canary.
2. 10-video batch with one transcript and one summary worker.
3. 10-video batch with planned concurrency.
4. Nomic batch sweep: 1, 4, 8, 16, 32 sequences within 8,192 tokens.
5. Qwen batch concurrency comparison: 1 versus 2, with an interactive chat
   request injected during the run.
6. 100-video channel only after YouTube pacing and the smaller gates pass.

Measure:

- total completion time;
- time to first searchable video;
- per-stage throughput and queue wait;
- YouTube throttles and retry delay;
- Qwen TTFT, prompt/decode throughput, and interactive latency;
- Nomic vectors per second and Qwen co-residency impact;
- Postgres connection usage, lock wait, and vector-write latency;
- Nemo health, memory-pressure, OOM/Xid/restart, and current hard-cap evidence.

No configured limit is raised merely because a higher value starts successfully.
It must improve end-to-end throughput without violating latency, correctness, or
host-safety gates.

## 16. Rollback Strategy

Each slice remains independently reversible until the final Redis removal.

- Keep the legacy execution path behind a feature flag through Slices 1–5.
- Use additive migrations before destructive schema cleanup.
- Do not delete legacy task/vector data during initial cutover.
- Stop new pipeline submissions before rollback.
- Allow leased work to drain or expire.
- Restore the prior application image and disable the pipeline flag.
- Retain job rows for diagnosis; do not reinterpret them as legacy tasks.
- Database down-migrations must not discard user transcripts, summaries, or
  vectors.

## 17. Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| More workers amplify YouTube requests | Global Postgres pacing and circuit breaker independent of replica count |
| Batch work degrades interactive chat | Strict interactive generation reservation and higher priority |
| Other Nemo consumers consume capacity | Nemo server hard cap plus conservative SummarizeMe client cap and pressure monitoring |
| Worker dies after external success | Idempotent writes, leases, and ambiguous-result reconciliation |
| PostgreSQL becomes connection-bound | Explicit small pools and no connections held across external calls |
| Embedding batches harm Qwen latency | One initial in-flight batch and measured sequence-size sweep |
| Structured response is malformed | Schema validation and one bounded corrective retry |
| Autoscaler kills active work | Drain protocol and lease-aware scale-down |
| Stale model configuration causes failures | Admin-managed discovered/configured/qualified/enabled lifecycle plus served-identity checks |
| Registering multiple models multiplies apparent capacity | All models on an endpoint consume one validated shared runtime pool |
| Deep reasoning unexpectedly degrades batch time | Visible user tradeoff, immutable effort metadata, telemetry, and unchanged global limits |
| Thinking is mistaken for evidence or indexed content | Separate field, collapsed labelling, and explicit prohibition from embeddings/retrieval |
| Unified vector schema reduces filtered recall | Preserve existing tables until retrieval parity and reversible migration support cutover |

## 18. Configuration Contract

Names are provisional but should be frozen before Slice 1 implementation.

```text
ASYNC_PIPELINE_ENABLED=false
AI_MODEL_REGISTRY_ENABLED=false
AI_MODEL_REGISTRY_BOOTSTRAP_FROM_ENV=true

WORKER_LEASE_SECONDS=600
WORKER_IDLE_EXIT_SECONDS=300

YT_MAX_IN_FLIGHT=2
YT_MIN_START_INTERVAL_SECONDS=12
YT_START_JITTER_SECONDS=3

GEN_BATCH_CONCURRENCY=2
GEN_INTERACTIVE_RESERVE=1
GEN_APP_MAX_IN_FLIGHT=3
GEN_MAX_REQUEST_TOKENS=262144

EMBED_IN_FLIGHT_BATCHES=1
EMBED_MAX_SEQUENCES=8
EMBED_MAX_BATCH_TOKENS=8192

# Transitional seeds only while the database registry is empty.
VLLM_GEN_MODEL=nemo-qwen3.8-27b-nvfp4
VLLM_EMBED_MODEL=nemo-nomic-embed-text-v1.5
```

After the registry cutover, enabled models, defaults, reasoning capabilities,
sampling profiles, and runtime-pool assignments are database authority.
Endpoint URLs and secret-reference values may remain bootstrap/runtime
environment configuration. An emergency recovery flag may temporarily restore
bootstrap selection without rewriting historical artifact provenance.

## 19. Acceptance Decisions Required Before Implementation

1. Accept PostgreSQL as the durable queue and pgvector database.
2. Accept one structured Qwen request per ordinary video instead of four
   independent section requests.
3. Accept the initial SummarizeMe generation allocation of two batch slots plus
   one reserved interactive slot.
4. Accept globally paced yt-dlp starts at an initial 12-second interval with two
   possible in-flight subprocesses.
5. Accept stage-specific workers and a bounded host-side timer for scale-to-zero.
6. Accept preservation of the current vector-table layout until performance and
   retrieval benchmarks justify a separate migration.

The accepted AI-product decisions for user-selectable reasoning, last-used
preferences, visible collapsed thinking, the nine-section summary contract, and
admin model management are recorded in Section 18 of
`docs/ai-product-and-model-management-architecture-plan.md` and do not require
re-decision before implementation planning.

After these decisions, implementation should proceed in the vertical slices
above rather than as one all-at-once rewrite.

## Appendix A — Expected Source Boundaries And Call Paths

Names in this section are proposed to make ownership and dependency direction
reviewable before implementation. They may be refined during Slice 0 without
changing the architecture.

### A.1 Proposed modules

| Path | Responsibility |
| --- | --- |
| `db/models.py` | ORM models for jobs, work items, limits, leases, transcript segments, summary runs, conversations, model registry, preferences, and audit records |
| `alembic/versions/*_add_processing_pipeline.py` | Additive queue/admission schema |
| `alembic/versions/*_add_ai_product_contracts.py` | Additive transcript, artifact, conversation, content-index, registry, preference, and audit schema |
| `services/job_queue.py` | Job submission, claims, lease renewal, transitions, progress, and recovery |
| `services/resource_admission.py` | Generation/embedding concurrency and YouTube pacing |
| `services/youtube_acquisition.py` | Discovery and one-video transcript acquisition |
| `services/summary_service.py` | Token budgeting, reasoning profiles, nine-section generation, evidence validation, thinking capture, and hierarchy |
| `services/embedding_service.py` | Timestamp-aware chunk creation, batch packing, embedding validation, versioning, and persistence |
| `services/retrieval_service.py` | Hybrid retrieval, fusion, diversity, confidence, parent expansion, and context packing |
| `services/model_registry.py` | Endpoint discovery, capability qualification, operation profiles, shared runtime pools, and user preference resolution |
| `workers/main.py` | Worker CLI, lifecycle, polling/notification, drain, and idle exit |
| `workers/stages/*.py` | One handler per processing stage |
| `blueprints/api.py` | Submit/cancel/status adapters; no daemon-thread execution |
| `blueprints/chat.py` | Persisted conversation, retrieval, typed reasoning/answer streaming, interactive admission, and priority |
| `blueprints/admin_models.py` | Admin-only endpoint/model discovery, qualification, profile, default, and audit APIs |
| `app_config.py` | Bootstrap endpoints/secrets, validated hard ceilings, and emergency registry recovery behavior |
| `frontend/src/app/admin/models/` | Model registry and qualification UI |
| `frontend/src/app/summaries/[id]/` | Nine-section summary, timeline, evidence, version, and thinking UI |
| `frontend/src/app/chat/` | Persisted chat, reasoning controls, collapsed thinking, and citation UI |
| `docker-compose*.yml` | Stage worker services, profiles, and Redis removal at cutover |
| `tests/unit/` | State-machine, packing, rate, summary/evidence schema, reasoning, registry, validation, and retry tests |
| `tests/integration/` | PostgreSQL claims, leases, concurrency, artifact versioning, registry, retrieval, and route contracts |

### A.2 Core service contracts

Illustrative signatures:

```python
class JobQueue:
    def create_job(self, job_type, requested_by, payload, idempotency_key) -> Job: ...
    def claim(self, resource_class, worker_id, lease_seconds) -> WorkItem | None: ...
    def renew(self, work_item_id, worker_id, lease_seconds) -> bool: ...
    def complete(self, work_item_id, worker_id, result=None) -> None: ...
    def retry(self, work_item_id, worker_id, available_at, error) -> None: ...
    def fail(self, work_item_id, worker_id, error) -> None: ...
    def recover_expired(self, resource_class=None) -> int: ...

class ResourceAdmission:
    def acquire(self, resource_class, owner, lease_seconds) -> ResourceLease | None: ...
    def renew(self, lease_id, owner, lease_seconds) -> bool: ...
    def release(self, lease_id, owner) -> None: ...
    def reserve_external_start(self, provider_key, interval, jitter) -> datetime: ...
    def open_circuit(self, provider_key, until, error_code) -> None: ...
```

Stage handlers accept an immutable work-item snapshot and return a typed outcome
describing success, retry, permanent failure, and downstream items. They do not
update arbitrary queue state directly.

### A.3 Primary call paths

Channel ingestion:

```text
POST /api/channel/start
  -> authorize
  -> JobQueue.create_job(channel_ingest)
  -> enqueue discover item
  -> return job ID
  -> control worker claims discover
  -> YouTubeAcquisition.discover
  -> enqueue transcript items
  -> transcript worker acquires pacing + concurrency leases
  -> YouTubeAcquisition.fetch_transcript(video)
  -> persist video and enqueue summary/transcript-embedding items
  -> summary and embedding workers process independently
  -> finalizer derives completed/partial/failed job state
```

Batch summarization:

```text
summary worker claims item
  -> acquire batch generation lease
  -> resolve immutable qualified model profile + user reasoning choice
  -> read timestamped transcript segments in a short DB transaction
  -> release DB connection
  -> calculate token-aware plan
  -> SummaryService.generate_nine_section_summary
  -> validate structure, evidence, timestamps, and quotes
  -> persist summary + thinking + provenance in a short transaction
  -> enqueue summary-embedding item
  -> complete work item and release generation lease
```

Interactive chat:

```text
POST chat route
  -> authorize and load bounded conversation history
  -> resolve qualified model + last-used reasoning preference
  -> retrieve and pack timestamped evidence
  -> acquire interactive generation lease
  -> call/stream separate reasoning, answer, sources, and usage events
  -> persist final turn and optional thinking separately
  -> release lease in guaranteed cleanup
  -> return/finish stream
```

Embedding:

```text
embedding worker claims compatible items
  -> build token-bounded input batch
  -> acquire embedding lease
  -> submit one Nomic request
  -> validate vectors
  -> batch-upsert vectors in a short transaction
  -> complete each included item and release lease
```
