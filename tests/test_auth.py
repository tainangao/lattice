from dataclasses import replace

import jwt
import pytest

from lattice.prototype.auth import AuthVerificationError, verify_supabase_bearer_token
from lattice.prototype.config import AppConfig


def _base_config() -> AppConfig:
    return AppConfig(
        gemini_api_key=None,
        supabase_url="https://example.supabase.co",
        supabase_key="anon-key",
        supabase_service_role_key=None,
        use_real_supabase=True,
        use_real_neo4j=False,
        use_neo4j_graphrag_hybrid=False,
        allow_seeded_fallback=True,
        allow_service_role_for_retrieval=False,
        neo4j_uri=None,
        neo4j_username=None,
        neo4j_password=None,
        neo4j_database="neo4j",
        neo4j_graphrag_vector_index=None,
        neo4j_graphrag_fulltext_index=None,
        neo4j_graphrag_retriever_mode="hybrid",
        neo4j_graphrag_embedder_provider="google",
        neo4j_graphrag_google_model="text-embedding-004",
        neo4j_graphrag_openai_model="text-embedding-3-small",
        neo4j_graphrag_hybrid_cypher_query=None,
        supabase_documents_table="embeddings",
        neo4j_scan_limit=200,
        phase4_enable_critic=True,
        phase4_confidence_threshold=0.62,
        phase4_min_snippets=2,
        phase4_max_refinement_rounds=1,
        phase4_initial_retrieval_limit=3,
        phase4_refinement_retrieval_limit=5,
        prototype_docs_path="data/prototype/private_documents.json",
        prototype_graph_path="data/prototype/graph_edges.json",
    )


def test_verify_supabase_bearer_token_rejects_missing_bearer_header() -> None:
    with pytest.raises(AuthVerificationError):
        verify_supabase_bearer_token(None, _base_config())


def test_verify_supabase_bearer_token_rejects_missing_supabase_url() -> None:
    config = replace(_base_config(), supabase_url=None)
    with pytest.raises(AuthVerificationError):
        verify_supabase_bearer_token("Bearer token", config)


def test_verify_supabase_bearer_token_returns_sub_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSigningKey:
        key = "fake-public-key"

    class _FakeJwkClient:
        def get_signing_key_from_jwt(self, _: str) -> _FakeSigningKey:
            return _FakeSigningKey()

    monkeypatch.setattr(
        "lattice.prototype.auth._get_jwk_client",
        lambda _: _FakeJwkClient(),
    )
    monkeypatch.setattr(
        "lattice.prototype.auth.jwt.decode",
        lambda *args, **kwargs: {
            "sub": "09f410c5-9f7e-4c1d-9d31-d6271f7b67c0",
            "aud": "authenticated",
            "iss": "https://example.supabase.co/auth/v1",
            "exp": 9999999999,
        },
    )

    result = verify_supabase_bearer_token("Bearer signed.jwt.token", _base_config())

    assert result == "09f410c5-9f7e-4c1d-9d31-d6271f7b67c0"


def test_verify_supabase_bearer_token_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeJwkClient:
        def get_signing_key_from_jwt(self, _: str) -> object:
            return object()

    monkeypatch.setattr(
        "lattice.prototype.auth._get_jwk_client",
        lambda _: _FakeJwkClient(),
    )

    def _raise_decode_error(*args, **kwargs):
        raise jwt.InvalidTokenError("invalid")

    monkeypatch.setattr("lattice.prototype.auth.jwt.decode", _raise_decode_error)

    with pytest.raises(AuthVerificationError):
        verify_supabase_bearer_token("Bearer signed.jwt.token", _base_config())
