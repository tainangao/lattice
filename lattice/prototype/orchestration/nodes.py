from __future__ import annotations

from lattice.prototype.models import RetrievalMode
from lattice.prototype.router_agent import route_question

from .state import OrchestrationState


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
    document_snippets = state.get("document_snippets", [])
    graph_snippets = state.get("graph_snippets", [])
    merged = [*document_snippets, *graph_snippets]
    return {
        "snippets": merged,
        "telemetry_events": [{"event": "fan_in_completed", "count": len(merged)}],
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
