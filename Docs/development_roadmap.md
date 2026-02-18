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

* **LangGraph Orchestration:**
* Implement full fan-out/fan-in flow with explicit state transitions.
* Run retrieval agents concurrently with Python `asyncio` to reduce latency.

* **Router Improvements:**
* Expand routing logic for mixed-intent handling and fallback behavior.
* Add structured telemetry for routing and retrieval outcomes.

* **Retriever Enhancements:**
* Improve graph retrieval depth and vector ranking quality.

### Phase 4: Critic, Feedback Loops, and Answer Quality

**Goal:** Improve trustworthiness and reasoning quality (Agent-G features).

* **Critic Module:**
* Score relevance and confidence of graph and document evidence.
* Flag weak retrieval sets before final generation.

* **Feedback Loops:**
* Trigger selective re-query or refinement when confidence is low.
* Add safeguards to prevent runaway retries.

* **Synthesis Quality:**
* Enforce grounded responses with clear source citations.

### Phase 5: Frontend, Security, and Production

**Goal:** Ship a secure, user-friendly product for real usage.

* **UI and Onboarding:**
* Polish the Chainlit experience with step-level agent visibility.
* Implement the cold-start flow (public demo quota, then auth and key flow).

* **Security Hardening:**
* Enforce Supabase RLS policy boundaries.
* Keep API key handling stateless through WebSocket headers.

* **Deployment:**
* Dockerize the app and deploy to HuggingFace Spaces.
* Add basic monitoring and operational runbooks.

## Milestone Summary

1. **Prototype Demo Ready:** End-to-end answer flow in Chainlit.
2. **Data Foundations Stable:** Reliable ingestion and secure storage.
3. **Agentic Orchestration Mature:** Parallel retrieval and stronger routing.
4. **Quality Layer Active:** Critic and feedback loops in production logic.
5. **Production Launch:** Hardened UX, security, and deployment.
