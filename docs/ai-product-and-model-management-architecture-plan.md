# AI Product And Model Management Architecture Plan

**Status:** Proposed
**Date:** 2026-08-27
**Design depth:** D2 — structural AI product and persistence change
**Decision posture:** User direction captured; implementation has not started
**Related plan:** `docs/performance-scaling-architecture-plan.md`

## 1. Decision Summary

SummarizeMe will move from a weak-model-oriented collection of independent
prompts to a long-context, schema-first, evidence-preserving AI product layer.
The application will use the current Qwen generation model for coherent
per-video synthesis, Nomic embeddings for evidence discovery, PostgreSQL and
pgvector for durable state and retrieval, and deterministic UI components for
summary navigation.

Users retain explicit agency over the model's supported reasoning level. The
application will remember the last reasoning level used by each user for each
operation. Model-returned thinking output will remain visible, but collapsed by
default and stored separately from the final answer.

Generated summaries will conform to a required nine-section contract:

1. Executive overview.
2. Main thesis.
3. Topics and supporting points.
4. Chapter or timeline sections.
5. Important facts and technical details.
6. Decisions, recommendations, and action items.
7. Definitions or glossary.
8. Open questions and caveats.
9. Evidence references containing start and end timestamps.

An administrator-facing model registry will replace hard-coded user-visible
model lists and runtime defaults. Environment variables remain only for database
bootstrap, endpoint bootstrap, and secret references. The registry manages
which already-served models are discovered, qualified, enabled, and assigned to
application operations; it does not download models or control Nemo services.

## 2. Relationship To The Performance Plan

This document is authoritative for:

- model capabilities and user-selectable reasoning behavior;
- prompt and structured-output contracts;
- summary, evidence, citation, retrieval, and chat behavior;
- model registry and administrative UI behavior;
- AI artifact persistence and versioning;
- AI-facing UI and UX requirements;
- AI quality evaluation and acceptance gates.

`docs/performance-scaling-architecture-plan.md` remains authoritative for:

- PostgreSQL work queues, leases, and idempotent workers;
- YouTube pacing and circuit breaking;
- generation and embedding resource admission;
- stage concurrency, worker scaling, and scale-to-zero;
- database connection budgets and runtime topology;
- the hard Nemo resource ceilings.

The two plans must be implemented together. User-selected reasoning changes the
work attached to a generation request, but it never bypasses the global Nemo
admission policy.

## 3. Goals And Non-Goals

### 3.1 Goals

1. Use Qwen3.8's long context and controllable reasoning without making every
   request maximally expensive.
2. Give each user a direct choice of supported reasoning effort.
3. Restore the last-used reasoning choice independently for chat and summary
   operations.
4. Show model-returned thinking output in a collapsed, clearly labelled panel.
5. Produce one coherent, validated summary object for an ordinary video.
6. Preserve timestamped evidence from transcript acquisition through summary,
   retrieval, chat, and UI rendering.
7. Make every material generated claim navigable back to transcript evidence.
8. Render summaries from typed data rather than model-generated HTML.
9. Support versioned regeneration without overwriting earlier summaries.
10. Improve channel and video retrieval through token-aware chunks, hybrid
    retrieval, confidence thresholds, and source diversity.
11. Allow administrators to discover, configure, test, qualify, enable, and
    disable already-served models from the web UI.
12. Prevent model configuration changes from violating shared runtime limits.
13. Evaluate factuality, evidence accuracy, coverage, usability, latency, and
    resource cost before replacing the current flow.

### 3.2 Non-Goals

- Displaying application or server secrets in the browser.
- Treating model thinking as authoritative evidence.
- Embedding model thinking or returning it as a retrieval source.
- Automatically trusting every model returned by `/v1/models`.
- Downloading, loading, unloading, deploying, or restarting Nemo models from
  SummarizeMe.
- Exposing arbitrary endpoint registration to non-administrators.
- Adding another vector database, standing message broker, or model-serving
  framework.
- Filling Qwen's 262,144-token context merely because the capacity exists.
- Claiming that a discovered capability works until the exact endpoint and
  model pass the corresponding qualification test.

## 4. Current-State Findings

### 4.1 Summary generation is fragmented

`blueprints/api.py` calls Qwen four times per transcript chunk and concatenates
the results. `prompts.py` asks independently for concise summary, topics,
takeaways, and comprehensive notes. Longer videos therefore produce multiple
partial outputs rather than one globally coherent summary.

### 4.2 Chunking is not model- or evidence-aware

`summarizer_v2.py` uses word counts and a punctuation regular expression.
`run_vectorizers.py` uses fixed character windows. Neither path preserves
speaker, timestamp, topic, tokenizer, parent-section, or source-version
boundaries.

### 4.3 Chat appears conversational but is stateless

The Next.js chat pages keep messages in browser component state, but the API
receives only the newest question. Follow-up questions cannot reliably refer to
prior turns. Reloading the page also loses the conversation.

### 4.4 Timestamp evidence is discarded downstream

`youtube_utils.py` parses SRT start time and duration and builds both timestamped
and un-timestamped transcript strings. Summarization, embedding, chat retrieval,
and the Next.js transcript view predominantly consume `transcript_no_ts`, so
citations cannot reliably link a generated statement to the relevant video
moment.

### 4.5 Retrieval is separated by generated section type

The application maintains separate embedding tables for transcripts and four
summary columns. Users are asked to select an internal data type before asking
a channel question. Retrieval is vector-only top-k search without a score
threshold, full-text signal, per-video diversity, parent expansion, or explicit
context token budget.

### 4.6 Model configuration has drifted

`app_config.py`, API defaults, and the frontend contain hard-coded Qwen3.6 and
Qwen2.5 model identifiers while current Homelab authority identifies
`nemo-qwen3.8-27b-nvfp4` as the active Nemo generation model.

### 4.7 Thinking handling is heuristic

The backend and frontend infer thinking boundaries from `<think>` tags and a
large set of text phrases. The deployed API can return reasoning separately, so
reasoning and answer content should be separate typed stream fields rather than
reconstructed from final text.

### 4.8 Rendering contracts are inconsistent

Chat responses are converted to HTML on the server, while stored summaries are
Markdown passed directly to a custom HTML sanitizer. The custom sanitizer and
hand-written Markdown transformations increase security and formatting risk.

## 5. Model Execution Contract

### 5.1 User-selectable reasoning

The user-facing selector maps directly to supported model behavior:

| UI label | Stored value | Model behavior | Intended use |
| --- | --- | --- | --- |
| Direct | `disabled` | Thinking disabled | Fast summaries and straightforward questions |
| Low | `low` | Low reasoning effort | Light analysis with lower latency |
| Medium | `medium` | Medium reasoning effort | Default quality/speed balance |
| Deep | `xhigh` | Highest supported reasoning effort | Difficult synthesis, comparisons, and nuanced material |

Rules:

1. The first-use default is `medium`.
2. The last successful user selection becomes the default for that user and
   operation.
3. Chat and summary preferences are stored independently.
4. The selected value is copied into the immutable job payload and generated
   artifact metadata.
5. Regenerating at another level creates a new version; it does not overwrite
   the previous artifact.
6. A model may expose only the reasoning values proven for its exact served
   runtime. The UI must not offer unsupported options.
7. The UI explains that deeper reasoning can increase latency and token use.
8. The application scheduler enforces the same generation permits and total
   token ceiling regardless of the user's choice.

### 5.2 Thinking output

Model-returned thinking is part of the user experience and will be displayed.
It remains distinct from the final answer.

Required behavior:

- Render a `Model thinking` accordion for summary generations and chat turns
  when thinking content exists.
- Start collapsed for every new response, including during streaming.
- Show a compact `Thinking...` status and elapsed time without automatically
  expanding the content; after completion, show reported reasoning-token usage
  when the runtime supplies it.
- Permit a sanitized formatted view and an escaped raw-text view.
- Label the panel as working analysis that may contain abandoned or incorrect
  paths; the final answer and evidence remain authoritative.
- Store thinking in a nullable field separate from the final artifact.
- Do not embed, index, cite, or retrieve thinking content.
- Exclude thinking from exports by default; provide an explicit
  `Include model thinking` export option.
- Do not inject stored thinking into later prompts merely because it is stored.
  Any use of model-native preserved thinking in multi-turn requests requires an
  explicit token-budget policy and an exact SGLang compatibility test.

### 5.3 Typed streaming protocol

Backend-to-browser streaming uses explicit event types:

```json
{"type":"reasoning_delta","content":"..."}
{"type":"answer_delta","content":"..."}
{"type":"sources","items":[]}
{"type":"usage","input_tokens":0,"reasoning_tokens":0,"output_tokens":0}
{"type":"done"}
```

The implementation must not combine reasoning and answer deltas or depend on
text-pattern parsing. A temporary compatibility adapter may parse legacy
`<think>` blocks during migration, but the typed path becomes authoritative.

### 5.4 Sampling and output profiles

Sampling is owned by an operation-specific model profile, not scattered call
sites. Each request records the effective values for:

- reasoning effort or thinking disabled;
- temperature;
- top-p and top-k where supported;
- presence and repetition penalties where supported;
- maximum reasoning/output tokens;
- structured-output mode;
- prompt and schema versions.

Profiles require workload qualification. Vendor-recommended chat values are
inputs to testing, not automatic proof that those values are optimal for
faithful transcript summarization.

## 6. Deterministic Summary Contract

### 6.1 Canonical representation

The canonical summary is validated JSON stored in PostgreSQL `JSONB`. The UI
renders typed components directly from that object. Markdown and plain text are
derived export formats; model-generated HTML is never authoritative.

Every top-level section is required. A section not supported by the transcript
uses an empty collection or an explicit `not_discussed` state instead of being
silently omitted.

### 6.2 Contract shape

The public contract is conceptually:

```json
{
  "schema_version": "summary.v3",
  "executive_overview": {
    "text": "",
    "evidence_ids": []
  },
  "main_thesis": {
    "statement": "",
    "evidence_ids": []
  },
  "topics": [
    {
      "title": "",
      "summary": "",
      "supporting_points": [
        {"text": "", "evidence_ids": []}
      ]
    }
  ],
  "chapters": [
    {
      "title": "",
      "start_seconds": 0,
      "end_seconds": 0,
      "summary": "",
      "key_points": [],
      "evidence_ids": []
    }
  ],
  "important_details": [
    {
      "statement": "",
      "classification": "fact",
      "speaker": null,
      "evidence_ids": []
    }
  ],
  "decisions": [],
  "recommendations": [],
  "action_items": [
    {
      "action": "",
      "owner": null,
      "due_date": null,
      "evidence_ids": []
    }
  ],
  "glossary": [
    {
      "term": "",
      "definition": "",
      "evidence_ids": []
    }
  ],
  "open_questions": [],
  "caveats": [],
  "evidence": [
    {
      "id": "E1",
      "start_seconds": 0,
      "end_seconds": 0,
      "speaker": null,
      "excerpt": "",
      "youtube_url": ""
    }
  ]
}
```

The implementation schema may use additional nested objects, but it must retain
the nine required user-facing sections and stable evidence references.

### 6.3 Claim classification

Important details and other claim-bearing objects distinguish:

```text
fact
speaker_claim
opinion
estimate
recommendation
inference
```

The prompt must not promote a speaker's assertion to an externally verified
fact. The application can establish transcript fidelity; it does not establish
the external truth of every statement in a video.

### 6.4 Evidence rules

1. Every evidence ID resolves to one video and one timestamp range.
2. Every timestamp range has `start_seconds <= end_seconds` and falls within the
   known video/transcript duration when that duration is available.
3. Exact quotations are permitted only when the excerpt is present verbatim in
   the normalized transcript span.
4. Paraphrases are not displayed as quotations.
5. Material claims should include at least one evidence ID.
6. A chapter's time range should cover its referenced evidence.
7. References that fail validation make the affected field invalid rather than
   silently dropping provenance.
8. YouTube links are derived by the application from video ID and timestamp;
   the model does not construct arbitrary URLs.

### 6.5 Validation and repair

The generation response is constrained by SGLang structured output when the
exact deployed endpoint proves compatible. It is then validated locally with a
typed schema such as Pydantic.

Validation covers:

- JSON and field types;
- all required sections;
- enum values;
- timestamp order and bounds;
- evidence-reference integrity;
- quote-to-transcript matching;
- maximum field and collection sizes;
- prohibited HTML;
- duplicate topics, chapters, and evidence entries.

One bounded corrective retry may receive validation errors and the invalid
object. A second invalid result is a visible generation failure, not a
successful empty summary.

### 6.6 Artifact metadata

Each summary version records:

- served model record and immutable served-model ID snapshot;
- reasoning effort;
- endpoint/profile revision;
- prompt version and summary schema version;
- normalized transcript hash and transcript version;
- input, reasoning, and output token usage when available;
- time to first token and total duration;
- complete/incomplete transcript status;
- structured-output validation and repair status;
- requester and generation timestamp;
- optional model thinking output.

## 7. Summary Generation Strategy

### 7.1 Ordinary video

When the timestamped transcript, prompt, requested reasoning budget, structured
output, and safety headroom fit the configured request budget, one Qwen request
produces the entire summary contract.

The application must use an exact or conservatively validated compatible
tokenizer. Word counts and character counts are not valid admission measures.

### 7.2 Oversized video

An oversized transcript uses a hierarchical path:

1. Segment the transcript by timestamps, speakers, and semantic/topic
   boundaries within a token budget.
2. Extract typed facts, topics, chapter candidates, caveats, actions, glossary
   terms, and evidence references from each segment.
3. Validate each map result against its source segment.
4. Run one global synthesis over the typed map results.
5. Validate the final evidence IDs against the original transcript segments.

Map outputs are internal evidence packets, not final user summaries. Final
sections are never produced by concatenating independent chunk summaries.

### 7.3 Concurrency interaction

Every map request and final synthesis request acquires the same batch generation
lease defined by the performance plan. Deep reasoning does not create an extra
lane. Interactive chat retains priority and its reserved admission class.

## 8. Transcript, Chunking, And Retrieval Design

### 8.1 Canonical transcript segments

The application should persist structured transcript segments instead of
relying only on two large text columns:

```text
transcript_segments
- id
- video_id
- transcript_version
- segment_order
- start_seconds
- end_seconds
- speaker nullable
- text
- normalized_text
- content_hash
```

The existing combined transcript strings may remain compatibility projections
during migration.

### 8.2 Retrieval chunks

Initial retrieval design:

- child chunks targeted at approximately 300–700 model tokens;
- approximately 10–15 percent overlap when topic boundaries do not already
  provide continuity;
- no split inside a transcript segment unless that segment itself exceeds the
  limit;
- parent sections targeted at approximately 1,500–3,000 tokens;
- stored start and end timestamps covering all child content;
- title, video, channel, transcript version, parent, source type, and content
  hash attached to every chunk.

These ranges are benchmark inputs, not immutable constants. Retrieval quality
tests determine the final values.

### 8.3 Unified content index

The target is a versioned `content_chunks` table rather than five independent
embedding tables:

```text
content_chunks
- id
- video_id
- summary_run_id nullable
- source_kind              # transcript, summary_section
- section_kind nullable
- parent_chunk_id nullable
- chunk_order
- start_seconds nullable
- end_seconds nullable
- content
- content_hash
- embedding_model_id
- embedding_revision
- embedding vector(768)
- search_document tsvector
- created_at
```

The migration is not required in the first work-queue slice. Existing tables
remain available until retrieval parity and migration correctness are proven.
After cutover, the unified table becomes authoritative and old tables are
removed only through a separately reversible cleanup.

Model thinking is never inserted into `content_chunks`.

### 8.4 Embedding behavior

- Preserve Nomic's exact `search_document: ` and `search_query: ` prefixes.
- Batch multiple inputs within both the 32-sequence and 8,192-total-token hard
  limits documented for the current service.
- Begin with a smaller qualified sequence count and benchmark upward.
- Validate vector count, 768 dimensions, finite values, and normalization.
- Record model/revision and source hash so changed sources are re-embedded.
- Replace a source version transactionally so partial rows cannot masquerade as
  a complete index.

### 8.5 Query-time retrieval

The target query path is:

1. Classify scope and intent using deterministic rules where sufficient.
2. Search vector and PostgreSQL full-text indexes.
3. Fuse rankings, initially with reciprocal-rank fusion.
4. Remove duplicates and near-duplicates.
5. Apply per-video diversity for channel queries.
6. Apply a minimum relevance/confidence policy.
7. Expand selected child chunks to their parent context where useful.
8. Pack the final evidence set into an explicit generation token budget.

A separate reranker model is optional and requires its own measured value,
memory, and latency justification. The initial design avoids keeping another
model resident solely for reranking.

## 9. Chat Contract

### 9.1 Real conversation state

Chat requests include bounded conversation history, not only the newest query.
Conversations and messages are persisted per user. The context builder may
summarize older turns when the conversation exceeds its token budget, but it
must retain recent user/assistant turns and referenced source identities.

The user preference for reasoning effort is applied to the current turn and
recorded on the assistant message.

### 9.2 Retrieval routing

- A broad request about one ordinary-sized video may use the complete
  timestamped transcript within a safe context budget.
- A narrow video question uses retrieval rather than duplicating retrieved
  chunks plus the full transcript.
- A channel question uses hybrid retrieval and source diversity.
- A comparison question allocates evidence across the entities/videos being
  compared instead of allowing one highly similar video to dominate.
- The application chooses sources automatically. Users choose scope and
  reasoning, not internal embedding-table names.

### 9.3 Prompt boundary

The prompt declares transcript and retrieved content to be untrusted evidence,
not instructions. It requires the model to:

- use only supplied evidence for content claims;
- distinguish video claims, opinions, estimates, and application inference;
- state when evidence is insufficient;
- cite stable evidence IDs for material claims;
- avoid invented quotes, timestamps, URLs, speakers, or source titles;
- follow the requested output style without changing the evidence contract.

### 9.4 Response contract

Chat returns separate fields/events for:

- thinking;
- final answer;
- structured claim/source references;
- source cards;
- usage/timing metadata;
- completion or sanitized failure state.

The frontend renders answer Markdown with a maintained safe renderer and renders
citations from typed source objects. The server does not append citation HTML to
the answer string.

## 10. Model Registry And Administrative UI

### 10.1 Configuration authority

The runtime database becomes authoritative for enabled models and operation
profiles. Environment variables remain responsible for:

- `DATABASE_URL`;
- bootstrap endpoint URLs when the registry is empty;
- secret values or secret-reference names;
- an emergency recovery/disable switch.

The existing `VLLM_GEN_MODEL` and `VLLM_EMBED_MODEL` variables may seed an empty
registry during migration, but they cease to be the normal runtime selection
authority after cutover.

### 10.2 Endpoint registry

```text
ai_endpoints
- id
- name
- base_url
- endpoint_type
- api_key_env_name nullable
- runtime_pool_id
- enabled
- last_health_status
- last_checked_at
- created_at
- updated_at
```

Secrets are never stored in plaintext endpoint rows. `api_key_env_name` names a
server-side environment or secret-provider entry.

### 10.3 Model registry

```text
ai_models
- id
- endpoint_id
- served_model_id
- display_name
- model_role              # generation, embedding, reranker, transcription, multimodal
- context_limit nullable
- output_limit nullable
- embedding_dimensions nullable
- supports_streaming
- supports_structured_output
- supports_thinking
- supported_efforts JSONB
- capabilities JSONB
- qualification_status    # discovered, configured, testing, qualified, disabled
- enabled
- created_at
- updated_at
```

`served_model_id` is unique within an endpoint. Historical artifacts keep both
the model-row reference and an immutable served-ID snapshot so later renames or
disablement do not rewrite provenance.

### 10.4 Operation profiles

```text
ai_model_profiles
- id
- model_id
- operation               # summary, video_chat, channel_chat, embedding
- profile_name
- reasoning_effort nullable
- sampling_parameters JSONB
- max_output_tokens
- structured_output_enabled
- prompt_version
- schema_version nullable
- is_default
- enabled
- created_at
- updated_at
```

Defaults are unique per operation within the enabled/qualified set. A profile
cannot enable a capability the model has not passed in qualification.

### 10.5 Shared runtime pools

Capacity belongs to a serving runtime, not to each registered model:

```text
ai_runtime_pools
- id
- name
- resource_class
- max_concurrent_requests
- max_total_tokens nullable
- reserved_interactive_requests
- hard_ceiling_source
- enabled
- updated_at
```

All SummarizeMe models served by the current Nemo Qwen endpoint consume the same
generation pool. Registering a second model never multiplies the four-request
Nemo hard ceiling.

### 10.6 User preferences

```text
user_ai_preferences
- user_id
- operation               # summary, chat
- model_id nullable
- reasoning_effort
- updated_at

UNIQUE (user_id, operation)
```

The server validates the stored preference against the current qualified model.
If a model or reasoning level is disabled, the UI falls back visibly to the
operation default rather than submitting an invalid hidden selection.

### 10.7 Administrative workflow

The admin-only `AI Models` page supports:

- list registered endpoints and their last health result;
- discover served IDs through `/v1/models`;
- distinguish discovered, configured, qualified, enabled, and disabled models;
- edit display names, roles, limits, and declared capabilities;
- configure operation profiles and defaults;
- run connection, generation, streaming, structured-output, reasoning, and
  embedding-vector tests as applicable;
- display qualification evidence and the last successful test;
- enable, disable, and soft-retire models;
- view an audit history of configuration changes.

Discovery never implies qualification. `/v1/models` generally proves only that
a served ID exists. Context length, reasoning values, structured output,
embedding dimensions, normalization, and acceptable quality require exact tests.

### 10.8 Scope and safety boundary

The registry manages application routing to already-served models. It does not:

- download weights;
- start or stop services;
- edit Nemo systemd or container definitions;
- allocate GPU memory;
- raise server concurrency or token pools;
- expose arbitrary endpoints to ordinary users.

Any future infrastructure-control integration requires a separate authorization,
threat model, and bounded operator contract.

## 11. Summary And Chat UI/UX

### 11.1 Summary navigation

Desktop uses a sticky contents column and main reading surface. Mobile uses a
collapsible contents drawer. The nine required sections appear in stable order
with scroll-spy highlighting:

1. Executive Overview
2. Main Thesis
3. Topics
4. Chapters
5. Important Details
6. Decisions & Actions
7. Glossary
8. Open Questions
9. Evidence

The page supports:

- search within the complete summary;
- expand/collapse all;
- copy section and copy complete summary;
- Markdown, JSON, and plain-text export;
- optional inclusion of model thinking in export;
- `Ask about this section` actions;
- regenerate at another supported reasoning level;
- comparison of summary versions;
- explicit transcript-incomplete and `not discussed` states.

### 11.2 Chapter timeline

Chapters render as timestamped navigation, for example:

```text
00:00  Introduction
04:28  Core architecture
12:42  Performance constraints
28:15  Recommendations
```

Selecting a chapter or evidence timestamp opens the YouTube video at the exact
start time and can reveal the surrounding transcript.

### 11.3 Evidence interaction

Material claims show evidence chips such as `E1 · 12:42`. Selecting a chip opens
an evidence drawer containing:

- video and chapter title;
- start/end time;
- transcript excerpt and surrounding context;
- speaker when available;
- `Watch on YouTube` action;
- classification and summary claims using the evidence.

### 11.4 Thinking panel

`Model thinking` appears in a secondary `Generation details` region for
summaries and inline with assistant turns for chat. It is collapsed by default
and does not participate in page search unless the user explicitly includes it.

Generation details also show:

- user-facing model name and immutable served-ID provenance;
- selected reasoning effort;
- prompt and schema version;
- input/reasoning/output token use where available;
- duration and validation state;
- transcript completeness;
- regeneration controls.

### 11.5 Chat usability

- Multiline composer.
- Stop generation.
- Retry and regenerate.
- Edit and resubmit a user turn.
- Persisted conversations across reloads.
- Suggested questions based on video/channel state.
- Automatic source selection instead of summary-table selection.
- Clear scope selection: current video or current channel.
- Inline evidence chips and a source drawer.
- Auto-scroll only while the user remains near the bottom.

### 11.6 Model and reasoning selectors

Ordinary users see only qualified and enabled models. Internal model IDs remain
in admin/provenance views. If only one qualified model exists, the model selector
may be hidden while reasoning selection remains visible.

The last-used choice is restored per user and operation. The selected values are
visible before submission and on the completed artifact.

## 12. Persistence And Versioning

### 12.1 Summary runs

The current unique `(video_id, model_name)` summary shape is replaced by
versioned runs:

```text
summary_runs
- id
- video_id
- model_id
- served_model_id_snapshot
- model_profile_id
- reasoning_effort
- schema_version
- prompt_version
- transcript_version
- transcript_hash
- generation_profile_hash
- structured_summary JSONB
- final_markdown nullable
- reasoning_output nullable
- validation_state
- repair_attempted
- input_tokens nullable
- reasoning_tokens nullable
- output_tokens nullable
- time_to_first_token_ms nullable
- duration_ms nullable
- requested_by
- created_at
```

`generation_profile_hash` covers the model, prompt, schema, reasoning, sampling,
and transcript source. It supports idempotent retries without preventing an
intentional regeneration under another profile.

### 12.2 Conversations

```text
conversations
- id
- user_id
- scope_type              # video, channel
- scope_id
- title
- created_at
- updated_at

conversation_messages
- id
- conversation_id
- role
- content
- reasoning_output nullable
- reasoning_effort nullable
- model_id nullable
- sources JSONB nullable
- usage JSONB nullable
- created_at
```

Reasoning remains displayable but separate from `content`. Neither stored
reasoning nor conversation text is placed into retrieval indexes.

### 12.3 Audit records

Model endpoint, model, capability, qualification, default-profile, and runtime
pool changes write bounded audit records containing actor, timestamp, affected
record, before/after non-secret fields, and outcome.

## 13. Security And Trust Boundaries

- Model management is restricted to administrators.
- All inference calls originate server-side.
- Endpoint URLs are normalized and restricted to approved schemes and networks;
  arbitrary URL testing must not become an SSRF primitive.
- Secret values are never stored in model registry rows or returned to the
  browser.
- Transcript and retrieved text are explicitly marked as untrusted data in
  prompts.
- Model Markdown is rendered through one maintained, tested renderer and
  sanitizer; hand-written HTML transformations are removed.
- Thinking output receives the same rendering/sanitization protections as final
  output.
- Generated YouTube links are application-derived from known video IDs and
  validated timestamps.
- Raw external errors are logged with bounded sanitization and are not returned
  to users.
- Disabled models and prior summary versions are soft-retained so provenance is
  not broken.

## 14. Observability And Evaluation

### 14.1 Request telemetry

Capture by operation, model profile, and reasoning effort:

- input, reasoning, and output tokens;
- time to first reasoning token and first answer token where available;
- total duration;
- structured validation and repair results;
- retrieval candidates, selected evidence count, and packed context tokens;
- summary section completeness;
- user cancellation, retry, and regeneration counts;
- Nemo admission wait and in-flight class.

Do not log complete transcripts, prompts, thinking, or answers in ordinary
application logs.

### 14.2 Quality corpus

Before cutover, create a bounded evaluation set covering:

- short and long videos;
- technical tutorials;
- discussions and interviews;
- videos with conflicting opinions;
- action-oriented content;
- weak or incomplete captions;
- channel-wide comparisons;
- follow-up chat questions.

Evaluate:

- factual consistency with transcript evidence;
- quotation and timestamp accuracy;
- evidence precision and coverage;
- topic and chapter coverage;
- duplicate and contradictory content;
- retrieval hit rate and source diversity;
- output-schema validity;
- user navigation and task completion;
- latency and token cost by reasoning effort.

Compare Direct, Low, Medium, and Deep on the same sources. The product should
show the choice, not imply that the slowest setting is always objectively best.

### 14.3 Required exact-runtime gates

- Qwen3.8 served identity.
- Supported reasoning-effort request syntax.
- Disabled-thinking request syntax.
- Separate reasoning and answer fields in non-streaming and streaming modes.
- SGLang JSON-schema constrained output.
- Token-usage reporting fields.
- Nomic prefix, dimensions, normalization, maximum input, and batch behavior.

Unsupported fields must fail visibly during qualification rather than silently
falling back to a different behavior.

## 15. Implementation Slices

### AI Slice A — Contracts and compatibility

- Add typed summary, evidence, generation-profile, and stream-event schemas.
- Add exact-runtime probes for reasoning modes and structured output.
- Add token budgeting and transcript-segment normalization.
- Preserve current behavior behind a disabled feature flag.

Acceptance:

- All nine summary sections validate.
- Evidence-reference and quote checks fail incorrect fixtures.
- Reasoning and answer streams remain separate.
- Unsupported reasoning modes cannot be selected.

### AI Slice B — Timestamped transcript authority

- Add transcript segments and compatibility projections.
- Preserve speaker/timestamp information from acquisition.
- Add timestamped transcript API and UI navigation.

Acceptance:

- Segment order, duration, hash, and timestamp invariants pass.
- A UI timestamp opens the correct YouTube position.
- Existing transcript consumers continue to work during migration.

### AI Slice C — Structured summary runs

- Add versioned `summary_runs`.
- Implement one-call ordinary-video generation.
- Implement hierarchical oversized-video extraction and synthesis.
- Store final object and optional thinking separately.

Acceptance:

- Ordinary videos use one generation request.
- Oversized summaries are synthesized, not concatenated.
- Regeneration at another reasoning level creates a new version.
- Interactive admission remains available during batch generation.

### AI Slice D — Summary experience

- Build nine-section navigation and typed section components.
- Add chapter timeline, evidence drawer, search, export, and version comparison.
- Add collapsed thinking and generation details.
- Replace inconsistent Markdown/HTML handling.

Acceptance:

- Desktop and mobile navigation reach every required section.
- Evidence links are application-derived and timestamp-correct.
- Thinking begins collapsed and remains separate from the final answer.
- Security tests cover rendered summary, answer, and thinking content.

### AI Slice E — Retrieval and conversational chat

- Add bounded conversation history and persistence.
- Add typed chat streaming events.
- Add token-aware chunks, hybrid retrieval, diversity, thresholds, and parent
  expansion.
- Migrate to the unified content index after parity gates.

Acceptance:

- Follow-up questions retain conversation meaning.
- Channel questions cite multiple relevant videos when the evidence warrants it.
- Irrelevant low-confidence results do not become context.
- Reasoning is visible but never indexed.

### AI Slice F — Model registry

- Add endpoints, models, profiles, runtime pools, preferences, and audit schema.
- Add admin discovery, test, qualification, and enable/disable workflows.
- Replace hard-coded frontend model options.
- Migrate environment model values to one-time bootstrap behavior.

Acceptance:

- A discovered model is not selectable until qualified and enabled.
- Last-used model/reasoning preferences restore per user and operation.
- Registering multiple models cannot multiply a runtime pool ceiling.
- Endpoint secrets never appear in browser responses or audit diffs.

### AI Slice G — Evaluation and cutover

- Run the quality corpus across reasoning modes.
- Record retrieval, evidence, schema, latency, and resource results.
- Enable the new summary/chat UI after acceptance.
- Retain additive rollback compatibility until production proof is complete.

## 16. Rollback

- Use additive schema changes through qualification.
- Retain legacy summary columns and vector tables until new reads and writes
  prove parity.
- Keep a feature flag for legacy summary/chat rendering during migration.
- Do not delete summary versions, reasoning output, transcript segments, or
  evidence during rollback.
- Disable new model profiles rather than deleting referenced registry records.
- Revert selection authority to bootstrap configuration only through an
  explicit recovery mode.

## 17. Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Deep reasoning makes large batches unexpectedly slow | Show the user-visible tradeoff, preserve their choice, capture telemetry, and retain global admission limits |
| Thinking output is mistaken for the answer | Collapse by default, label as working analysis, and keep final answer/evidence visually authoritative |
| Thinking leaks into search or later answers | Separate persistence fields and prohibit reasoning from content indexes |
| Model emits valid JSON with unsupported claims | Evidence IDs, claim classification, quote validation, and evaluation corpus |
| Long context reduces quality or consumes shared capacity | Dynamic token routing, conservative headroom, and hierarchical path |
| Model discovery is treated as qualification | Explicit discovered/configured/testing/qualified/enabled lifecycle |
| Registry values exceed Nemo limits | Shared runtime-pool ceilings validated against the performance plan |
| Arbitrary endpoint management creates SSRF | Admin-only allowlisted server-side endpoint validation |
| Structured UI loses useful narrative flow | Preserve a coherent overview while providing deterministic section navigation |
| Unified index migration reduces retrieval quality | Keep legacy tables until measured parity and reversible cutover |

## 18. Captured Product Decisions

The following directions are accepted for planning:

1. Users select the supported reasoning level.
2. The application defaults to the last reasoning level used by that user,
   independently for chat and summary operations; first use defaults to Medium.
3. Model thinking output is shown in a panel collapsed by default.
4. Thinking and final answers are streamed and stored separately.
5. Summaries use the deterministic nine-section contract in this document.
6. The summary UI provides durable section, chapter, timeline, and evidence
   navigation rather than four independent free-form tabs.
7. An admin web UI manages registered models and operation profiles instead of
   maintaining hard-coded frontend model lists.
8. Model-registry scope is application configuration and qualification, not
   model deployment or Nemo infrastructure control.
9. PostgreSQL remains the application, vector, job, preference, artifact, and
   registry database; Redis and an additional vector database are unnecessary.

## 19. External And Local Authority

Model and runtime behavior must be checked against:

- Qwen3.8 model card: <https://huggingface.co/Qwen/Qwen3.8-27B>
- Deployed quantized checkpoint: <https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4>
- SGLang structured output: <https://docs.sglang.io/docs/advanced_features/structured_outputs>
- Nomic Embed v1.5 model card: <https://huggingface.co/nomic-ai/nomic-embed-text-v1.5>
- `Homelab-Documentation/services/ai-inference-and-translation-platform.md`
- `Homelab-Documentation/change-management/2026-08-21-nemo-voice-identity-continuity.md`
- `Homelab-Documentation/ai/objects/serving-profiles/nemo-nomic-embed-text-vllm-8k.md`

The application repository remains authoritative for implemented behavior. The
external and Homelab sources define capability candidates and current resource
boundaries; implementation tests must prove the exact integration.
