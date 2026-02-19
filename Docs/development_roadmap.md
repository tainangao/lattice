# Development Roadmap: Agentic Graph RAG Application (Prototype-First)

This roadmap is organized to deliver visible user results early, then incrementally harden infrastructure, quality, and production readiness.

### Phase 1: Working Prototype (Result First)

**Goal:** Deliver an end-to-end demo quickly with minimal setup and one happy-path query flow.

* **Prototype Scope:**
* Build a Chainlit chat flow that can answer a user question using at least one retrieval source.
* Support one sample private document and one small seeded graph dataset.

* **Minimal Retrieval Path:**
* Implement Router Agent with basic routing rules (direct answer vs retrieval).
* Enable Retriever Bank in simplified mode:
* **Agent A (Unstructured):** Supabase vector retrieval on a small test corpus.
* **Agent B (Graph):** Basic Neo4j retrieval (hybrid mode or reduced traversal depth).
* Return a synthesized response with source references.

* **Success Criteria:**
* User can ask a multi-source question and receive one grounded answer in the UI.
* End-to-end latency and correctness are measurable, even if not yet optimized.

### Phase 2: Data Layer Hardening & Ingestion

**Goal:** Strengthen the prototype's data foundations after proving value.

* **Database Setup:**
* Finalize Supabase schema for embeddings and metadata.
* Provision and standardize Neo4j AuraDB for the shared graph knowledge base.
* Add Row Level Security (RLS) for private document access.

* **Ingestion Pipelines:**
* **Private Files:** Implement production-ready PyMuPDF parsing, chunking, and embedding.
* **Shared Graph:** Build an admin ingestion pipeline to extract entities and relationships with strict schema controls.

* **Data Quality:**
* Add validation checks for chunk quality, node-label constraints, and ingestion failures.

### Phase 3: Core Agentic Orchestration (Scale from Prototype)

**Goal:** Upgrade from basic flow to robust parallel orchestration.

**Status (2026-02-19):** Closed for core scope. GraphRAG migration is deferred follow-up.

* **LangGraph Orchestration:**
* Implement full fan-out/fan-in flow with explicit state transitions.
* Run retrieval agents concurrently with Python `asyncio` to reduce latency.

* **Router Improvements:**
* Expand routing logic for mixed-intent handling and fallback behavior.
* Add structured telemetry for routing and retrieval outcomes.

* **Retriever Enhancements:**
* Improve graph retrieval depth and vector ranking quality.

* **Execution note (2026-02-19):**
* `neo4j-graphrag` migration is on hold and treated as optional follow-up, not a Phase 3 close blocker.
* Phase 3 closure focuses on shipped LangGraph fan-out/fan-in orchestration, routing hardening, telemetry, and regression stability with current retrievers.

### Phase 4: Critic, Feedback Loops, and Answer Quality

**Goal:** Improve trustworthiness and reasoning quality (Agent-G features).

**Status (2026-02-19):** In progress.

* **Progress audit (2026-02-19, updated):**
* **Done:**
  * Step A complete: Dockerized Space baseline is live (`app_port: 7860`, startup timeout configured).
  * Step B complete: runtime secrets/variables are documented and consumed via env-based config.
  * Step C complete: API supports request-scoped `X-Gemini-Api-Key`; Chainlit supports session-scoped `/setkey`.
  * Step D complete: operational runbook exists with Space secrets/variables, health checks, and deploy flow (`./scripts/deploy_hf.sh`).
  * Step E baseline complete: regression coverage exists for key runtime/deployment paths with seeded fallback behavior preserved.
* **Not done yet:**
  * Chainlit onboarding polish is partial (command UX and guidance are improving, but full user journey copy and affordances still need refinement).
  * Cold-start flow is partially implemented (public demo quota + key escalation started, auth layer still pending by design).
  * Security hardening follow-up remains: explicit RLS policy verification checklist and deployment-time validation evidence.
  * Basic monitoring is partial: health endpoints and telemetry events exist, but no consolidated production dashboard/alerts yet.
  * Final Phase 5 close criteria and sign-off checklist are not yet documented.

* **Execution strategy (quality vs speed):**
* Ship a pragmatic single-pass critic + one bounded refinement loop first, behind config defaults.
* Keep all behavior additive and non-breaking to preserve Phase 3 API contract and velocity.
* Defer heavyweight multi-agent critic chains until baseline quality telemetry is stable.

* **Critic Module:**
* Score relevance and confidence of graph and document evidence.
* Flag weak retrieval sets before final generation.

* **Feedback Loops:**
* Trigger selective re-query or refinement when confidence is low.
* Add safeguards to prevent runaway retries.

* **Synthesis Quality:**
* Enforce grounded responses with clear source citations.

* **Phase 4 implementation plan (current):**
* **Step A (core critic):** Add deterministic critic scoring in orchestration using snippet count, score quality, source diversity, and citation signal checks.
* **Step B (bounded feedback loop):** Add at most one configurable refinement round that increases retrieval depth/limit and re-runs fan-out/fan-in.
* **Step C (guardrails):** Add safeguards for runaway retries (`max_refinement_rounds`), direct-route bypass, and telemetry visibility of critic outcomes.
* **Step D (tests):** Add orchestration tests for low-confidence refinement, no-refinement direct path, and bounded retry behavior.
* **Step E (evaluation):** Compare pre/post confidence and latency from telemetry before considering richer iterative loops.

* **Phase 4 acceptance criteria (increment 1):**
* Critic emits confidence + reason codes per request.
* Low-confidence retrieval can trigger one controlled refinement loop.
* Loop terminates deterministically with no infinite retries.
* Response contract remains unchanged for `/api/prototype/query`.
* Regression tests stay green.

* **Progress update (2026-02-19):**
* Increment 1 is implemented (critic scoring + bounded refinement loop + tests).
* Increment 2 is implemented (grounded-answer enforcement, low-confidence policy tiers, and quality summary telemetry fields including confidence bucket and refinement trigger rate).
* Next focus: calibrate confidence thresholds against production telemetry and finalize Phase 4 close criteria.

### Phase 5: Frontend, Security, and Production

**Goal:** Ship a secure, user-friendly product for real usage.

**Status (2026-02-19):** In progress.

* **Execution strategy (quality vs speed):**
* Prioritize deployability and operational safety first (Hugging Face Docker Space + env-secret workflow), then incrementally polish UX.
* Keep API contract stable and avoid large architecture changes while hardening deployment/security paths.

* **UI and Onboarding:**
* Polish the Chainlit experience with step-level agent visibility.
* Implement the cold-start flow (public demo quota, then auth and key flow).

* **Security Hardening:**
* Enforce Supabase RLS policy boundaries.
* Keep API key handling stateless through WebSocket headers.

* **Deployment:**
* Dockerize the app and deploy to HuggingFace Spaces.
* Add basic monitoring and operational runbooks.

* **Phase 5 implementation plan (current):**
* **Step A (Spaces deployment baseline):** Add Dockerfile + Spaces metadata + startup timeout and app port alignment for Hugging Face Docker Spaces.
* **Step B (runtime secrets):** Standardize Secrets/Variables usage for `real_connectors` deployment and remove repo-coupled secret assumptions.
* **Step C (stateless key handling):** Support request-scoped Gemini key override for API and ephemeral session key override for Chainlit.
* **Step D (operational runbook):** Document Space secrets/variables, health checks, and push/deploy workflow.
* **Step E (hardening pass):** Keep full tests green and preserve fallback behavior when connectors or keys are missing.

* **Phase 5 acceptance criteria (increment 1):**
* App runs on Hugging Face Docker Space with `app_port: 7860`.
* Production secrets are configured through Space settings, not committed files.
* API supports per-request runtime key override without server-side persistence.
* Chainlit supports session-level runtime key override without disk persistence.
* Full regression suite remains green.

* **Current build focus (started 2026-02-19):**
* Add cold-start UX controls in Chainlit (public demo quota, clear key lifecycle commands, and user-visible quota feedback).
* Keep API contract unchanged while improving frontend onboarding behavior.

## Milestone Summary

1. **Prototype Demo Ready:** End-to-end answer flow in Chainlit.
2. **Data Foundations Stable:** Reliable ingestion and secure storage.
3. **Agentic Orchestration Mature:** Parallel retrieval and stronger routing.
   - `neo4j-graphrag` adoption remains deferred until provider/runtime prerequisites are stable.
4. **Quality Layer Active:** Critic and feedback loops in production logic.
5. **Production Launch:** Hardened UX, security, and deployment.
