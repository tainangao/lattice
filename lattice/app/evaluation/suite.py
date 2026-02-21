from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass(frozen=True)
class EvalCase:
    name: str
    question: str
    expected_routes: tuple[str, ...]
    min_citations: int


@dataclass(frozen=True)
class EvalResult:
    name: str
    passed: bool
    detail: str


def _run_case(client: TestClient, case: EvalCase, session_id: str) -> EvalResult:
    response = client.post(
        "/api/v1/query",
        json={"question": case.question},
        headers={"X-Demo-Session": session_id},
    )
    if response.status_code != 200:
        return EvalResult(
            name=case.name,
            passed=False,
            detail=f"query failed with status {response.status_code}",
        )

    payload = response.json()
    route = payload.get("route")
    citations = payload.get("citations", [])
    if route not in case.expected_routes:
        return EvalResult(
            name=case.name,
            passed=False,
            detail=f"unexpected route: {route}",
        )
    if not isinstance(citations, list) or len(citations) < case.min_citations:
        return EvalResult(
            name=case.name,
            passed=False,
            detail="insufficient citations",
        )
    return EvalResult(name=case.name, passed=True, detail="ok")


def run_offline_eval(app: FastAPI) -> dict[str, object]:
    cases = (
        EvalCase(
            name="graph_dependencies",
            question="show graph dependencies for project alpha",
            expected_routes=("graph", "hybrid"),
            min_citations=1,
        ),
        EvalCase(
            name="aggregate_count",
            question="count total project dependencies",
            expected_routes=("aggregate",),
            min_citations=1,
        ),
    )

    with TestClient(app) as client:
        results = [_run_case(client, case, "eval-suite") for case in cases]

        first = client.post(
            "/api/v1/query",
            json={"question": "show graph dependencies for project alpha"},
            headers={"X-Demo-Session": "eval-memory"},
        )
        memory_result = EvalResult(
            name="memory_follow_up_resolution",
            passed=False,
            detail="initial query failed",
        )
        if first.status_code == 200:
            thread_id = first.json().get("thread_id")
            second = client.post(
                "/api/v1/query",
                json={
                    "thread_id": thread_id,
                    "question": "what about that relationship evidence?",
                },
                headers={"X-Demo-Session": "eval-memory"},
            )
            if (
                second.status_code == 200
                and "Follow-up context from prior user turn"
                in second.json().get("resolved_question", "")
            ):
                memory_result = EvalResult(
                    name="memory_follow_up_resolution",
                    passed=True,
                    detail="ok",
                )
            else:
                memory_result = EvalResult(
                    name="memory_follow_up_resolution",
                    passed=False,
                    detail="follow-up resolution check failed",
                )
        results.append(memory_result)

    passed = all(row.passed for row in results)
    return {
        "passed": passed,
        "results": [
            {"name": row.name, "passed": row.passed, "detail": row.detail}
            for row in results
        ],
    }
