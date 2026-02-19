# Phase 5 Runbook: Hugging Face Spaces (Docker, real_connectors)

Date: 2026-02-19
Space: `sunkistCAT/lattice` (public)

## 1) Space configuration

- SDK: `Docker`
- Visibility: `public`
- Port: `7860` (set by README frontmatter and container command)

## 2) Required Space Secrets

Set these in Space Settings -> Variables and secrets -> Secrets:

- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`

Optional (GraphRAG experiment path only):

- `OPENAI_API_KEY`

## 3) Recommended Space Variables

Set these in Space Settings -> Variables and secrets -> Variables:

- `USE_REAL_SUPABASE=true`
- `USE_REAL_NEO4J=true`
- `ALLOW_SEEDED_FALLBACK=true`
- `ALLOW_SERVICE_ROLE_FOR_RETRIEVAL=false`
- `SUPABASE_DOCUMENTS_TABLE=embeddings`
- `NEO4J_DATABASE=neo4j`
- `NEO4J_SCAN_LIMIT=200`
- `PHASE4_ENABLE_CRITIC=true`
- `PHASE4_CONFIDENCE_THRESHOLD=0.62`
- `PHASE4_MIN_SNIPPETS=2`
- `PHASE4_MAX_REFINEMENT_ROUNDS=1`
- `PHASE4_INITIAL_RETRIEVAL_LIMIT=3`
- `PHASE4_REFINEMENT_RETRIEVAL_LIMIT=5`
- `PUBLIC_DEMO_QUERY_LIMIT=3`

## 4) Push and deploy

From local repository:

```bash
./scripts/deploy_hf.sh
```

Optional override (remote + target branch):

```bash
./scripts/deploy_hf.sh huggingface main
```

After push, Space rebuild starts automatically.

## 5) Post-deploy checks

1. Space build is `Running` (no Docker build errors)
2. `GET /health` returns `{"ok": true}`
3. `GET /health/data` returns 200 or expected connector diagnostics
4. `POST /api/prototype/query` returns answer + snippets
5. Chainlit route `/chainlit` loads and answers sample question

## 6) Runtime key handling

- API: request-scoped key via `X-Gemini-Api-Key` header.
- Chainlit: session-scoped key via `/setkey <key>` command.
- Chainlit: remove session key with `/clearkey`; show command help with `/help`.
- Keys are not persisted to repository files.

## 7) Known operational notes

- If HF push returns intermittent HTTP 500, retry push and verify remote HEAD sync.
- Keep seeded fallback enabled during first production shakedown to avoid hard outages.
