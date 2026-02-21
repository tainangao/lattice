# Requirements Traceability Matrix

This matrix maps `Docs/new_app_requirements.md` requirements to delivery phases in `Docs/gap_closure_plan.md` and concrete verification checks.

| Requirement | Gap-Closure Phase(s) | Verification Checks |
| --- | --- | --- |
| FR-1 Authentication and Identity | Phase B, Phase F | Supabase Auth login/sign-up works in Chainlit; backend derives user from verified Supabase JWT `sub`; unauthorized private endpoints return 401; no parallel custom auth path |
| FR-2 File Upload and Ingestion | Phase B, Phase F | PDF/DOCX/MD/TXT upload succeeds; parser -> chunk -> embed -> upsert pipeline runs; ingestion job status is visible; parse failures are user-visible |
| FR-3 Retrieval Layer | Phase C, Phase F | pgvector retrieval replaces overlap-only path; graph aggregation/count intent path works; private/shared scope isolation tests pass; caching behavior validated |
| FR-4 Agentic Orchestration | Phase D, Phase F | Planner + tool registry active; parallel retrieval and bounded refinement are observable; stop criteria enforced; tool trace telemetry is emitted |
| FR-5 Multi-Turn Memory | Phase E, Phase F | Follow-up reference tests pass ("that movie", "this doc"); conversation state persists by thread/session/user |
| FR-6 Response and Citations | Phase D, Phase E, Phase F | Retrieval-based answers include citations; low-confidence messaging differentiates weak evidence vs infra failure |
| FR-7 Observability and Evaluation | Phase F | Golden dataset and regression gates run in CI; dashboards include latency/success/confidence/error classes |
| FR-8 Onboarding and Access Modes | Phase B, Phase E, Phase F | Public demo quota flow works; private actions blocked until Supabase Auth session exists; auth escalation UX is clear and validated |
| FR-9 Runtime Key Handling | Phase B, Phase F | Session-level set/clear key lifecycle works; key is never persisted server-side; no-key behavior is explicit and tested |
| FR-10 Chainlit UX and Deployment | Phase E, Phase F | Step-level execution visibility appears in Chainlit; source-linked final answers render; Docker/HuggingFace Spaces runbook and readiness checks are validated |

## Notes

- Intentional exclusions per product direction: `neo4j-graphrag` adoption and graph ingestion rework are out of this traceability scope.
- If requirements change, update this matrix first, then update `Docs/gap_closure_plan.md` to keep planning and delivery in sync.
