# Rebuild Cleanup Runbook (Archive-and-Rebuild)

This runbook executes the agreed strategy:

- Keep an immutable archive branch of the current prototype.
- Push archive branch to `origin` only.
- Clean `main` for v1 rebuild aligned to `Docs/new_app_requirements.md`.

## Scope Decisions Locked

- Keep on `main`: `Docs/new_app_requirements.md`
- Do not keep on `main`: `Docs/requirements_traceability.md`, `Docs/gap_closure_plan.md`
- Push archive branch only to `origin`

## Preconditions

1. Working tree has no secrets staged.
2. `origin` remote is reachable.
3. Current branch is `main`.

## Phase 1 - Archive Snapshot

1. Create archive branch from current `main`.
2. Add and commit PRD/review planning docs that were still untracked.
3. Create annotated snapshot tag.
4. Push archive branch and tag to `origin` only.

Verification:

- `git branch --list archive/prototype-2026q1` shows branch exists.
- `git ls-remote --heads origin archive/prototype-2026q1` returns branch ref.
- `git ls-remote --tags origin snapshot-pre-rebuild-2026-02-21` returns tag ref.

## Phase 2 - Initial Main Cleanup

1. Return to `main`.
2. Remove `Docs/requirements_traceability.md`.
3. Remove `Docs/gap_closure_plan.md`.
4. Keep `Docs/new_app_requirements.md` as the sole active PRD source.

Verification:

- `git status --short` shows the two docs deleted on `main`.
- `Docs/new_app_requirements.md` still present.

## Phase 3 - Next Cleanup Pass (Planned)

1. Remove prototype runtime (`lattice/prototype/**`) from `main`.
2. Replace `main.py` and `lattice/chainlit_app.py` with v1 skeleton entrypoints.
3. Reset tests into FR-aligned suites (`unit`, `integration`, `e2e`).
4. Rewrite `README.md` to v1 architecture and execution model.

## Rollback

- Prototype rollback reference branch: `archive/prototype-2026q1`
- Snapshot tag: `snapshot-pre-rebuild-2026-02-21`
