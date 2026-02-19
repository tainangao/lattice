# Step G GraphRAG Regression Comparison

This artifact compares graph retrieval behavior across three modes:

- `cypher`: existing `Neo4jGraphRetriever`
- `hybrid`: GraphRAG `HybridRetriever` with Google-first embedder selection
- `hybrid_cypher`: GraphRAG `HybridCypherRetriever`

## Query Set

- `Docs/step_g_graphrag_regression_queries.json`

## Runner

- `scripts/regression/compare_graphrag_retrievers.py`

## Usage

```bash
python scripts/regression/compare_graphrag_retrievers.py
```

The regression scripts auto-load local `.env` values when present.

Optional flags:

```bash
python scripts/regression/compare_graphrag_retrievers.py \
  --queries Docs/step_g_graphrag_regression_queries.json \
  --output .tmp/regression/step_g_graphrag_comparison.json
```

## Output

The script writes JSON output containing, per mode and query:

- active graph backend signal
- route mode
- latency in ms
- snippet count
- snippet source IDs
- snippet scores

Use this output to compare retrieval relevance and latency across baseline and GraphRAG modes during Step G rollout.

Backend signal values:

- `cypher`
- `graphrag_hybrid`
- `graphrag_hybrid_cypher`
- `cypher_fallback_from_hybrid`
- `cypher_fallback_from_hybrid_cypher`
