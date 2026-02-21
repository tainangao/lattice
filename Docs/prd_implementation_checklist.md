# PRD Implementation Checklist

Source of truth: `Docs/PRD.md`

Legend: `implemented`, `partial`, `missing`

## Functional Requirements

- FR-1 Authentication and Identity: `partial`
  - implemented: Supabase JWT verification via JWKS + `sub` extraction, 401 protection on private endpoints, Chainlit `/auth login`, `/auth oauth-url`, `/auth refresh`, `/auth callback`, and `/auth clear` commands.
  - missing: no first-class browser callback completion flow, no explicit sign-up command/flow, and auth persistence is limited to in-memory chat session state.

- FR-2 File Upload and Ingestion: `partial`
  - implemented: PDF/DOCX/MD/TXT parsing, async in-process ingestion worker (parse -> chunk -> embed -> upsert), queued/processing/success/failed job states, deterministic chunk metadata fields (`source`, `page`, offsets, `user_id`).
  - missing: Chainlit UX only shows initial queued status (no built-in status polling/failure surfacing), parser-to-page fidelity is weak (`page` is currently fixed to `1`), SLA targets are not measured, and persistence is not durable if Supabase is unavailable.

- FR-3 Retrieval Layer: `partial`
  - implemented: Supabase pgvector matching, Neo4j Cypher retrieval, hybrid merge/dedupe path, aggregate route for count-style questions, semantic query/embedding caching, score-normalization + lexical rerank heuristic.
  - missing: no explicit metadata filter API/controls, reranking is heuristic-only (no stronger model), aggregate counts are based on capped retrieved hits rather than full corpus counts, and quality thresholds are not enforced beyond the lightweight eval set.

- FR-4 Agentic Orchestration: `partial`
  - implemented: router supports direct/document/graph/hybrid/aggregate, LangGraph branch fan-out for parallel retrieval, critic refinement with bounded attempts, planner budget guardrail via `PLANNER_MAX_STEPS`, and tool decisions are returned in trace payloads.
  - missing: no generalized planner/executor multi-tool calling loop (plan is route-template based), and limited tool-level retry/guardrail policy beyond critic refinement.

- FR-5 Multi-Turn Memory: `partial`
  - implemented: short-term thread memory, follow-up rewrite using prior turn context, and benchmark coverage for reference resolution.
  - missing: no long-term preference memory, memory is process-local/in-memory only, and coreference handling remains keyword-heuristic.

- FR-6 Response and Citations: `partial`
  - implemented: retrieval answers include citations with `source_id` + `location`, confidence/policy/action are explicit, and infra-degraded vs low-evidence is distinguished.
  - missing: graph citation IDs are query-order based (`neo4j-edge-{index}`/`graph-edge-{index}`) rather than stable graph entity IDs, and synthesis quality is mostly extractive.

- FR-7 Observability and Evaluation: `partial`
  - implemented: structured per-query trace objects (route, confidence, latency, decisions), offline eval harness with golden cases, CI gate runs tests + eval.
  - missing: telemetry is in-memory only (no durable sink/dashboard/alerting), and no SLO gate for performance targets (for example p95 <= 12s).

- FR-8 Onboarding and Access Modes: `partial`
  - implemented: unauthenticated demo mode with quota enforcement, dual-mode behavior, upload blocked without auth, auth-escalation guidance on `/upload`, and quota display in Chainlit.
  - missing: demo quota is hardcoded (not runtime configurable), and onboarding/escalation UX is still command-driven rather than polished guided flow.

- FR-9 Runtime Key Handling: `partial`
  - implemented: session-scoped runtime key lifecycle (`set`/`clear`/`status`/`help`) in API + Chainlit commands, keys are kept in memory and not persisted to disk.
  - missing: default chat flow does not proactively explain no-key mode behavior (it is only visible via `/key status` or API `runtime_key_source`), and runtime key usage depends on backend mode configuration.

- FR-10 Chainlit UX and Deployment: `partial`
  - implemented: Chainlit shows step-level execution from trace decisions and renders answer confidence/policy/citations, Dockerfile + HuggingFace runbook exist.
  - missing: Docker entrypoint currently serves FastAPI (`uvicorn main:app`) instead of Chainlit frontend runtime, source references are not clickable deep links, and there is no recorded full HuggingFace Spaces validation pass.

## Non-Functional Requirements

- Security (RLS, no service-role query path): `partial`
  - implemented: Supabase access uses anon key + user JWT, SQL schema defines RLS policies for own-row access.
  - missing: no automated security validation suite (RLS/auth regression tests are minimal).

- Performance (p95 <= 12s): `missing`
  - missing: no p95 latency measurement, alerting, or CI performance gate.

- Reliability (graceful degraded mode): `partial`
  - implemented: degraded/infra-failure response policies exist.
  - missing: core runtime state is in-memory and not resilient across restarts.

- Scalability (async pipeline, queue-backed ingestion): `partial`
  - implemented: async worker queue exists.
  - missing: queue is process-local (no external durable queue/worker tier).

- Maintainability (clear contracts, high critical-path coverage): `partial`
  - implemented: modular package boundaries + typed dataclass contracts + passing unit/eval suite.
  - missing: critical-path depth is still limited (for example end-to-end coverage for all file types and production auth flows).

- Operational Cost Control (quota/caching guards): `partial`
  - implemented: demo quota and retrieval/embedding caching are present.
  - missing: quota is fixed and there is no broader cost policy (per-user/token budgets, adaptive throttling).

## Definition of Done Snapshot

- End-to-end private upload/query for PDF/DOCX/MD/TXT: `partial`
- Auth, memory, and hybrid retrieval are production-stable: `partial`
- Agent tool traces are visible and debuggable: `implemented`
- Benchmarks + regression tests pass in CI: `implemented`
- User journey (new user -> upload -> ask -> follow-up) passes UAT: `partial`
- Public demo mode, quota UX, and auth escalation flow are validated: `partial`
- Docker deployment to HuggingFace Spaces is documented and repeatable: `partial`

## Immediate Next Actions

1. Implement browser-native Supabase auth callback + sign-up flow and durable session lifecycle for Chainlit.
2. Add ingestion status polling/failure surfacing in Chainlit and improve page-aware metadata extraction.
3. Improve retrieval quality and count accuracy with stronger reranking, metadata filtering, and true aggregation queries.
4. Align HuggingFace deployment to the intended Chainlit frontend runtime and execute an end-to-end validation run.
5. Defer p95/SLO and broader operational cost controls until the usability-first milestone is complete.

## Usability-First Execution Plan (Top 3 Gaps)

### Gap 1: Auth onboarding and session UX (FR-1/FR-8)

- small effort:
  - add `/auth signup <email> <password>` command using Supabase password sign-up endpoint.
  - add callback helper command to parse URL fragment/query and auto-store tokens.
  - improve `/auth status` messaging with explicit next-step guidance.
- medium effort:
  - add a guided in-chat auth flow (buttons/actions) for login, OAuth provider choice, callback completion, and refresh.
  - persist auth tokens in Chainlit persistence (encrypted at rest) with explicit clear/logout semantics.
  - add auth journey integration tests: new user -> login/signup -> upload allowed.
- large effort:
  - replace command-driven auth with full browser-native OAuth callback completion in Chainlit frontend.
  - add multi-provider auth UX parity (email/password + OAuth) with recoverable error flows.
  - add full UAT script and regression tests for session expiry/recovery.

### Gap 2: Upload-to-query ingestion usability (FR-2)

- small effort:
  - add post-upload polling in Chainlit until job reaches success/failed.
  - show actionable parse/upsert failure messages in chat instead of raw JSON.
  - enforce explicit file-type validation feedback before upload.
- medium effort:
  - add ingestion progress states in UI (queued -> processing -> embedding -> upsert -> done).
  - improve parser metadata fidelity (page-aware extraction for PDF/DOCX where available).
  - add tests for all four file types covering success and parse failure behavior.
- large effort:
  - move ingestion to a durable external queue/worker with retry + dead-letter behavior.
  - persist ingestion jobs/chunks in durable storage with recovery across restarts.
  - add ingestion analytics (time-to-queryable, failure categories) and remediation playbooks.

### Gap 3: Retrieval quality and answer usefulness (FR-3/FR-6)

- small effort:
  - add metadata filter controls (source/page/file) to retrieval request path.
  - tighten route hints and fallback behavior for ambiguous questions.
  - improve citation formatting in Chainlit for faster source inspection.
- medium effort:
  - add stronger reranking (cross-encoder/LLM rerank option) behind a config flag.
  - implement true aggregate count path against source backends (not capped hit counts).
  - expand golden eval set with quality-focused cases and minimum policy/citation assertions.
- large effort:
  - add query decomposition for hybrid retrieval (sub-queries + merge strategy).
  - add evidence synthesis constraints to reduce extractive/noisy responses.
  - ship continuous eval + quality regression dashboard for release gating.
