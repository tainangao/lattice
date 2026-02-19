from lattice.prototype.retrievers.document_retriever import (
    _document_overlap_score,
    _document_query_tokens,
)


def test_document_query_tokens_omits_generic_terms() -> None:
    tokens = _document_query_tokens(
        "In this document, what does integration_token_abc123 mean?"
    )

    assert "document" not in tokens
    assert "what" not in tokens
    assert "integration_token_abc123" in tokens


def test_document_overlap_score_uses_significant_tokens() -> None:
    question = "What does integration_token_abc123 mean in this file?"
    content = "The value integration_token_abc123 is used for retrieval probes."

    score = _document_overlap_score(question, content)

    assert score > 0.0
