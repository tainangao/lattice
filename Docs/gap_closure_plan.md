# Concrete Gap-Closure Plan

## Strategy Recommendation

Use a **stabilize-then-upgrade** approach:

1) Fix correctness/security/UX blockers first.
2) Add true agent/tool architecture and memory next.
3) Harden with evals and production controls.

Target: 6-8 weeks.

---

## Phase A (Week 1): Reality Baseline and Stop-the-Bleed

Deliverables:

- Freeze roadmap claims; publish "actual status" doc.
- Make CI green (fix retriever interface contract drift).
- Add explicit runtime mode banner in UI (prototype vs production).
- Disable misleading upload commands until real multi-format upload pipeline is live (PDF/DOCX/MD/TXT).

Exit criteria:

- Tests green.
- UX no longer implies unsupported behavior.

---

## Phase B (Weeks 1-2): Auth + Upload Foundation

Deliverables:

- Implement full Chainlit auth flow using Supabase Auth (login/sign-up/session persistence).
- Unify auth boundary so Chainlit private flows use JWT-verified backend endpoints.
- Implement onboarding and access modes: public demo quota, explicit auth escalation for private uploads, and clear quota/status messaging.
- Add multi-format ingestion endpoint and job tracking for PDF/DOCX/MD/TXT.
- Integrate format-appropriate parsing and metadata-rich chunking.
- Add embedding generation + vector persistence in runtime ingestion (close current chunk-only gap).
- Implement stateless runtime key handling with session-level set/clear/help lifecycle in chat UI.

Exit criteria:

- Authenticated user can upload PDF/DOCX/MD/TXT and see ingestion status.
- Unauthorized requests blocked consistently.
- Public mode/private mode boundaries are enforced and user-visible.

---

## Phase C (Weeks 2-3): Retrieval Correctness Upgrade

Deliverables:

- Replace token-overlap doc retrieval with vector similarity + filters.
- Add explicit aggregation/query-intent path for count/list/statistical questions.
- Rework graph retrieval to be schema-aware and domain-agnostic.
- Introduce retrieval confidence calibration dataset.

Exit criteria:

- "How many X" style queries no longer depend on snippet limit.
- Retrieval quality benchmark meets target.

---

## Phase D (Weeks 3-4): True Agentic Orchestration

Deliverables:

- Add planner agent + tool registry:
  - document_retrieve
  - graph_retrieve
  - graph_aggregate
  - answer_synthesize
  - critic_revise
- Convert deterministic router into LLM+policy router with fallback heuristics.
- Keep bounded refinement loop with max step and cost/latency limits.
- Add trace view in UI for each tool call and rationale summary.

Exit criteria:

- Tool-calling traces visible in logs/UI.
- At least one multi-step query class demonstrably better than deterministic path.

---

## Phase E (Weeks 4-5): Multi-Turn Memory and UX Polish

Deliverables:

- Conversation store (thread_id/session_id/user_id).
- Context window builder for follow-up questions.
- Better system feedback:
  - parse failure
  - auth failure
  - low evidence
  - connector failure
- Replace generic low-confidence message with actionable next steps.
- Add step-level Chainlit execution visibility for router, retrieval branches, critic, and synthesis.

Exit criteria:

- Follow-up benchmark passes.
- UX no longer returns opaque failure messages.

---

## Phase F (Weeks 5-6): Evaluation, Monitoring, and Release Readiness

Deliverables:

- Golden dataset for doc/graph/hybrid/multi-turn/count queries.
- Automated regression suite and quality gates in CI.
- Dashboards for latency, success rate, confidence, and error classes.
- Release checklist with evidence (security, RLS, eval, UAT, onboarding flow, runtime key behavior).
- Docker + HuggingFace Spaces deployment runbook validation (startup/readiness/recovery checks).

Exit criteria:

- All release gates pass.
- Stakeholder sign-off based on measured outcomes, not checklist-only claims.

---

## Workstreams and Ownership

- **Backend/Orchestration**: agent tools, planner, retrievers, critic loop.
- **Data/ML**: embeddings, rerank, query intent classification, eval dataset.
- **Frontend/UX**: auth UX, ingestion status, traces, error handling.
- **Platform/SRE**: CI quality gates, observability, runbooks, alerts.

---

## High-Risk Items + Mitigations

- Risk: connector failures masked by fallback
  Mitigation: explicit degraded mode + failure-type messaging + alerting.
- Risk: agent loop cost/latency blow-up
  Mitigation: max steps, timeout, tool budget.
- Risk: cross-user data leakage
  Mitigation: mandatory auth context + RLS verification tests per environment.
- Risk: roadmap drift again
  Mitigation: "claim requires evidence" policy for phase closure.

---

## Immediate Next 10 Tasks (Execution-Ready)

1. Fix retriever interface mismatch and make CI green.
2. Add "actual capabilities" banner in Chainlit UI.
3. Implement Chainlit auth callbacks and session persistence.
4. Route Chainlit upload through JWT-verified backend endpoint only.
5. Add PyMuPDF dependency and PDF parser service (baseline for multi-format ingestion).
6. Add parser stack for DOCX/MD/TXT and normalize multi-format metadata.
7. Implement ingestion job state + progress events.
8. Replace doc overlap retrieval with pgvector similarity query + caching.
9. Add count/aggregation query tool path for graph and source-scope tests.
10. Add conversation memory store, follow-up context packing, and release gate dashboard.
