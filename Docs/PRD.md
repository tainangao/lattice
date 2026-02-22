# Product Requirements Document: Agentic Graph RAG Assistant

## 1) Product Vision

Build a production-grade **Agentic Graph RAG Assistant** that intelligently routes user queries between private uploaded documents and a shared, pre-ingested Neo4j knowledge graph.

The system will use a **FastAPI** backend, **LangGraph** for agentic orchestration, **Supabase (pgvector)** for private document embeddings, and **Neo4j** for structured shared knowledge. The application will enforce secure, user-scoped access for private files while providing conversational, multi-turn answers grounded in both data sources.

- Ingest private user files (PDF, DOCX, MD, TXT)
- Query private documents and/or a shared Neo4j knowledge graph
- Use agentic routing to select optimal retrieval strategy (document, graph, or hybrid)
- Provide accurate, grounded, multi-turn answers with memory
- Enforce secure, user-scoped access by default

---

## 2) Product Goals and Success Metrics

## Primary Goals

* Accurate answers grounded in cited evidence from either private docs or the graph.
* Seamless, synchronous private file workflow from upload to queryable state.
* Intelligent orchestration using LangGraph to determine the correct retrieval tool (Vector DB vs. Graph DB).
* Conversational continuity across turns.
* Reliable auth and user isolation.


---

## 3) User Personas

* **Analyst**: Uploads private research reports (PDF/DOCX) and asks comparative questions, combining insights from their private docs with the shared Netflix knowledge graph.
* **Demo User**: Explores the capabilities of the pre-ingested Netflix graph without an account, subject to quota limits.

---

## 4) Technical Stack Definition

To prevent dependency conflicts, the system MUST be built using the following core stack:

* **Backend Framework**: FastAPI
* **Agent Orchestration**: LangGraph (StateGraph, Tool Nodes, Conditional Edges)
* **Vector Database**: Supabase (pgvector)
* **Graph Database**: Neo4j (strictly for nodes/edges, no embeddings stored here)
* **LLM Integration**: LangChain standard interfaces (ChatModels, Embeddings)
* **Frontend**: Chainlit (Dockerized for HuggingFace Spaces)
* **Identity**: Supabase Auth

---

## 5) Functional Requirements

## FR-1 Authentication and Identity

- Supabase Auth is the required identity provider for login/sign-up.
- Support Supabase Auth email/password and Supabase-supported OAuth providers.
- Persistent sessions with refresh handling.
- All private operations require authenticated identity.
- User identity must be server-derived from Supabase JWT (`sub`) after signature/claim verification via Supabase JWKS.

Acceptance:

- Unauthorized private endpoints return 401.
- Authenticated user can upload/query own docs.
- Chainlit login/sign-up/session flows are implemented through Supabase Auth (no parallel custom auth system).

## FR-2 File Upload and Ingestion

- Support PDF, DOCX, MD, TXT upload with format-appropriate parsers (for example: PyMuPDF for PDF, python-docx for DOCX, native text readers for MD/TXT).
- Async ingestion pipeline: parse -> normalize -> chunk -> embed -> upsert.
- Job status visible in UI: queued/processing/success/failed.
- Deterministic chunk metadata with source, page, offsets, user_id.
- Runtime ingestion must generate and persist embeddings (not chunk-and-store only).

Acceptance:

- Uploaded PDF, DOCX, MD, and TXT files are queryable within target SLA.
- Parse failures are surfaced clearly to user.

## FR-3 Retrieval Layer

- Document retrieval: pgvector similarity + metadata filters + rerank.
- Graph retrieval: Cypher + graph-specific retrieval strategy.
- Hybrid merge and rerank with score normalization and dedupe.
- Retrieval must preserve source scope: private document retrieval is user-scoped; graph retrieval uses shared knowledge scope.
- Add query/embedding caching to reduce repeated retrieval and embedding cost for semantically repeated requests.

Acceptance:

- Count queries use query-specific strategy (aggregation path), not snippet truncation.
- Retrieval result quality meets benchmark dataset thresholds.

## FR-4 Agentic Orchestration

- Router agent chooses direct/document/graph/hybrid/aggregate tool path.
- Retriever agents run in parallel when needed.
- Critic agent can trigger bounded refinement.
- Planner/executor tool-calling loop with max-steps and guardrails.

Acceptance:

- Tool calls and decisions logged in trace.
- No unbounded loops; deterministic stop criteria.

## FR-5 Multi-Turn Memory

- Conversation memory with short-term turn context + optional long-term preferences.
- Follow-up queries must resolve references ("that movie", "this doc").

Acceptance:

- Multi-turn benchmark passes reference resolution tests.

## FR-6 Response and Citations

- Answers must cite sources with stable source IDs and location metadata.
- Low-confidence policy must be explicit and actionable.
- Distinguish infra failure vs low evidence.

Acceptance:

- No uncited retrieval-based claims in production mode.

## FR-7 Observability and Evaluation

- Structured telemetry for route, tools, latency, confidence, errors.
- Offline evaluation suite (golden questions + regression checks).

Acceptance:

- Release requires green eval suite + SLO checks.

## FR-8 Onboarding and Access Modes

- Provide a public demo mode for unauthenticated users with configurable session query quota.
- Preserve dual-mode UX: public demo for shared knowledge queries, authenticated mode for private file features.
- Upload attempts in public mode must trigger clear auth escalation guidance.
- Show remaining demo quota and clear next actions in UI.

Acceptance:

- Unauthenticated users can query shared graph/document demo scope up to quota.
- Private upload and private retrieval are blocked until Supabase Auth session is active.
- Public mode never exposes private user data.

## FR-9 Runtime Key Handling

- Support stateless, user-provided Gemini key handling for runtime requests.
- Support session-scoped key lifecycle controls in chat UI (set/clear/help semantics).
- Never persist user Gemini keys to disk or long-lived server storage.

Acceptance:

- Runtime key can be set and cleared within a session without server-side persistence.
- If no user key is present, app behavior is explicit (demo limits, degraded mode, or guidance).

## FR-10 Chainlit UX and Deployment

- Chainlit must show step-level execution visibility for router, retrieval branches, critic, and synthesis.
- Final answers should include clickable source references and concise confidence messaging.
- Deploy as a Dockerized app targeting HuggingFace Spaces runtime.

Acceptance:

- Users can see agent workflow progress, not just final answer text.
- Deployment runbook covers startup checks, readiness checks, and incident recovery basics.

---

## 5) Non-Functional Requirements

- **Security**: strict RLS, no service-role use in user query path.
- **Performance**: p95 response <= 12s at expected concurrency.
- **Reliability**: graceful degraded mode with transparent messaging.
- **Scalability**: async pipeline, queue-backed ingestion.
- **Maintainability**: clear module contracts, high test coverage on critical paths.
- **Operational Cost Control**: enforce quota/caching guards suitable for free-tier constrained environments.

---

## 6) Out of Scope (v1)

- Advanced multimodal OCR/table extraction beyond baseline PDF/DOCX/MD/TXT support.
- Enterprise SSO/SAML.
- Autonomous long-running background research agents.

---

## 7) Definition of Done (v1)

- End-to-end private upload works for PDF, DOCX, MD, and TXT and is queryable.
- Auth, memory, and hybrid retrieval are production-stable.
- Agent tool traces are visible and debuggable.
- Benchmarks + regression tests pass in CI.
- User journey (new user -> upload -> ask -> follow-up) passes UAT.
- Public demo mode, quota UX, and auth escalation flow are validated.
- Docker deployment to HuggingFace Spaces is documented and repeatable.
