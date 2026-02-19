from __future__ import annotations

from typing import Any

from lattice.prototype.config import AppConfig, select_supabase_retrieval_key


def build_readiness_report(config: AppConfig) -> dict[str, Any]:
    supabase = _supabase_readiness(config)
    neo4j = _neo4j_readiness(config)
    overall_ready = bool(supabase["ready"] and neo4j["ready"])
    return {
        "ready": overall_ready,
        "connectors": {
            "supabase": supabase,
            "neo4j": neo4j,
        },
        "gemini": {
            "configured": bool(config.gemini_api_key),
            "reason": (
                "env_or_runtime_key_available"
                if config.gemini_api_key
                else "missing_gemini_key_fallback_mode"
            ),
        },
        "retriever_mode": {
            "use_real_supabase": config.use_real_supabase,
            "use_real_neo4j": config.use_real_neo4j,
            "allow_seeded_fallback": config.allow_seeded_fallback,
        },
    }


def _supabase_readiness(config: AppConfig) -> dict[str, Any]:
    retrieval_key, key_source = select_supabase_retrieval_key(config)
    is_configured = bool(config.supabase_url and retrieval_key)
    return _connector_readiness(
        name="supabase",
        enabled=config.use_real_supabase,
        configured=is_configured,
        allow_seeded_fallback=config.allow_seeded_fallback,
        configured_reason=(
            f"configured_with_{key_source}"
            if key_source
            else "configured_with_retrieval_key"
        ),
        missing_reason="missing_SUPABASE_URL_or_retrieval_key",
    )


def _neo4j_readiness(config: AppConfig) -> dict[str, Any]:
    is_configured = bool(
        config.neo4j_uri and config.neo4j_username and config.neo4j_password
    )
    return _connector_readiness(
        name="neo4j",
        enabled=config.use_real_neo4j,
        configured=is_configured,
        allow_seeded_fallback=config.allow_seeded_fallback,
        configured_reason="configured_with_credentials",
        missing_reason="missing_NEO4J_URI_or_credentials",
    )


def _connector_readiness(
    name: str,
    enabled: bool,
    configured: bool,
    allow_seeded_fallback: bool,
    configured_reason: str,
    missing_reason: str,
) -> dict[str, Any]:
    if not enabled:
        return {
            "ready": True,
            "mode": "seeded_only",
            "reason": f"{name}_real_mode_disabled",
        }
    if configured:
        return {
            "ready": True,
            "mode": "real",
            "reason": configured_reason,
        }
    if allow_seeded_fallback:
        return {
            "ready": True,
            "mode": "seeded_fallback",
            "reason": missing_reason,
        }
    return {
        "ready": False,
        "mode": "misconfigured",
        "reason": missing_reason,
    }
