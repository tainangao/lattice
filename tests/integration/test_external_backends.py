from __future__ import annotations

import os

import pytest

from lattice.app.graph.neo4j_store import Neo4jGraphStore, Neo4jSettings
from lattice.app.retrieval.supabase_store import SupabaseVectorStore


@pytest.mark.integration
def test_supabase_match_embeddings_rpc_available() -> None:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
    supabase_test_jwt = os.getenv("SUPABASE_TEST_JWT")
    if not supabase_url or not supabase_anon_key or not supabase_test_jwt:
        pytest.skip("Missing SUPABASE_URL/SUPABASE_ANON_KEY/SUPABASE_TEST_JWT")

    store = SupabaseVectorStore(url=supabase_url, anon_key=supabase_anon_key)
    hits = store.match_chunks(
        user_jwt=supabase_test_jwt,
        query_embedding=[0.0] * 1536,
        match_count=1,
        match_threshold=-1.0,
    )
    assert isinstance(hits, list)


@pytest.mark.integration
def test_neo4j_connection_and_query() -> None:
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not uri or not username or not password:
        pytest.skip("Missing NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD")

    store = Neo4jGraphStore(
        Neo4jSettings(
            uri=uri,
            username=username,
            password=password,
            database=database,
        )
    )
    try:
        hits = store.search(query="project", limit=1)
        assert isinstance(hits, list)
    finally:
        store.close()
