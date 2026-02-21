from __future__ import annotations

import hashlib


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
