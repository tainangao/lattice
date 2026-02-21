# HuggingFace Spaces Deployment Runbook

## Scope

Operational runbook for deploying `lattice` to HuggingFace Spaces with Docker.

## Required Variables

Set these in the Space secrets/environment:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_JWKS_URL` (optional when `SUPABASE_URL` is set)
- `SUPABASE_JWT_AUDIENCE` (if configured in Supabase)
- `SUPABASE_JWT_ISSUER` (if needed)
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`
- `EMBEDDING_BACKEND`
- `GEMINI_EMBEDDING_MODEL`
- `CRITIC_BACKEND`
- `CRITIC_MODEL`
- `CRITIC_MAX_REFINEMENTS`
- `RERANK_BACKEND`
- `RERANK_MODEL`
- `PLANNER_MAX_STEPS`
- `GEMINI_API_KEY` (optional fallback if users do not provide session keys)
- `SUPABASE_OAUTH_REDIRECT_URL` (set to `/api/v1/auth/oauth/callback` route)

## Build and Startup

1. Space SDK: Docker.
2. Image build uses `Dockerfile` at repo root.
3. Start command inside image:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}
```

## Readiness Checks

After deployment, verify:

1. `GET /health` returns `{"ok": true}`.
2. `GET /api/v1/status` reports rebuild source `Docs/PRD.md`.
3. Authenticated check: `GET /api/v1/auth/session` with a valid Supabase JWT returns `user_id`.
4. Demo path: `POST /api/v1/query` with `X-Demo-Session` returns route + citations.

## Incident Recovery Basics

### Symptom: auth failures (401/503)

- Validate Supabase URL/JWKS/audience/issuer settings.
- Confirm JWT is from the same Supabase project.

### Symptom: document retrieval is empty

- Verify ingestion job status at `/api/v1/private/ingestion/jobs/{job_id}`.
- Verify Supabase SQL schema/RPC setup from `scripts/ingestion/supabase_phase2_schema.sql`.
- Check RLS policies allow authenticated user access to own rows.

### Symptom: graph retrieval is empty

- Validate Neo4j URI/credentials/database.
- Run integration check: `pytest -m integration` in a similarly configured environment.

### Symptom: high latency/timeouts

- Lower `CRITIC_MAX_REFINEMENTS` to `0` temporarily.
- Set `EMBEDDING_BACKEND=deterministic` and/or `CRITIC_BACKEND=deterministic` to degrade gracefully.

## Rollback

1. Revert Space to prior commit/image.
2. Re-run readiness checks above.
3. Preserve incident notes with failing endpoint, timestamp, and environment deltas.
