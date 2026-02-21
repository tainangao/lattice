from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CriticDecision:
    should_refine: bool
    reason: str


class CriticModel:
    def evaluate(
        self,
        *,
        question: str,
        route: str,
        top_score: float,
        hit_count: int,
    ) -> CriticDecision:
        raise NotImplementedError


class DeterministicCriticModel(CriticModel):
    def evaluate(
        self,
        *,
        question: str,
        route: str,
        top_score: float,
        hit_count: int,
    ) -> CriticDecision:
        if route in {"graph", "document"} and (top_score < 0.35 or hit_count < 2):
            return CriticDecision(
                should_refine=True,
                reason="low evidence on single-source route",
            )
        return CriticDecision(should_refine=False, reason="evidence is sufficient")


class GeminiCriticModel(CriticModel):
    def __init__(self, *, api_key: str, model: str) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        self._model = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=1.0,
            max_retries=1,
        )

    def evaluate(
        self,
        *,
        question: str,
        route: str,
        top_score: float,
        hit_count: int,
    ) -> CriticDecision:
        prompt = (
            "You are a retrieval critic. Return strict JSON with keys "
            "should_refine(boolean) and reason(string). "
            "Refine only if confidence is likely weak and hybrid retrieval would help. "
            f"Question: {question}\n"
            f"Route: {route}\n"
            f"Top score: {top_score}\n"
            f"Hit count: {hit_count}"
        )
        response = self._model.invoke(prompt)
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            text = str(response.content)
        try:
            payload = json.loads(text)
            should_refine = bool(payload.get("should_refine", False))
            reason = str(payload.get("reason", "critic decided"))
            return CriticDecision(should_refine=should_refine, reason=reason)
        except Exception:
            return CriticDecision(should_refine=False, reason="critic parse fallback")


def build_critic_model(
    *,
    runtime_key: str | None,
    backend: str,
    model: str,
) -> CriticModel:
    resolved_key = (
        runtime_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
    if backend == "google" and resolved_key:
        try:
            return GeminiCriticModel(api_key=str(resolved_key), model=model)
        except Exception:
            return DeterministicCriticModel()
    return DeterministicCriticModel()
