# PRD Implementation Checklist

Source of truth: `Docs/PRD.md`

Legend: `implemented`, `partial`, `missing`

## Functional Requirements

- FR-1 Authentication and Identity: `partial`
  - implemented: Supabase JWT verification via JWKS, protected private endpoints, Chainlit session login/refresh commands.
  - missing: OAuth callback UX and full persistent session lifecycle beyond in-memory Chainlit session state.

- FR-2 File Upload and Ingestion: `partial`
  - implemented: PDF/DOCX/MD/TXT parsing, async queue-backed ingestion, job states, chunk metadata, embed+upsert path.
  - missing: production SLA validation and stronger page-level metadata fidelity for parsed documents.

- FR-3 Retrieval Layer: `partial`
  - implemented: Supabase pgvector retrieval, Neo4j retrieval, hybrid merge/dedupe, aggregate route, query caches.
  - missing: true reranking model, semantic cache normalization, benchmarked quality thresholds.

- FR-4 Agentic Orchestration: `partial`
  - implemented: router paths, parallel retrieval branches, critic refinement with bounded retries, LangGraph integration.
  - missing: generalized planner/executor tool-calling loop with explicit max-step governance.

- FR-5 Multi-Turn Memory: `partial`
  - implemented: short-term turn memory and follow-up reference resolution heuristics.
  - missing: long-term preference memory and deeper coreference handling.

- FR-6 Response and Citations: `partial`
  - implemented: citations with source/location, confidence labels.
  - missing: stronger final synthesis quality guardrails and strict infra-failure vs low-evidence policy messaging.

- FR-7 Observability and Evaluation: `partial`
  - implemented: structured trace payloads (route/tool/latency/confidence/errors/attempts), offline eval harness.
  - missing: online guardrails dashboard and expanded golden/regression benchmark coverage.

- FR-8 Onboarding and Access Modes: `partial`
  - implemented: demo mode quota, dual-mode behavior, private upload requires auth.
  - missing: polished auth-escalation UX and full onboarding journey in Chainlit.

- FR-9 Runtime Key Handling: `implemented`
  - implemented: session key set/clear/help/status, in-memory only, no persistence.
  - implemented: fallback to `GEMINI_API_KEY`/`GOOGLE_API_KEY` when session key not set.

- FR-10 Chainlit UX and Deployment: `partial`
  - implemented: working Chainlit app flow with step-level trace rendering and source citations, deployment runbook.
  - missing: production-hardened Chainlit auth callback UX and full HuggingFace Spaces validation pass.

## Definition of Done Snapshot

- End-to-end private upload/query for PDF/DOCX/MD/TXT: `partial`
- Production-stable auth/memory/hybrid retrieval: `partial`
- Visible and debuggable agent traces: `implemented`
- Benchmarks + regression tests in CI quality gate: `partial`
- New user -> upload -> ask -> follow-up UAT: `partial`
- Public demo mode/quota/auth escalation validated: `partial`
- Docker deployment to HF Spaces documented and repeatable: `partial`

## Immediate Next Actions

1. Implement first-class Supabase OAuth callback UX in Chainlit.
2. Expand eval suite with golden datasets and failure-mode assertions; enforce in CI.
3. Validate HuggingFace Spaces deployment end-to-end using the runbook.
4. Upgrade retrieval quality with reranking and measurable benchmark targets.
