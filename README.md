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

This repository is now on a v1 rebuild track based on `Docs/new_app_requirements.md`.

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

## Auth Scaffold Environment

- `SUPABASE_URL` (used to derive JWKS URL)
- `SUPABASE_JWKS_URL` (optional explicit override)
- `SUPABASE_JWT_AUDIENCE` (optional)
- `SUPABASE_JWT_ISSUER` (optional override)

## Rebuild Source of Truth

- Product requirements: `Docs/new_app_requirements.md`
- Cleanup runbook: `Docs/rebuild_cleanup_runbook.md`
