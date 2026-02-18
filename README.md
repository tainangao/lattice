# Lattice: Phase 1 Working Prototype

This repository now contains a prototype-first Agentic Graph RAG demo.

## What is implemented

- FastAPI app with `GET /health` and `POST /api/prototype/query`
- Chainlit interface mounted at `/chainlit`
- Router agent (direct vs doc vs graph vs both)
- Fan-out retrieval over seeded document and graph datasets
- Fan-in synthesis with source citations
- Optional Gemini generation when `GEMINI_API_KEY` is set

## Quickstart

1. Install dependencies:

```bash
pip install -e .
```

2. Optional: copy env vars:

```bash
cp .env.example .env
```

3. Run the app:

```bash
uvicorn main:app --reload
```

4. Open:

- API docs: `http://127.0.0.1:8000/docs`
- Chainlit UI: `http://127.0.0.1:8000/chainlit`

## Example query

"How does the project timeline in my PDF compare to graph dependencies?"
