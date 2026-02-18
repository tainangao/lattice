import pytest

from lattice.prototype.config import AppConfig
from lattice.prototype.models import RetrievalMode
from lattice.prototype.service import PrototypeService


def _test_config() -> AppConfig:
    return AppConfig(
        gemini_api_key=None,
        supabase_url=None,
        supabase_key=None,
        neo4j_uri=None,
        neo4j_username=None,
        neo4j_password=None,
        prototype_docs_path="data/prototype/private_documents.json",
        prototype_graph_path="data/prototype/graph_edges.json",
    )


@pytest.mark.asyncio
async def test_run_query_returns_sources_for_hybrid_query() -> None:
    service = PrototypeService(_test_config())

    response = await service.run_query(
        "How does the timeline compare to graph dependencies?"
    )

    assert response.route.mode == RetrievalMode.BOTH
    assert response.snippets
    assert "Sources:" in response.answer
