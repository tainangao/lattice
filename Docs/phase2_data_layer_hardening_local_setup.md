# Phase 2: Data Layer Hardening and Ingestion (Local-First Setup)

Date: 2026-02-18
Scope: Supabase + Neo4j environment setup, bootstrap, and verification

## Why this exists

Phase 2 shifts the project from seeded retrieval toward real data systems. This setup keeps local iteration fast while still supporting hosted services (Supabase cloud and Neo4j Aura).

## Prerequisites

- `uv` installed
- Python 3.11+
- Supabase project (hosted or local CLI stack)
- Neo4j target (Aura or local Neo4j instance)

## Environment contract

Use `.env.example` as the source of truth and copy to `.env`.

Required now:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`

Runtime toggles:

- `USE_REAL_SUPABASE` (default `false`)
- `USE_REAL_NEO4J` (default `false`)
- `ALLOW_SEEDED_FALLBACK` (default `true`)

Recommended for Neo4j/Aura:

- `NEO4J_DATABASE` (default: `neo4j`)
- `AURA_INSTANCEID`
- `AURA_INSTANCENAME`

Recommended for ingestion:

- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DOCUMENTS_TABLE` (default: `embeddings`)
- `NEO4J_SCAN_LIMIT` (default: `200`)

## Bootstrap script

Run this once per machine or when env values change:

```bash
./scripts/setup/phase2_bootstrap.sh
```

What it does:

1. Ensures `uv` is installed.
2. Creates `.env` from `.env.example` if missing.
3. Loads `.env` into the current shell process.
4. Runs `uv sync`.
5. Verifies:
   - prototype seed paths are present,
   - Supabase REST endpoint is reachable,
   - Neo4j connection and `RETURN 1` query succeed.

## Command-by-command verification

Run these commands in order from repo root.

1. Sync dependencies:

```bash
uv sync
```

2. Create env file if you do not have one:

```bash
cp .env.example .env
```

3. Fill `.env` with real credentials (Supabase + Neo4j).

4. Verify connectivity directly:

```bash
set -a && source .env && set +a
uv run python scripts/setup/verify_phase2_connections.py
```

Expected result: all checks print `[OK]` and the script exits successfully.

5. Run API server:

```bash
uv run uvicorn main:app --reload
```

6. Validate health endpoint:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected response:

```json
{"ok": true}
```

7. Validate prototype query endpoint:

```bash
curl -s -X POST http://127.0.0.1:8000/api/prototype/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How does the timeline compare to graph dependencies?"}'
```

Expected response includes:

- `route.mode` as one of `document`, `graph`, or `both`
- `answer` with a grounded response
- `snippets` array with source entries

8. Validate data-layer health endpoint:

```bash
curl -s http://127.0.0.1:8000/health/data
```

Expected response includes:

- `retriever_mode` showing real-vs-seeded settings
- `supabase.status` and `neo4j.status`
- `ok` set based on readiness and fallback policy

## Notes for Supabase local-first

- If you are running a local Supabase stack, set `SUPABASE_URL` to your local API URL.
- Keep `SUPABASE_KEY` aligned with the mode you are testing:
  - anon key for user-facing read paths,
  - service-role key for ingestion/admin workflows.

## Next implementation step after setup

## Retrieval mode switching

To enable real connectors for local tests:

```bash
set -a && source .env && set +a
export USE_REAL_SUPABASE=true
export USE_REAL_NEO4J=true
export ALLOW_SEEDED_FALLBACK=true
uv run uvicorn main:app --reload
```

With fallback enabled, the app returns seeded results if real connectors fail.

## Ingestion commands

After `.env` is configured, run ingestion jobs from repo root.

Private documents to Supabase:

```bash
set -a && source .env && set +a
uv run python scripts/ingestion/ingest_private_documents.py
```

Graph edges to Neo4j:

```bash
set -a && source .env && set +a
uv run python scripts/ingestion/ingest_graph_data.py
```

Netflix CSV to Neo4j (local file ingestion via Python driver):

```bash
set -a && source .env && set +a
uv run python scripts/ingestion/ingest_netflix_csv_neo4j.py
```

Optional Cypher-only load script (requires CSV URL reachable by Neo4j):

- `scripts/ingestion/neo4j_netflix_load.cypher`

Post-ingestion data quality validation:

```bash
set -a && source .env && set +a
uv run python scripts/ingestion/validate_phase2_data.py
```

Idempotency behavior:

- Document ingestion uses deterministic `id` values and upserts on conflict.
- Graph ingestion uses `MERGE` for nodes and relationships.
