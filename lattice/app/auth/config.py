from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SupabaseAuthSettings:
    supabase_url: str | None
    jwks_url: str | None
    jwt_audience: str | None
    jwt_issuer: str | None


def load_supabase_auth_settings() -> SupabaseAuthSettings:
    supabase_url = os.getenv("SUPABASE_URL")
    default_jwks_url = (
        f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        if supabase_url
        else None
    )
    return SupabaseAuthSettings(
        supabase_url=supabase_url,
        jwks_url=os.getenv("SUPABASE_JWKS_URL", default_jwks_url),
        jwt_audience=os.getenv("SUPABASE_JWT_AUDIENCE"),
        jwt_issuer=os.getenv("SUPABASE_JWT_ISSUER", supabase_url),
    )
