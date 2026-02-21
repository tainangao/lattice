---
title: Lattice Agentic Graph RAG
emoji: 🧭
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: main.py
pinned: false
app_port: 7860
startup_duration_timeout: 45m
---

# Lattice: Agentic Graph RAG v1 Rebuild

This repository is now on a v1 rebuild track based on `Docs/PRD.md`.

The previous prototype has been archived on branch `archive/prototype-2026q1`.

## Current State

- FastAPI bootstrap app for rebuild work
- New FR-aligned package layout under `lattice/app/`
- Legacy prototype runtime and tests removed from `main`

## Local Quickstart

1. Install dependencies:

```bash
uv sync
```

2. Run the API:

```bash
uv run uvicorn main:app --reload
```

3. Verify bootstrap endpoints:

- `GET /`
- `GET /health`
- `GET /ready`
- `GET /api/v1/status`
- `GET /api/v1/auth/session` (requires `Authorization: Bearer <supabase-jwt>`)
- `GET /api/v1/demo/quota`
- `POST /api/v1/runtime/key`
- `POST /api/v1/private/ingestion/upload` (requires auth)
- `GET /api/v1/private/ingestion/jobs` (requires auth)
- `GET /api/v1/observability/traces` (requires auth)
- `POST /api/v1/query`

## Offline Evaluation

Run the PRD regression checks locally:

```bash
uv run python scripts/eval/run_offline_eval.py
```

## Auth Scaffold Environment

- `SUPABASE_URL` (used to derive JWKS URL)
- `SUPABASE_JWKS_URL` (optional explicit override)
- `SUPABASE_JWT_AUDIENCE` (optional)
- `SUPABASE_JWT_ISSUER` (optional override)

## Retrieval and Graph Environment

- `SUPABASE_ANON_KEY` (required for PostgREST/RPC with user JWT)
- `EMBEDDING_DIMENSIONS` (default `1536`)
- `EMBEDDING_BACKEND` (`deterministic` or `google`)
- `GEMINI_EMBEDDING_MODEL` (default `models/gemini-embedding-001`)
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- `ENABLE_LANGGRAPH` (default `true`; falls back safely if package unavailable)
- `CRITIC_BACKEND` (`deterministic` or `google`)
- `CRITIC_MODEL` (default `gemini-2.5-flash`)
- `CRITIC_MAX_REFINEMENTS` (default `1`)

## Rebuild Source of Truth

- Product requirements: `Docs/PRD.md`
