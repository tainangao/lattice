from __future__ import annotations

from types import SimpleNamespace

from lattice.prototype.retrievers.graph_retriever import build_graphrag_embedder


def test_build_graphrag_embedder_uses_google_provider_first(
    monkeypatch,
) -> None:
    class _GoogleEmbedder:
        def __init__(self, model: str, api_key: str) -> None:
            self.model = model
            self.api_key = api_key

    fake_module = SimpleNamespace(GoogleGenAIEmbeddings=_GoogleEmbedder)
    monkeypatch.setattr(
        "lattice.prototype.retrievers.graph_retriever.importlib.import_module",
        lambda _: fake_module,
    )

    embedder = build_graphrag_embedder(
        provider="google",
        gemini_api_key="gemini-key",
        google_model="text-embedding-004",
        openai_model="text-embedding-3-small",
    )

    assert isinstance(embedder, _GoogleEmbedder)
    assert embedder.api_key == "gemini-key"


def test_build_graphrag_embedder_can_fallback_to_openai(
    monkeypatch,
) -> None:
    class _OpenAIEmbedder:
        def __init__(self, model: str, api_key: str) -> None:
            self.model = model
            self.api_key = api_key

    fake_module = SimpleNamespace(OpenAIEmbeddings=_OpenAIEmbedder)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(
        "lattice.prototype.retrievers.graph_retriever.importlib.import_module",
        lambda _: fake_module,
    )

    embedder = build_graphrag_embedder(
        provider="google",
        gemini_api_key="gemini-key",
        google_model="text-embedding-004",
        openai_model="text-embedding-3-small",
    )

    assert isinstance(embedder, _OpenAIEmbedder)
    assert embedder.api_key == "openai-key"


def test_build_graphrag_embedder_returns_none_when_dependencies_missing(
    monkeypatch,
) -> None:
    def _raise_import_error(module_name: str) -> None:
        raise ImportError(module_name)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "lattice.prototype.retrievers.graph_retriever.importlib.import_module",
        _raise_import_error,
    )

    embedder = build_graphrag_embedder(
        provider="google",
        gemini_api_key="gemini-key",
        google_model="text-embedding-004",
        openai_model="text-embedding-3-small",
    )

    assert embedder is None
