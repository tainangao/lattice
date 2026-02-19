from __future__ import annotations

import logging
from time import perf_counter
from typing import Protocol

from lattice.prototype.models import RetrievalMode
from lattice.prototype.models import SourceSnippet
from lattice.prototype.retrievers.merge import rank_and_trim_snippets
from lattice.prototype.router_agent import route_question
from lattice.prototype.synthesizer import synthesize_answer

from .state import OrchestrationState

LOGGER = logging.getLogger(__name__)


class Retriever(Protocol):
    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]: ...


def router_node(state: OrchestrationState) -> OrchestrationState:
    question = state.get("question", "")
    decision = route_question(question)
    return {
        "route_mode": decision.mode,
        "route_reason": decision.reason,
        "telemetry_events": [
            {
                "event": "route_selected",
                "mode": decision.mode.value,
                "reason": decision.reason,
                "question_length": len(question),
            }
        ],
    }


def document_retrieval_node(state: OrchestrationState) -> OrchestrationState:
    _ = state
    return {
        "document_snippets": [],
        "telemetry_events": [{"event": "document_branch_completed", "count": 0}],
    }


def graph_retrieval_node(state: OrchestrationState) -> OrchestrationState:
    _ = state
    return {
        "graph_snippets": [],
        "telemetry_events": [{"event": "graph_branch_completed", "count": 0}],
    }


def merge_node(state: OrchestrationState) -> OrchestrationState:
    started = perf_counter()
    document_snippets = state.get("document_snippets", [])
    graph_snippets = state.get("graph_snippets", [])
    merged = rank_and_trim_snippets([*document_snippets, *graph_snippets])
    return {
        "snippets": merged,
        "telemetry_events": [
            {
                "event": "fan_in_completed",
                "count": len(merged),
                "document_count": len(document_snippets),
                "graph_count": len(graph_snippets),
                "duration_ms": _duration_ms(started),
            }
        ],
    }


def synthesize_node(state: OrchestrationState) -> OrchestrationState:
    if state.get("route_mode") == RetrievalMode.DIRECT:
        return {
            "answer": "Hello! Ask me about project timelines, dependencies, or document context.",
            "snippets": [],
            "telemetry_events": [{"event": "synthesis_completed", "mode": "direct"}],
        }

    snippets = state.get("snippets", [])
    if not snippets:
        answer = (
            "I could not find matching prototype context yet. "
            "Try asking about project timelines, dependencies, or ownership links."
        )
    else:
        answer = "Prototype synthesis pending LangGraph wiring."
    return {
        "answer": answer,
        "telemetry_events": [{"event": "synthesis_completed", "mode": "retrieval"}],
    }


def finalize_node(state: OrchestrationState) -> OrchestrationState:
    return {
        "telemetry_events": [
            {
                "event": "orchestration_completed",
                "mode": (
                    state.get("route_mode").value
                    if state.get("route_mode") is not None
                    else None
                ),
                "snippet_count": len(state.get("snippets", [])),
            }
        ]
    }


def make_document_retrieval_node(
    primary_retriever: Retriever | None,
    fallback_retriever: Retriever,
    allow_seeded_fallback: bool,
):
    async def _node(state: OrchestrationState) -> OrchestrationState:
        mode = state.get("route_mode")
        if mode not in {RetrievalMode.DOCUMENT, RetrievalMode.BOTH}:
            return {"document_snippets": []}

        question = state.get("question", "")
        started = perf_counter()
        snippets = await _run_retriever_with_fallback(
            question=question,
            primary_retriever=primary_retriever,
            fallback_retriever=fallback_retriever,
            allow_seeded_fallback=allow_seeded_fallback,
            retriever_name="document",
        )
        return {
            "document_snippets": snippets,
            "telemetry_events": [
                {
                    "event": "document_branch_completed",
                    "count": len(snippets),
                    "duration_ms": _duration_ms(started),
                }
            ],
        }

    return _node


def make_graph_retrieval_node(
    primary_retriever: Retriever | None,
    fallback_retriever: Retriever,
    allow_seeded_fallback: bool,
):
    async def _node(state: OrchestrationState) -> OrchestrationState:
        mode = state.get("route_mode")
        if mode not in {RetrievalMode.GRAPH, RetrievalMode.BOTH}:
            return {"graph_snippets": []}

        question = state.get("question", "")
        started = perf_counter()
        snippets = await _run_retriever_with_fallback(
            question=question,
            primary_retriever=primary_retriever,
            fallback_retriever=fallback_retriever,
            allow_seeded_fallback=allow_seeded_fallback,
            retriever_name="graph",
        )
        return {
            "graph_snippets": snippets,
            "telemetry_events": [
                {
                    "event": "graph_branch_completed",
                    "count": len(snippets),
                    "duration_ms": _duration_ms(started),
                }
            ],
        }

    return _node


def make_synthesize_node(gemini_api_key: str | None):
    async def _node(state: OrchestrationState) -> OrchestrationState:
        if state.get("route_mode") == RetrievalMode.DIRECT:
            return {
                "answer": "Hello! Ask me about project timelines, dependencies, or document context.",
                "snippets": [],
                "telemetry_events": [
                    {"event": "synthesis_completed", "mode": "direct"}
                ],
            }

        snippets = state.get("snippets", [])
        started = perf_counter()
        answer = await synthesize_answer(
            question=state.get("question", ""),
            snippets=snippets,
            gemini_api_key=gemini_api_key,
        )
        return {
            "answer": answer,
            "telemetry_events": [
                {
                    "event": "synthesis_completed",
                    "mode": "retrieval",
                    "duration_ms": _duration_ms(started),
                }
            ],
        }

    return _node


async def _run_retriever_with_fallback(
    question: str,
    primary_retriever: Retriever | None,
    fallback_retriever: Retriever,
    allow_seeded_fallback: bool,
    retriever_name: str,
) -> list[SourceSnippet]:
    if primary_retriever is None:
        return await fallback_retriever.retrieve(question)

    try:
        return await primary_retriever.retrieve(question)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "Primary retriever failed",
            extra={"retriever": retriever_name},
            exc_info=exc,
        )
        if allow_seeded_fallback:
            return await fallback_retriever.retrieve(question)
        return [_build_retriever_error_snippet(retriever_name, exc)]


def _build_retriever_error_snippet(
    retriever_name: str,
    exc: Exception,
) -> SourceSnippet:
    return SourceSnippet(
        source_type="system",
        source_id=f"retrieval_error:{retriever_name}",
        text=(
            f"Retriever '{retriever_name}' failed ({exc.__class__.__name__}). "
            "Seeded fallback is disabled."
        ),
        score=0.0,
    )


def _duration_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)
