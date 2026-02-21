from __future__ import annotations

import hashlib
import os


class EmbeddingProvider:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int) -> None:
        self._dimensions = dimensions

    def _hash_vector(self, text: str) -> list[float]:
        required_bytes = max(self._dimensions * 2, 64)
        digest_source = b""
        seed = text.encode("utf-8")
        while len(digest_source) < required_bytes:
            seed = hashlib.sha256(seed).digest()
            digest_source += seed
        return [value / 255.0 for value in digest_source[: self._dimensions]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._hash_vector(text)


def build_embedding_provider(dimensions: int) -> EmbeddingProvider:
    return DeterministicEmbeddingProvider(dimensions=dimensions)


class GoogleGenerativeAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
    ) -> None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=api_key,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=dimensions,
        )
        self._query_embeddings = GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=api_key,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=dimensions,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(row) for row in self._embeddings.embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(self._query_embeddings.embed_query(text))


def build_runtime_embedding_provider(
    *,
    dimensions: int,
    runtime_key: str | None,
    model: str,
    backend: str,
) -> EmbeddingProvider:
    should_use_google = backend == "google" and bool(runtime_key)
    if not should_use_google:
        return DeterministicEmbeddingProvider(dimensions=dimensions)

    try:
        return GoogleGenerativeAIEmbeddingProvider(
            api_key=runtime_key or os.getenv("GOOGLE_API_KEY", ""),
            model=model,
            dimensions=dimensions,
        )
    except Exception:
        return DeterministicEmbeddingProvider(dimensions=dimensions)
