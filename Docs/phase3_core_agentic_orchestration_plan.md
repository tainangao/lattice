# Phase 3 Implementation Plan: Core Agentic Orchestration (Scale from Prototype)

Date: 2026-02-19
Scope: Introduce LangGraph fan-out/fan-in orchestration, stronger routing, and telemetry while preserving the current API contract.

## Implementation status (as of 2026-02-19)

### Completed

- LangGraph orchestration module created with typed state and reducer-safe fields.
- Router, retrieval branch, merge, synthesize, and finalize nodes are implemented.
- `PrototypeService` delegates query execution through the orchestration graph (all modes).
- Fan-out/fan-in path is active for `both` route with merged ranking/trim behavior.
- Existing fallback behavior is preserved in orchestration branches (seeded fallback and diagnostic system snippet when fallback is disabled).
- Core orchestration tests were added and updated:
  - `tests/test_orchestration_graph.py`
  - `tests/test_prototype_service.py`
- Full test suite is currently green after orchestration wiring.

### Partially completed

- Router improvements are only partially complete: the orchestration router is wired, but mixed-intent/tie-break logic has not been expanded beyond current routing behavior.
- Telemetry events exist in graph state (`telemetry_events`) for route selection, branch completion, fan-in, synthesis, and finalize steps, but dedicated telemetry module/log sink integration is not complete.
- Tests and validation are partially complete: orchestration path coverage exists, but targeted failure-path orchestration tests (single-branch failure with fallback on/off) are still pending.

### Not completed yet

- Dedicated telemetry module (`lattice/prototype/orchestration/telemetry.py`) and structured log emission pipeline.
- Additional orchestration-focused routing tests file (`tests/test_orchestration_routing.py`).
- Neo4j GraphRAG migration work (`HybridRetriever` / `HybridCypherRetriever`) remains evaluation/planning only.

## Why this phase now

Phase 1 proved end-to-end viability, and Phase 2 stabilized real data connectors (Supabase + Neo4j) with integration coverage. Phase 3 now upgrades control flow from a mostly linear service path to explicit agentic orchestration.

This plan aligns with:

- `Docs/development_roadmap.md` (Phase 3 goal: robust parallel orchestration)
- `Docs/agentic_rag_app_plan.md` (LangGraph fan-out/fan-in architecture)

## Phase 3 goals

1. Implement explicit orchestration state transitions using LangGraph.
2. Run retrieval branches concurrently with clear fan-out/fan-in behavior.
3. Improve routing for mixed-intent queries and deterministic fallback behavior.
4. Add structured telemetry for route decisions and retrieval outcomes.
5. Improve retrieval quality where it affects orchestration-level outcomes.

## Non-goals (kept for later phases)

- Full critic loop and confidence-driven retry loop (Phase 4).
- Major frontend redesign and onboarding changes (Phase 5).
- Breaking response schema changes for `/api/prototype/query`.

## Architectural target (Phase 3)

### Orchestration model

- Adopt a LangGraph `StateGraph` as the execution backbone.
- Use explicit orchestration state (query, route decision, retriever outputs, telemetry metadata, errors).
- Use reducer-safe state keys for fan-out branches to avoid overwrite collisions.

### Fan-out/fan-in flow

1. **Router node** classifies request as `direct`, `document`, `graph`, or `both`.
2. **Fan-out retrieval nodes** run document and graph retrieval concurrently when route is `both`.
3. **Fan-in merge node** aggregates snippets, applies ranking/trim policy, and forwards to synthesis.
4. **Synthesis node** produces grounded answer using merged snippets.
5. **Finalize node** returns stable `QueryResponse` contract.

### Error model

- Preserve current behavior: optional seeded fallback and explicit diagnostic snippets when fallback is disabled.
- Keep branch failures isolated so one retriever failure does not automatically collapse the full request.
- Record retriever error outcomes in telemetry payload.

## External integration direction (current docs)

- **LangGraph**: Use conditional edges and fan-out/fan-in patterns with typed state and reducer fields.
- **Neo4j GraphRAG**: Evaluate migration path from custom Cypher ranking to `HybridRetriever` / `HybridCypherRetriever` where practical.
- **Neo4j traversal depth**: treat depth/hops as Cypher-level behavior (not a simple retriever flag).

## Deliverables

### 1) LangGraph orchestration skeleton

- Add an orchestration module with typed state and node functions.
- Implement router, document retrieval, graph retrieval, merge/rerank, synthesis, and finalization nodes.
- Keep `PrototypeService` as the API-facing facade while delegating execution to the graph.

### 2) Router improvements

- Expand intent handling for mixed queries (document + graph cues in one question).
- Reduce ambiguous defaults by adding stronger graph/document cue logic and tie-break rules.
- Capture route reason codes for telemetry.

### 3) Parallel retrieval behavior

- Ensure `both` mode executes retrieval branches concurrently through graph fan-out.
- Add explicit fan-in merge semantics with deterministic ordering and trimming.

### 4) Telemetry and observability

- Add structured event records for:
  - route selected,
  - retriever branch duration,
  - snippet counts by source,
  - fallback usage,
  - branch errors.
- Wire telemetry to logs first; keep extension points for LangSmith/trace tools.

### 5) Retrieval quality follow-up integration

- Keep recent ranking improvements and extend where orchestration needs signal clarity.
- Prioritize improvements that reduce noisy branch outputs during fan-in.
- Defer full critic scoring mechanics to Phase 4.

### 6) Tests and validation

- Add orchestration-level tests for route paths: direct, document, graph, both.
- Add tests that verify fan-out/fan-in behavior and stable response contract.
- Add failure-path tests for one-branch-fails scenarios with fallback on/off.
- Continue running integration tests against real Supabase/Neo4j connectors.

## Proposed implementation sequence

1. **State design and graph scaffold**
   - Define orchestration state schema and node boundaries.
2. **Router node + direct path**
   - Route and short-circuit behavior parity with current service.
3. **Retriever branch nodes**
   - Document and graph branch wrappers around existing retrievers.
4. **Fan-in merge node**
   - Centralize ranking, dedupe, and threshold trimming.
5. **Synthesis/finalization nodes**
   - Preserve answer generation and `QueryResponse` output shape.
6. **Telemetry layer**
   - Add structured event emission at each state transition.
7. **Test expansion and regression pass**
   - Unit + integration validation; compare route/retrieval behavior pre/post graph introduction.

## Acceptance criteria

- `/api/prototype/query` response schema remains unchanged.
- `both` route executes document and graph retrieval in parallel via graph orchestration.
- Route and branch outcomes are observable via structured telemetry.
- Existing integration tests continue to pass in real-connector mode.
- Added orchestration tests cover success and branch-failure scenarios.

## Risks and controls

- **Risk:** Orchestration complexity introduces regressions.
  - **Control:** Keep `PrototypeService` facade stable and migrate behind feature-compatible interfaces.
- **Risk:** Parallel branches increase nondeterministic ordering.
  - **Control:** Deterministic fan-in ranking + dedupe before synthesis.
- **Risk:** Retrieval branch latency dominates response time.
  - **Control:** Add branch duration telemetry and phase-specific timeout policy.
- **Risk:** Graph retriever migration to GraphRAG changes relevance unexpectedly.
  - **Control:** Introduce behind config flags and validate with integration probes.

## Suggested file targets (implementation phase)

- `lattice/prototype/orchestration/state.py`
- `lattice/prototype/orchestration/nodes.py`
- `lattice/prototype/orchestration/graph.py`
- `lattice/prototype/orchestration/telemetry.py`
- `lattice/prototype/service.py` (facade wiring only)
- `tests/test_orchestration_graph.py`
- `tests/test_orchestration_routing.py`

## Immediate next step

Complete the remaining Phase 3 gaps in this order:

1. Add telemetry module + structured emission (logs first, LangSmith-ready hooks).
2. Add orchestration failure-path tests (branch failure with fallback on/off).
3. Add routing-behavior tests focused on mixed-intent and tie-break outcomes.
4. Re-run full unit + integration suite and update this status section.
