# Product Requirements Document: Agentic Graph RAG Assistant

## 1) Product Vision

Build a production-grade **Agentic Graph RAG Assistant** that intelligently routes user queries between private uploaded documents and a shared, pre-ingested Neo4j knowledge graph.

The system will use a **FastAPI** backend, **LangGraph** for agentic orchestration, **Supabase (pgvector)** for private document embeddings, and **Neo4j** for structured shared knowledge. The application will enforce secure, user-scoped access for private files while providing conversational, multi-turn answers grounded in both data sources.

---

## 2) Product Goals and Success Metrics

### Primary Goals

* Accurate answers grounded in cited evidence from either private docs or the graph.
* Seamless, synchronous private file workflow from upload to queryable state.
* Intelligent orchestration using LangGraph to determine the correct retrieval tool (Vector DB vs. Graph DB).

### KPIs (first 60 days)

* Upload-to-query success rate >= 95%.
* Median first-answer latency <= 8s; p95 <= 15s (accounting for synchronous ingestion and LangGraph routing).
* Citation presence in >= 98% retrieval answers.
* Cross-user retrieval leakage = 0.

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

### FR-1 Authentication and Identity

* Supabase Auth is the required identity provider.
* Persistent sessions with refresh handling via the Chainlit/FastAPI integration.
* User identity must be server-derived from Supabase JWT (`sub`).

### FR-2 File Upload and Synchronous Ingestion

* Support PDF, DOCX, MD, TXT upload.
* **Synchronous Pipeline**: Ingestion (parse -> chunk -> embed -> upsert to Supabase) must happen synchronously during the HTTP request. The UI will block/show a loading state until complete.
* Embeddings are strictly stored in Supabase `pgvector` alongside chunk metadata (user_id, source, page).
* *Constraint*: Do not write document data to Neo4j.

### FR-3 Retrieval Layer

* **Document Retrieval (Supabase)**: `pgvector` similarity search filtered strictly by the authenticated `user_id`.
* **Graph Retrieval (Neo4j)**: Query the pre-ingested Netflix Shows dataset. Use a Text-to-Cypher generation chain (similar to LangChain's GraphQA) to intelligently navigate nodes and relationships based on the user's natural language query.
*
* *Constraint*: Neo4j retrieval does not use vector similarity; it relies purely on LLM-generated Cypher queries executing against the existing schema.

### FR-4 Agentic Orchestration (LangGraph)

* Implement a LangGraph `StateGraph` with the following nodes:
* **Router**: Analyzes the query and decides the execution path.
* **Private Doc Tool**: Executes the Supabase vector retrieval.
* **Netflix Graph Tool**: Executes the Neo4j Cypher generation and retrieval.
* **Generation**: Synthesizes the retrieved context into a final answer.


* The graph state must pass the conversation history, the current query, and the stateless LLM API key.

### FR-5 Multi-Turn Memory

* Managed via LangGraph's checkpointer or by maintaining message history in the frontend state and passing it to the FastAPI backend on each turn.
* Follow-up queries must resolve references accurately.

### FR-6 Response and Citations

* Answers must cite sources explicitly (e.g., "According to your uploaded document `Q3_Report.pdf`..." or "Based on the Netflix Graph...").
* If a Cypher query fails or returns empty, the agent must gracefully report a lack of information rather than hallucinating.

### FR-8 Onboarding and Access Modes

* **Public Demo Mode**: Unauthenticated users can only trigger the LangGraph route for the shared Netflix Neo4j graph.
* **Authenticated Mode**: Users can upload private files and trigger both the Supabase and Neo4j routes.

### FR-9 Runtime Key Handling (Stateless)

* Support stateless, user-provided Gemini/LLM keys.
* Because ingestion is synchronous (FR-2), the key provided in the active HTTP request is used directly to generate embeddings and execute LLM calls, then immediately discarded.
* Never persist user keys to disk or database.

---

## 6) Non-Functional Requirements

* **Security**: Strict PostgreSQL RLS on the documents table.
* **Architecture**: Clean separation of concerns between the Chainlit frontend, FastAPI backend, and LangGraph orchestration.
* **Deployment**: Dockerized app targeting HuggingFace Spaces runtime.

---

## 7) Definition of Done (v1)

* LangGraph successfully routes queries about "stranger things" to Neo4j, and queries about "my uploaded report" to Supabase.
* End-to-end private upload works synchronously and is immediately queryable.
* Text-to-Cypher generates valid queries against the pre-ingested Netflix schema.
* User keys are handled statelessly without breaking the ingestion flow.
* Docker deployment is fully documented.
