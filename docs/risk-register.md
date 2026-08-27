# SummarizeMe Risk Register

This document tracks all identified technical, architectural, operational, security, and inference risks for the AI Product & Performance Scaling implementation, including mitigation strategies, trigger conditions, severity ratings, and ownership.

---

## Risk Scoring Matrix
- **Likelihood**: Low (1), Medium (2), High (3)
- **Impact**: Low (1), Medium (2), High (3), Critical (4)
- **Risk Score** = Likelihood $\times$ Impact (1–12)
  - 🟢 **Low** (1–3): Monitor; standard safeguards apply
  - 🟡 **Medium** (4–6): Mitigation required in active design
  - 🔴 **High / Critical** (8–12): Hard architectural gate; must be resolved before phase acceptance

---

## Active Risk Register

| Risk ID | Category | Description | Likelihood | Impact | Score | Mitigation Strategy | Trigger Indicator / Metric | Assigned Phase & Owner | Status |
|---|---|---|:---:|:---:|:---:|---|---|:---:|:---:|
| **RSK-001** | Hardware / Nemo | Batch summary jobs overwhelm shared Nemo generation capacity, starving other homelab workloads or degrading interactive chat. | 3 | 4 | **12** 🔴 | Strict client-side admission: max 2 batch slots + 1 reserved interactive slot = 3 max in-flight (leaving 1 slot for external services under Nemo 4-stream ceiling). | Qwen TTFT > 3000ms, Nemo queue depth > 0, batch jobs timing out. | Phase 1 & 3 (`Agent-Beta`) | Active |
| **RSK-002** | External API / YouTube | yt-dlp triggers YouTube 429 rate limiting, CAPTCHAs, or IP bans during channel-wide batch downloads. | 3 | 4 | **12** 🔴 | Global PostgreSQL-backed start pacing (12s interval + 0–3s jitter), max 2 in-flight subprocesses, automatic exponential backoff, and circuit breaker tripwire. | Consecutive yt-dlp `429 Too Many Requests` or `Sign in to confirm you’re not a bot`. | Phase 2 (`Agent-Beta`) | Active |
| **RSK-003** | Database / Concurrency | PostgreSQL connection pool starvation caused by workers holding database sessions across long LLM (Qwen) or YouTube calls. | 3 | 3 | **9** 🔴 | Strict rule: All DB transactions must be short ($\le 50\text{ms}$). Release DB connection before making any network or external subprocess call. | SQLAlchemy `TimeoutError: QueuePool limit of size 5 overflow 5 reached`. | Phase 1 & 3 (`Agent-Alpha`) | Active |
| **RSK-004** | AI Product / Hallucination | Model produces plausible structured summary JSON containing ungrounded claims or hallucinated evidence timestamps. | 2 | 3 | **6** 🟡 | Pydantic schema validation, claim classification, quote-to-transcript verbatim matching, timestamp boundary checks, and single corrective retry. | Summary validation failure rate > 5%, failed quote matching on `E1` chips. | Phase 0 & 3 (`Agent-Alpha`) | Active |
| **RSK-005** | AI Product / Privacy | Model thinking output leaks into retrieval indexes, pgvector embeddings, or public search results. | 2 | 3 | **6** 🟡 | Thinking output stored in distinct nullable database columns (`reasoning_output`), strictly filtered out of `content_chunks` and embeddings. | Presence of `reasoning_output` in `content_chunks.content` or vector search hits. | Phase 3 & 4 (`Agent-Alpha`) | Active |
| **RSK-006** | Hardware / Nemo | Large Nomic embedding batches cause GPU memory pressure or increase Qwen generation latency on Nemo host. | 2 | 3 | **6** 🟡 | Initial embedding batch sequence limit set to 8 (packed $\le 8,192$ tokens), max 1 in-flight batch; benchmark sequence sweep (1, 4, 8, 16, 32). | Nemo GPU VRAM usage > 90%, embedding latency spike during active generation. | Phase 4 (`Agent-Alpha`) | Active |
| **RSK-007** | Operational / Workers | Worker process crashes or is killed by OOM mid-task, abandoning claimed work items and leaving orphaned leases. | 2 | 3 | **6** 🟡 | Expiring leases with periodic heartbeat renewal (`renew`), crash recovery loop in `JobQueue.recover_expired_leases`, at-least-once idempotency. | Work items remaining in `leased` status past `lease_expires_at`. | Phase 1 (`Agent-Alpha`) | Active |
| **RSK-008** | Security / Admin | Unauthenticated or malicious users invoke Model Registry APIs to add unauthorized endpoints or trigger SSRF attacks. | 1 | 4 | **4** 🟡 | Enforce `@require_role(["admin"])` on all registry routes, server-side URL validation (allowlist schemes/hosts), secret names stored as env refs. | 403 Forbidden spikes on `/api/admin/` or non-allowlisted endpoint registration attempts. | Phase 5 (`Agent-Beta`) | Active |
| **RSK-009** | Architecture / Migration | Deprecating legacy vector tables prematurely breaks RAG search during transitional rollout. | 2 | 2 | **4** 🟡 | Additive schema migrations, dual-write bridge to both `content_chunks` and legacy vector tables, feature flags guarding new retrieval path until parity proven. | Discrepancy between legacy RAG search results and unified `content_chunks` search. | Phase 4 & 5 (`Agent-Beta`) | Active |
| **RSK-010** | Autoscaling | Scale-down terminates active worker container abruptly, corrupting in-flight generation or transcript downloads. | 2 | 2 | **4** 🟡 | Graceful drain protocol on SIGTERM, 5-minute idle grace period, scaler checks active leases before reducing replicas. | Work items marked `failed` immediately following scaling script execution. | Phase 7 (`Agent-Alpha`) | Active |

---

## Risk Review & Escalation Workflow

1. **Continuous Monitoring**: Subagents check risk indicators during each task execution.
2. **Trigger Escalation**: If any metric crosses a trigger threshold:
   - Subagent immediately sends a `BLOCKER` message with the `Risk ID` to the Lead Orchestrator.
   - Task status transitions to `[!] BLOCKED` on the checklist board.
3. **Independent Review Audit**: Review subagents (`ReviewCore` and `ReviewSurfaces`) explicitly audit compliance against all active risks during phase synchronization gates.
4. **Resolution & Retrospective**: Mitigations are verified with targeted unit/integration tests before closing the risk.
