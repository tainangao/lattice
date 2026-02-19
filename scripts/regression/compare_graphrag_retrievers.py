from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from lattice.prototype.config import AppConfig, load_config
from lattice.prototype.service import PrototypeService


def _build_mode_config(base: AppConfig, mode_name: str) -> AppConfig:
    if mode_name == "cypher":
        return replace(
            base,
            use_real_neo4j=True,
            use_neo4j_graphrag_hybrid=False,
        )
    if mode_name == "hybrid":
        return replace(
            base,
            use_real_neo4j=True,
            use_neo4j_graphrag_hybrid=True,
            neo4j_graphrag_retriever_mode="hybrid",
            neo4j_graphrag_embedder_provider="google",
        )
    if mode_name == "hybrid_cypher":
        return replace(
            base,
            use_real_neo4j=True,
            use_neo4j_graphrag_hybrid=True,
            neo4j_graphrag_retriever_mode="hybrid_cypher",
            neo4j_graphrag_embedder_provider="google",
        )
    raise ValueError(f"Unsupported mode: {mode_name}")


async def _run_mode(
    mode_name: str,
    base_config: AppConfig,
    queries: list[str],
) -> dict[str, object]:
    config = _build_mode_config(base_config, mode_name)
    service = PrototypeService(config)

    rows: list[dict[str, object]] = []
    for query in queries:
        start = perf_counter()
        response = await service.run_query(query)
        elapsed_ms = (perf_counter() - start) * 1000.0
        snippets = response.snippets
        rows.append(
            {
                "query": query,
                "route_mode": response.route.mode.value,
                "latency_ms": round(elapsed_ms, 2),
                "snippet_count": len(snippets),
                "snippet_sources": [snippet.source_id for snippet in snippets],
                "snippet_scores": [round(snippet.score, 4) for snippet in snippets],
            }
        )

    return {"mode": mode_name, "results": rows}


async def _main_async(query_file: Path, output_file: Path) -> None:
    queries = json.loads(query_file.read_text(encoding="utf-8"))
    if not isinstance(queries, list) or not all(
        isinstance(item, str) for item in queries
    ):
        raise ValueError("Query file must be a JSON array of strings")

    base_config = load_config()
    comparisons = []
    for mode in ["cypher", "hybrid", "hybrid_cypher"]:
        comparisons.append(await _run_mode(mode, base_config, queries))

    payload = {
        "query_file": str(query_file),
        "modes": comparisons,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Cypher vs GraphRAG retriever modes"
    )
    parser.add_argument(
        "--queries",
        default="Docs/step_g_graphrag_regression_queries.json",
        help="Path to JSON query list",
    )
    parser.add_argument(
        "--output",
        default=".tmp/regression/step_g_graphrag_comparison.json",
        help="Path for JSON comparison output",
    )
    args = parser.parse_args()

    query_file = Path(args.queries)
    output_file = Path(args.output)
    asyncio.run(_main_async(query_file, output_file))


if __name__ == "__main__":
    main()
