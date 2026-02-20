# gemini3_agentic_rag_app_plan.md

## Overview

This document outlines the design for an agentic RAG application tailored for complex knowledge retrieval. The system prioritizes **asynchronous agent orchestration** and **hybrid retrieval** (Graph + Vector).

**Key Architectural Shift:**

* **Frontend:** Switched from Streamlit to **Chainlit** to support native async streaming and "Chain of Thought" visualization.
* **Graph Engine:** Neo4j graph retrieval remains active via the current Cypher-based retriever path; `neo4j-graphrag` is paused and kept experimental behind flags.
* **Orchestration:** LangGraph with parallel execution (Fan-out/Fan-in) to reduce latency.

---

## Technical Stack

* **Frontend/App Server:** Chainlit (Python)
* **Orchestration:** LangGraph
* **Database (Relational & Vector):** Supabase (PostgreSQL + pgvector)
* **Database (Graph):** Neo4j (AuraDB)
* **LLM & Embeddings:** Google Gemini (via AI Studio)
* **Graph SDK (Experimental):** `neo4j-graphrag` (paused for Phase 3 closeout; retained behind config flags only)

---

## Delivery Phases (Prototype-First)

This plan follows a prototype-first delivery sequence so stakeholders can see results early before deeper platform hardening.

### Phase 1: Working Prototype (Result First)

* Deliver a Chainlit demo with one happy-path multi-source question flow.
* Enable basic routing and simplified retrievers for Supabase + Neo4j.
* Return grounded answers with source references.

### Phase 2: Data Layer Hardening & Ingestion

* Finalize Supabase and Neo4j data models and access patterns.
* Harden private file and shared graph ingestion pipelines.
* Enforce RLS and add ingestion quality checks.

### Phase 3: Core Agentic Orchestration (Scale from Prototype)

* Implement full LangGraph fan-out/fan-in state transitions.
* Improve routing logic and retrieval quality.
* Add telemetry for route and retrieval outcomes.
* Keep `neo4j-graphrag` migration out of the critical path until provider/runtime prerequisites are met.

### Phase 3 Status Note (Aligned with closeout plan)

* **Core Phase 3 scope is closed:** orchestration, routing, telemetry, and regression stability are complete.
* **GraphRAG adoption is on hold:** `neo4j-graphrag` remains deferred as a post-Phase-3 follow-up.
* **Resume criteria for GraphRAG:**
1. Stable embedding provider path is available in project runtime.
2. Preflight reports `ready_for_graphrag=true`.
3. Regression runs show live non-fallback backends (`graphrag_hybrid` and `graphrag_hybrid_cypher`).

### Phase 4: Critic, Feedback Loops, and Answer Quality

* Add critic scoring and low-confidence detection.
* Trigger selective re-query/refinement loops.
* Enforce source-grounded synthesis behavior.

### Phase 5: Frontend, Security, and Production

* Polish UI and onboarding for real usage.
* Complete security hardening and stateless key handling.
* Dockerize and deploy to HuggingFace Spaces.

### Phase 6: Authenticated Private Knowledge Workflows

* Implement Supabase Auth login/session flow for user-scoped actions.
* Add end-to-end private file workflow: upload -> parse -> chunk -> embed -> store.
* Enforce authenticated `user_id` assignment for private document ingestion and retrieval.
* Connect Chainlit upload interactions to backend ingestion jobs with clear user feedback.
* Preserve public demo mode while requiring auth for private file features.

#### Phase 6 Delivery Notes (Supabase Auth Free Tier)

* Supabase Auth can run on the Free plan for this phase, with current quota limits.
* Free-tier assumptions for planning:
1. Keep MAU usage within the free monthly quota.
2. Keep project count and storage footprint within free limits.
3. Treat pricing and quota values as externally managed and subject to future changes.

#### Phase 6 Implementation Checklist (Repo-Aligned)

1. **Auth session bridge (Chainlit -> backend):**
* Add login/session flow in Chainlit and pass user JWT to backend private endpoints.
* Require valid user JWT for private upload/ingestion actions.

2. **Upload entrypoint and ingestion trigger:**
* Add upload handling in Chainlit message flow for private documents.
* Add backend upload/ingestion endpoint(s) for authenticated users.

3. **Parser + chunk + embedding pipeline:**
* Parse uploaded files with PyMuPDF baseline.
* Apply deterministic chunking and embedding generation for each chunk.
* Upsert into Supabase `embeddings` with source metadata and `user_id`.

4. **User-scoped retrieval + RLS alignment:**
* Ensure retrieval uses user-scoped auth context (`auth.uid()` boundary).
* Remove service-role retrieval paths from user-query runtime flows.

5. **Validation and tests:**
* Add tests for login-required upload, successful authenticated ingest, and unauthorized rejection.
* Add tests for cross-user isolation in retrieval results.

---

## Core Agentic Architecture (LangGraph)

The application will use a **Fan-out / Fan-in** architecture inspired by the **Agent-G framework**. Instead of calling agents sequentially, the system employs a modular **Retriever Bank** and a **Critic Module** to ensure high accuracy.

### 1. Router Agent (Dynamic Assignment)

* **Role:** Analyzes user intent to dynamically assign retrieval tasks.
* **Logic:**
* *Direct Answer:* Routine greetings or out-of-scope queries.
* *Retrieval Assignment:* Determines if the query requires **Graph Knowledge Bases** (relationships/hierarchies) or **Unstructured Documents** (context), or both.


* **Output:** A routing state that triggers specific agents in the Retriever Bank simultaneously.

### 2. Retriever Bank (The "Fan-Out")

These processes run concurrently using Python `asyncio`, acting as specialized agents for different data types.

* **Agent A: Unstructured Document Retriever (Supabase)**
* **Scope:** User-uploaded documents (Row Level Security enabled).
* **Role:** Provides contextual information to complement graph data.
* **Method:** Standard dense vector retrieval using Gemini embeddings.


* **Agent B: Graph Retriever (Neo4j)**
* **Scope:** Shared organizational knowledge base.
* **Role:** Extracts relationships, hierarchies, and connections (e.g., project dependencies or ownership mappings).
* **Method (current):** Uses the existing Cypher-based graph retrieval path for reliability in production.
1. **Graph Retrieval:** Runs deterministic Cypher retrieval/ranking for graph-grounded snippets.
2. **Traversal Logic:** Uses Cypher-level traversal/depth behavior for relationship discovery.
3. **Experimental Modes (paused):** `neo4j-graphrag` (`HybridRetriever` / `HybridCypherRetriever`) remains config-gated and non-critical until resume criteria are satisfied.





### 3. Critic & Synthesis Layer (The "Fan-In")

* **Role:** Acts as the **Critic Module** and final synthesizer.
* **Logic:**
* **Critic Module:** Evaluates the relevance and quality of the retrieved graph and document data. Flags low-confidence results.
* **Feedback Loop:** If quality is below threshold, triggers a re-query or refinement step (optional iteration).
* **Generation:** The LLM integrates validated data into a coherent response, citing specific sources (e.g., *"According to file X..."*) and ensuring alignment with the query's intent.



---

## User Journey & UX (Chainlit Interface)

### Step 1: Onboarding (The "Cold Start" Fix)

To reduce friction, we remove the immediate requirement for an API Key.

1. **Welcome Screen:** Users see a "Public Demo" mode.
2. **Trial Quota:** Users can ask 5 questions against the *Shared Knowledge Base* using a system-provided backend key.
3. **Authentication:** When they attempt to **Upload a File**, they are prompted to:
* Log in (Supabase Auth).
* Enter their personal Gemini API Key (stored in browser local storage).



### Step 2: The Chat Experience

Chainlit provides native UI elements for agentic visibility.

* **User Query:** "How does the project timeline in my PDF compare to the engineering dependencies in the graph?"
* **Step UI (Visualized automatically by Chainlit):**
* *Router:* "Multi-source query detected."
* *Parallel Execution:*
* 🔵 [Running] `PrivateDocAgent` parsing 'timeline.pdf'...
* 🟢 [Running] `GraphAgent` scanning dependencies...


* *Critic:* "Validating relevance... 95% confidence."
* *Synthesis:* Merging contexts.


* **Final Output:** A unified answer with clickable footnotes to the source documents.

---

## Data Ingestion Pipelines

### 1. File Ingestion (Private)

* **Parser:** **PyMuPDF** for prototype-first simplicity and lower operational overhead; defer LlamaParse/Unstructured.io for a later phase if complex layout/table extraction becomes a requirement.
* **Process:**
1. User uploads file via Chainlit UI.
2. File is parsed into normalized text for chunking.
3. Text is chunked (parent-child chunking) and embedded.
4. Stored in Supabase `embeddings` table with `user_id`.



### 2. Graph Ingestion (Shared)

* **Process:** Admin-triggered pipeline.
* **Entity Extraction:** Uses Gemini to identify entities (Nodes) and relationships (Edges) from unstructured policy documents.
* **Schema Enforcement:** The LLM is constrained to a pre-defined set of Node Labels (e.g., `Person`, `Project`, `Department`) to prevent graph pollution.

---

## Security & Performance Considerations

### Performance

* **Parallelism:** By running Graph and Vector searches asynchronously, target response time drops from ~10s to ~4-5s.
* **Caching:** Implement `LangChain` caching to avoid re-embedding the same query multiple times.

### Security

* **Supabase RLS:** Row Level Security policies MUST be active.
* `SELECT * FROM embeddings WHERE user_id = auth.uid()`


* **Key Management:** The Gemini API Key is passed from the client in the `Authorization` header of the WebSocket handshake, ensuring the server remains stateless regarding user secrets.

## Deployment

* **Container:** Dockerized application (Chainlit + internal FastAPI router).
* **Hosting:** HuggingFace Spaces.
