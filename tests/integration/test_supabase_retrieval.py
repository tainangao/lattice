from __future__ import annotations

import os
from uuid import uuid4

import pytest
from supabase import create_client

from lattice.prototype.config import load_config
from lattice.prototype.service import PrototypeService


def _supabase_integration_ready() -> bool:
    required = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"]
    return all(os.getenv(name) for name in required)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _supabase_integration_ready(),
        reason="Supabase integration env vars are not configured",
    ),
]


@pytest.mark.asyncio
async def test_real_supabase_retrieval_returns_probe_snippet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_id = f"integration-probe-{uuid4().hex[:12]}"
    probe_source = "integration_probe.md"
    probe_chunk_id = probe_id
    probe_token = f"integration_token_{uuid4().hex[:8]}"

    config = load_config()
    assert config.supabase_url is not None
    assert config.supabase_service_role_key is not None

    client = create_client(config.supabase_url, config.supabase_service_role_key)
    client.table(config.supabase_documents_table).upsert(
        [
            {
                "id": probe_id,
                "source": probe_source,
                "chunk_id": probe_chunk_id,
                "content": f"{probe_token} is a supabase integration probe token",
                "metadata": {"test": "integration"},
            }
        ],
        on_conflict="id",
    ).execute()

    monkeypatch.setenv("USE_REAL_SUPABASE", "true")
    monkeypatch.setenv("USE_REAL_NEO4J", "false")
    monkeypatch.setenv("ALLOW_SEEDED_FALLBACK", "false")
    monkeypatch.setenv("ALLOW_SERVICE_ROLE_FOR_RETRIEVAL", "true")
    monkeypatch.setenv("SUPABASE_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", config.supabase_service_role_key)

    try:
        service = PrototypeService(load_config())
        response = await service.run_query(f"In this document, what is {probe_token}?")

        assert response.route.mode.value == "document"
        assert any(probe_token in snippet.text for snippet in response.snippets)
        assert any(
            snippet.source_id == f"{probe_source}#{probe_chunk_id}"
            for snippet in response.snippets
        )
    finally:
        client.table(config.supabase_documents_table).delete().eq(
            "id", probe_id
        ).execute()
