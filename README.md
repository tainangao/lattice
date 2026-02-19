---
title: Lattice Agentic Graph RAG
emoji: 🧭
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
startup_duration_timeout: 45m
---

# Lattice: Agentic Graph RAG Prototype

This repository contains a prototype-first Agentic Graph RAG app with LangGraph orchestration, dual retrieval (document + graph), and quality-control loops.

## Implemented

- FastAPI app with `GET /health` and `POST /api/prototype/query`
- Chainlit interface mounted at `/chainlit`
- Router agent (direct vs doc vs graph vs both)
- Fan-out retrieval over seeded document and graph datasets
- Fan-in synthesis with source citations
- Optional Gemini generation when `GEMINI_API_KEY` is set
- Phase 4 critic and bounded refinement loop for low-confidence retrieval sets
- Runtime per-request key override for API via `X-Gemini-Api-Key` header

## Local Quickstart

1. Install dependencies:

```bash
uv sync
```

2. Optional: copy env vars:

```bash
cp .env.example .env
```

3. Run the app:

```bash
uv run uvicorn main:app --reload
```

4. Open:

- API docs: `http://127.0.0.1:8000/docs`
- Chainlit UI: `http://127.0.0.1:8000/chainlit`

## Session key override (Chainlit)

In Chainlit chat, set a temporary Gemini key for the current chat session:

```text
/setkey <your-gemini-key>
```

This key stays in memory for the active chat session only.

## API runtime key override

You can provide a request-scoped Gemini key without writing it to server config:

```bash
curl -X POST http://127.0.0.1:8000/api/prototype/query \
  -H "Content-Type: application/json" \
  -H "X-Gemini-Api-Key: $GEMINI_API_KEY" \
  -d '{"question":"How does the timeline compare to graph dependencies?"}'
```

## Hugging Face Spaces (Docker)

This repo is configured for Docker Spaces.

Required Space Secrets for `real_connectors` mode:

- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`

Recommended Space Variables:

- `USE_REAL_SUPABASE=true`
- `USE_REAL_NEO4J=true`
- `ALLOW_SEEDED_FALLBACK=true`
- `SUPABASE_DOCUMENTS_TABLE=embeddings`
- `NEO4J_DATABASE=neo4j`

## Example query

"How does the project timeline in my PDF compare to graph dependencies?"

## Phase 2 setup

For local-first Supabase + Neo4j bootstrap and verification, follow:

- `Docs/phase2_data_layer_hardening_local_setup.md`
