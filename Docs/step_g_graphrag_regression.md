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

Optional flags:

```bash
python scripts/regression/compare_graphrag_retrievers.py \
  --queries Docs/step_g_graphrag_regression_queries.json \
  --output .tmp/regression/step_g_graphrag_comparison.json
```

## Output

The script writes JSON output containing, per mode and query:

- route mode
- latency in ms
- snippet count
- snippet source IDs
- snippet scores

Use this output to compare retrieval relevance and latency across baseline and GraphRAG modes during Step G rollout.
