# Phase 2 Implementation Plan: Data Layer Hardening and Ingestion

Date: 2026-02-18
Scope: Replace seeded retrieval with real Supabase and Neo4j connectors, then add idempotent ingestion pipelines and validation.

## Goal

Move from Phase 1 seeded retrieval to real data-layer integrations while preserving a safe fallback path and the current API response contract.

## Non-Goals (This Iteration)

- Full production orchestration and critic-loop upgrades.
- Breaking API response changes.

## Scope and Deliverables

### 1) Configuration and mode toggles

Update `lattice/prototype/config.py` to support explicit runtime behavior:

- `USE_REAL_SUPABASE` (default: `false`)
- `USE_REAL_NEO4J` (default: `false`)
- `ALLOW_SEEDED_FALLBACK` (default: `true`)

Also ensure env coverage for active integration values:

- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`

### 2) Real document retriever (Supabase)

Extend `lattice/prototype/retrievers/document_retriever.py`:

- Keep seeded retriever for fallback.
- Add Supabase-backed retriever implementation.
- Preserve `SourceSnippet` output shape.
- Handle empty/no-result/error paths predictably.

### 3) Real graph retriever (Neo4j)

Extend `lattice/prototype/retrievers/graph_retriever.py`:

- Keep seeded retriever for fallback.
- Add Neo4j-backed retriever implementation.
- Support `NEO4J_DATABASE`.
- Preserve `SourceSnippet` output shape.

### 4) Service wiring and fallback behavior

Update `lattice/prototype/service.py`:

- Select seeded vs real retrievers using config toggles.
- Keep current endpoint contract unchanged.
- Apply fallback behavior when real connectors fail and fallback is enabled.

### 5) Validation and tests

Update or add tests under `tests/` to cover:

- Seeded mode only.
- Real mode enabled.
- Failure path with fallback enabled.
- Stable response contract in all modes.

### 6) Ingestion pipelines (idempotent and retry-safe)

Add scripts:

- `scripts/ingestion/ingest_private_documents.py`
  - parse/chunk/embed flow scaffold
  - deterministic chunk IDs
  - idempotent upsert semantics in Supabase
- `scripts/ingestion/ingest_graph_data.py`
  - deterministic node/edge identities
  - `MERGE`-based writes in Neo4j
  - retry-safe behavior for transient failures

### 7) Documentation updates

Update docs to match implementation and run flow:

- `Docs/phase2_data_layer_hardening_local_setup.md`
- `README.md`
- `.env.example`

Include a known-good dataset run and expected output checks.

## Execution Sequence

1. Config contract and mode toggles.
2. Supabase document retriever.
3. Neo4j graph retriever.
4. Service wiring for mode selection and fallback.
5. Tests for mode coverage and failure behavior.
6. Ingestion script implementation.
7. End-to-end validation and docs finalization.

## Acceptance Criteria

- `/api/prototype/query` response schema remains stable.
- With real flags enabled and valid credentials:
  - document retrieval uses Supabase
  - graph retrieval uses Neo4j
- With connector failure and fallback enabled:
  - request still succeeds via seeded retrieval
- Ingestion scripts are rerunnable without duplicate growth.
- Docs and env template reflect actual commands and variables.

## Risk Controls

- Safe defaults keep seeded retrieval active unless explicitly enabled.
- Fallback switch limits impact of service outages.
- Deterministic IDs and upserts prevent duplicate ingestion.
- Incremental rollout: retrieval integration first, ingestion second.

## Immediate Next Step

Start with Steps 1-5 (retriever integration and tests), then proceed to Steps 6-7 (ingestion + validation runbook).

## Current Status and Next Actions

### Completed in current branch

- Config toggles, real retrievers, service wiring, and fallback controls are implemented.
- Ingestion scripts for Supabase and Neo4j are implemented.
- Retrieval behavior is tuned for Netflix graph queries.

### Next actions (Phase 2 hardening)

1. **Data quality gates after ingestion**
   - Implemented: validation command checks Supabase and Neo4j health plus quality signals.
   - Added: `scripts/ingestion/validate_phase2_data.py` and `/health/data` support data outputs.

2. **Operational fallback visibility**
   - Implemented: `/health/data` reports real/seeded mode, fallback policy, and source readiness.

3. **RLS and key-path alignment**
   - Implemented: least-privilege retrieval key selection (`SUPABASE_KEY` first).
   - Implemented: service-role reserved for ingestion/validation admin paths.
   - Added: explicit opt-in flag `ALLOW_SERVICE_ROLE_FOR_RETRIEVAL` for local diagnostics.

4. **Retriever quality follow-up**
   - Add stronger ranking/reranking for mixed graph queries and reduce irrelevant fallback snippets.

5. **Integration test coverage**
   - Implemented: env-gated integration tests for Supabase and Neo4j retrieval with fallback disabled.
   - Added:
     - `tests/integration/test_supabase_retrieval.py`
     - `tests/integration/test_neo4j_retrieval.py`
   - Execution: `uv run pytest -m integration`
   - Current constraint: Supabase integration test uses service-role retrieval opt-in until user-auth JWT retrieval path is implemented.
