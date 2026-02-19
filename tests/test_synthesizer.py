import pytest

from lattice.prototype.models import SourceSnippet
from lattice.prototype.synthesizer import synthesize_answer


@pytest.mark.asyncio
async def test_synthesize_answer_fallback_includes_sources() -> None:
    snippets = [
        SourceSnippet(
            source_type="document",
            source_id="doc#1",
            text="Project Alpha launches in Q2.",
            score=0.8,
        )
    ]

    answer = await synthesize_answer(
        question="When does Project Alpha launch?",
        snippets=snippets,
        gemini_api_key=None,
    )

    assert "Sources:" in answer


@pytest.mark.asyncio
async def test_synthesize_answer_enforces_citations_for_generated_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snippets = [
        SourceSnippet(
            source_type="graph",
            source_id="ProjectAlpha->DataPlatform",
            text="Project Alpha depends on Data Platform Upgrade.",
            score=0.9,
        )
    ]

    async def _fake_generate(
        question: str,
        snippets: list[SourceSnippet],
        gemini_api_key: str,
    ) -> str | None:
        _ = question
        _ = snippets
        _ = gemini_api_key
        return "Project Alpha depends on Data Platform Upgrade."

    monkeypatch.setattr(
        "lattice.prototype.synthesizer._generate_with_gemini",
        _fake_generate,
    )

    answer = await synthesize_answer(
        question="What blocks Project Alpha?",
        snippets=snippets,
        gemini_api_key="key",
    )

    assert "Sources:" in answer
