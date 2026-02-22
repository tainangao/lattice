# PRD Implementation Checklist

Source of truth: `Docs/PRD.md`

Legend: `implemented`, `partial`, `missing`

## PRD-Specific Baseline Constraints

- Shared Graph Data Baseline (PRD 4.1): `partial`
  - implemented: Netflix ingestion script exists at `scripts/ingestion/ingest_netflix_csv_neo4j.py`; runtime fallback fixtures and offline eval prompts are now Netflix-aligned.
  - missing: local fallback graph corpus is still a tiny sample, not a full validated mirror of the ingested Netflix graph.

## Functional Requirements

- FR-1 Authentication and Identity: `partial`
  - implemented: Supabase JWT verification via JWKS + `sub` extraction, 401 protection on private endpoints, Chainlit `/auth signup|login|providers|oauth|callback|refresh|status|clear`, and API OAuth start/callback/complete/claim endpoints.
  - missing: auth UX is still command-centric and session persistence is chat-session scoped, not a polished product login lifecycle.

- FR-2 File Upload and Ingestion: `partial`
  - implemented: PDF/DOCX/MD/TXT parsing, async worker pipeline (parse -> chunk -> embed -> upsert), staged job states surfaced to Chainlit, upload polling + failure hints, deterministic metadata (`source`, `page`, offsets, `user_id`).
  - missing: page fidelity is still coarse for DOCX/MD/TXT (single-page semantics), SLA targets are not measured, and queue/worker durability is local-process only.

- FR-3 Retrieval Layer: `partial`
  - implemented: Supabase pgvector retrieval, Neo4j Cypher retrieval, hybrid merge/dedupe, aggregate count path via backend counts, semantic query/embedding caching, heuristic rerank plus optional LLM rerank mode.
  - missing: metadata filter controls are not exposed in the product flow, graph retrieval strategy is still much simpler than the Neo4j reference notebook target, and quality thresholds are still lightweight vs. PRD expectation.

- FR-4 Agentic Orchestration: `partial`
  - implemented: router supports direct/document/graph/hybrid/aggregate, LangGraph branch fan-out for parallel retrieval, critic refinement with bounded attempts, planner budget guardrail via `PLANNER_MAX_STEPS`, and tool decisions are returned in trace payloads.
  - missing: no generalized planner/executor multi-tool calling loop (plan is route-template based), and limited tool-level retry/guardrail policy beyond critic refinement.

- FR-5 Multi-Turn Memory: `partial`
  - implemented: short-term thread memory, follow-up rewrite using prior turn context, and benchmark coverage for reference resolution.
  - missing: no long-term preference memory, memory is process-local/in-memory only, and coreference handling remains keyword-heuristic.

- FR-6 Response and Citations: `partial`
  - implemented: retrieval answers include citations with `source_id` + `location`, confidence/policy/action are explicit, and infra-degraded vs low-evidence is distinguished.
  - missing: synthesis quality remains mostly extractive/snippet-based and citations are still not surfaced as clickable deep links in Chainlit.

- FR-7 Observability and Evaluation: `partial`
  - implemented: structured per-query trace objects (route, confidence, latency, decisions), offline eval harness with golden cases, CI gate runs tests + eval.
  - missing: telemetry is in-memory only (no durable sink/dashboard/alerting), and no SLO gate for performance targets (for example p95 <= 12s).

- FR-8 Onboarding and Access Modes: `partial`
  - implemented: unauthenticated demo mode with quota enforcement, dual-mode behavior, upload blocked without auth, auth-escalation guidance on `/upload`, and quota display in Chainlit.
  - missing: onboarding/escalation UX is still command-driven rather than polished guided flow.

- FR-9 Runtime Key Handling: `partial`
  - implemented: session-scoped runtime key lifecycle (`set`/`clear`/`status`/`help`) in API + Chainlit commands, keys are kept in memory and not persisted to disk.
  - missing: default chat flow does not proactively explain no-key mode behavior (it is only visible via `/key status` or API `runtime_key_source`), and runtime key usage depends on backend mode configuration.

- FR-10 Chainlit UX and Deployment: `partial`
  - implemented: Chainlit shows step-level execution from trace decisions and renders answer confidence/policy/citations, Dockerfile + HuggingFace runbook exist.
  - missing: Docker entrypoint currently serves FastAPI (`uvicorn main:app`) instead of Chainlit frontend runtime, source references are not clickable deep links, and there is no recorded full HuggingFace Spaces validation pass.

## Non-Functional Requirements

- Security (RLS, no service-role query path): `partial`
  - implemented: Supabase access uses anon key + user JWT, SQL schema defines RLS policies for own-row access.
  - missing: no automated security validation suite (RLS/auth regression tests are minimal), and local runtime persistence currently stores queued upload auth tokens in `.tmp/runtime_state.json`.

- Performance (p95 <= 12s): `missing`
  - missing: no p95 latency measurement, alerting, or CI performance gate.

- Reliability (graceful degraded mode): `partial`
  - implemented: degraded/infra-failure response policies exist.
  - missing: durability/recovery model is still local-file and single-process, not production-grade multi-instance reliability.

- Scalability (async pipeline, queue-backed ingestion): `partial`
  - implemented: async worker queue exists.
  - missing: queue is process-local (no external durable queue/worker tier).

- Maintainability (clear contracts, high critical-path coverage): `partial`
  - implemented: modular package boundaries + typed dataclass contracts + passing unit/eval suite.
  - missing: critical-path depth is still limited (for example end-to-end coverage for all file types and production auth flows).

- Operational Cost Control (quota/caching guards): `partial`
  - implemented: demo quota and retrieval/embedding caching are present.
  - missing: broader cost policy is absent (per-user/token budgets, adaptive throttling). Fixed quota behavior now follows PRD direction but still needs explicit validation with UX.

## Definition of Done Snapshot

- End-to-end private upload/query for PDF/DOCX/MD/TXT: `partial`
- Auth, memory, and hybrid retrieval are production-stable: `partial`
- Agent tool traces are visible and debuggable: `implemented`
- Benchmarks + regression tests pass in CI: `partial`
- User journey (new user -> upload -> ask -> follow-up) passes UAT: `partial`
- Public demo mode, fixed 3-query quota UX, and auth escalation flow are validated: `partial`
- Docker deployment to HuggingFace Spaces is documented and repeatable: `partial`

## Immediate Next Actions

1. Upgrade graph retrieval/orchestration quality toward the Neo4j reference notebook target for graph Q&A behavior.
2. Improve synthesis quality beyond snippet concatenation and add stricter answer-quality checks.
3. Align deployment/runtime to an actually usable Chainlit-first experience and complete end-to-end UAT.
4. Improve auth onboarding from command-first to guided UX.
5. Replace local-file runtime persistence model with production-safe storage and token handling.

## Usability-First Execution Plan (Top 3 Gaps)

### Gap 1: Auth onboarding and session UX (FR-1/FR-8)

- small effort:
  - add guided auth quick-actions in chat (instead of requiring typed commands).
  - add persistent auth status banner with clear next step and failure recovery hints.
  - simplify callback completion messaging to a single happy-path instruction.
- medium effort:
  - add a full guided in-chat auth flow (buttons/actions) for login, OAuth provider selection, callback completion, and refresh.
  - persist auth tokens in Chainlit persistence (encrypted at rest) with explicit clear/logout semantics.
  - add auth journey integration tests: new user -> login/signup -> upload allowed.
- large effort:
  - replace command-led auth with product-grade browser-native auth UX and account/session management.
  - add robust multi-provider auth UX parity (email/password + OAuth) with recoverable error flows.
  - add full UAT script and regression tests for session expiry/recovery.

### Gap 2: Upload-to-query ingestion usability (FR-2)

- small effort:
  - replace text-only stage updates with compact progress UI and clearer completion summary.
  - tighten user-facing error taxonomy for parse vs embed vs upsert failures.
  - add one-click retry path for failed ingestion jobs.
- medium effort:
  - improve metadata fidelity for DOCX/MD/TXT beyond single-page semantics.
  - add richer job detail endpoint payload for troubleshooting and support workflows.
  - add tests for all four file types covering success and parse failure behavior.
- large effort:
  - move ingestion to a durable external queue/worker with retry + dead-letter behavior.
  - persist ingestion jobs/chunks in durable storage with recovery across restarts.
  - add ingestion analytics (time-to-queryable, failure categories) and remediation playbooks.

### Gap 3: Retrieval quality and answer usefulness (FR-3/FR-6)

- small effort:
  - add metadata filter controls (source/page/file) to retrieval request path.
  - stabilize graph citation IDs to graph-entity-aware identifiers.
  - improve citation formatting in Chainlit for faster source inspection and validation.
- medium effort:
  - expand golden eval set with Netflix graph quality cases and minimum policy/citation assertions.
  - add graph-route benchmark checks derived from the Neo4j reference notebook behavior patterns.
  - add answer quality checks that fail on weak extractive stitching.
- large effort:
  - implement graph retrieval/orchestration architecture aligned with the Neo4j reference pattern.
  - add query decomposition for hybrid/graph retrieval (sub-queries + merge strategy).
  - ship continuous quality regression gating focused on graph-answer usefulness.
