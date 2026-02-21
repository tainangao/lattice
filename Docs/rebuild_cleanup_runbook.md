# Rebuild Cleanup Runbook (Archive-and-Rebuild)

This runbook captures the cleanup strategy and what has already been executed.

## Locked Decisions

- Keep only `Docs/new_app_requirements.md` as active product requirements on `main`.
- Do not keep `Docs/requirements_traceability.md` on `main`.
- Do not keep `Docs/gap_closure_plan.md` on `main`.
- Push archive branch only to `origin`.

## Executed (Completed)

1. Created archive branch from current state:
   - `archive/prototype-2026q1`
2. Added missing planning/review docs to archive history and committed them.
3. Created annotated snapshot tag:
   - `snapshot-pre-rebuild-2026-02-21`
4. Pushed archive branch and tag to `origin` only.

## Verification Commands

```bash
git ls-remote --heads origin archive/prototype-2026q1
git ls-remote --tags origin snapshot-pre-rebuild-2026-02-21
```

## Cleanup Steps Completed on `main`

1. Removed legacy phase/roadmap/prototype-planning docs to reduce source-of-truth drift.
2. Kept `Docs/new_app_requirements.md` as primary requirements source.
3. Removed `lattice/prototype/**` and prototype-only tests.
4. Created FR-aligned v1 package layout:
   - `lattice/app/auth`
   - `lattice/app/ingestion`
   - `lattice/app/retrieval`
   - `lattice/app/graph`
   - `lattice/app/orchestration`
   - `lattice/app/memory`
   - `lattice/app/response`
   - `lattice/app/observability`
5. Replaced `main.py` with a minimal v1 API skeleton.
6. Rewrote `README.md` for v1 bootstrap context.

## Next Planned Pass

1. Trim dependency set in `pyproject.toml` to v1 bootstrap minimum. (Done)
2. Introduce initial Supabase Auth verification boundary for FR-1 scaffolding. (Done)
3. Add v1 endpoint namespaces for auth, ingestion, retrieval, and query orchestration. (In progress)

## FR-1 Scaffold Added

- Added Supabase JWT verification module scaffold under `lattice/app/auth/`.
- Added protected auth session endpoint: `GET /api/v1/auth/session`.
- Added protected private probe endpoint: `GET /api/v1/private/ping`.
- Added unit tests for unauthorized, verified, and auth-config-error paths.
