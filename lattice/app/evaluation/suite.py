from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass(frozen=True)
class EvalCase:
    name: str
    question: str
    expected_routes: tuple[str, ...]
    min_citations: int
    expected_policies: tuple[str, ...]
    required_answer_substring: str | None = None


@dataclass(frozen=True)
class EvalResult:
    name: str
    passed: bool
    detail: str


def _load_cases() -> tuple[EvalCase, ...]:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "data" / "eval" / "golden_questions.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    cases: list[EvalCase] = []
    if not isinstance(payload, list):
        return tuple()

    for row in payload:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        question = row.get("question")
        expected_routes = row.get("expected_routes")
        min_citations = row.get("min_citations")
        expected_policies = row.get("expected_policies")
        required_answer_substring = row.get("required_answer_substring")

        if not isinstance(name, str) or not isinstance(question, str):
            continue
        if not isinstance(expected_routes, list) or not all(
            isinstance(item, str) for item in expected_routes
        ):
            continue
        if not isinstance(expected_policies, list) or not all(
            isinstance(item, str) for item in expected_policies
        ):
            continue
        if not isinstance(min_citations, int):
            continue
        if required_answer_substring is not None and not isinstance(
            required_answer_substring, str
        ):
            continue

        cases.append(
            EvalCase(
                name=name,
                question=question,
                expected_routes=tuple(expected_routes),
                min_citations=min_citations,
                expected_policies=tuple(expected_policies),
                required_answer_substring=required_answer_substring,
            )
        )
    return tuple(cases)


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
    policy = payload.get("policy")
    answer = payload.get("answer")
    citations = payload.get("citations", [])
    if route not in case.expected_routes:
        return EvalResult(
            name=case.name,
            passed=False,
            detail=f"unexpected route: {route}",
        )
    if policy not in case.expected_policies:
        return EvalResult(
            name=case.name,
            passed=False,
            detail=f"unexpected policy: {policy}",
        )
    if not isinstance(citations, list) or len(citations) < case.min_citations:
        return EvalResult(
            name=case.name,
            passed=False,
            detail="insufficient citations",
        )
    if case.required_answer_substring:
        if not isinstance(answer, str) or case.required_answer_substring not in answer:
            return EvalResult(
                name=case.name,
                passed=False,
                detail="missing expected answer substring",
            )
    return EvalResult(name=case.name, passed=True, detail="ok")


def run_offline_eval(app: FastAPI) -> dict[str, object]:
    cases = _load_cases()

    with TestClient(app) as client:
        results = [_run_case(client, case, f"eval-{case.name}") for case in cases]

        first = client.post(
            "/api/v1/query",
            json={"question": "who directed dick johnson is dead on netflix"},
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
