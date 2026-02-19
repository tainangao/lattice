from __future__ import annotations

from lattice.prototype.models import SourceSnippet


async def synthesize_answer(
    question: str,
    snippets: list[SourceSnippet],
    gemini_api_key: str | None,
) -> str:
    if gemini_api_key and snippets:
        generated = await _generate_with_gemini(question, snippets, gemini_api_key)
        if generated:
            return _enforce_grounded_output(generated, snippets)
    return _fallback_answer(question, snippets)


def _fallback_answer(question: str, snippets: list[SourceSnippet]) -> str:
    if not snippets:
        return (
            "I could not find matching prototype context yet. "
            "Try asking about project timelines, dependencies, or ownership links."
        )
    context_lines = "\n".join(f"- {item.text}" for item in snippets)
    citations = ", ".join(f"{item.source_type}:{item.source_id}" for item in snippets)
    return (
        f"Question: {question}\n"
        "Prototype synthesis:\n"
        f"{context_lines}\n"
        f"Sources: {citations}"
    )


def _enforce_grounded_output(answer: str, snippets: list[SourceSnippet]) -> str:
    resolved = answer.strip()
    if not resolved:
        context_lines = "\n".join(f"- {item.text}" for item in snippets)
        citations = ", ".join(
            f"{item.source_type}:{item.source_id}" for item in snippets
        )
        return f"Prototype synthesis:\n{context_lines}\nSources: {citations}"
    if not snippets:
        return resolved
    if _has_citation_signal(resolved):
        return resolved
    citations = ", ".join(f"{item.source_type}:{item.source_id}" for item in snippets)
    return f"{resolved}\n\nSources: {citations}"


def _has_citation_signal(answer: str) -> bool:
    lowered = answer.lower()
    return "sources:" in lowered or "[" in answer


async def _generate_with_gemini(
    question: str,
    snippets: list[SourceSnippet],
    gemini_api_key: str,
) -> str | None:
    try:
        from google import genai
    except Exception:
        return None

    context = "\n".join(
        f"[{item.source_type}:{item.source_id}] {item.text}" for item in snippets
    )
    prompt = (
        "Answer using only the provided context. Keep it concise. "
        "Include source references in brackets.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}"
    )
    try:
        client = genai.Client(api_key=gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        await client.aio.aclose()
        return response.text
    except Exception:
        return None
