from __future__ import annotations

from functools import lru_cache

import jwt

from lattice.prototype.config import (
    AppConfig,
    extract_bearer_token,
    normalize_runtime_user_id,
)


class AuthVerificationError(ValueError):
    pass


def verify_supabase_bearer_token(
    authorization_header: str | None,
    config: AppConfig,
) -> str:
    token = extract_bearer_token(authorization_header)
    if token is None:
        raise AuthVerificationError("Missing bearer token")
    if not config.supabase_url:
        raise AuthVerificationError("Supabase URL is required for JWT verification")

    issuer = _build_supabase_issuer(config.supabase_url)
    jwks_url = f"{issuer}/.well-known/jwks.json"

    try:
        signing_key = _get_jwk_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["sub", "exp", "iss", "aud"]},
        )
    except (jwt.PyJWTError, AttributeError, TypeError) as exc:
        raise AuthVerificationError("Invalid or expired bearer token") from exc

    user_id = normalize_runtime_user_id(claims.get("sub"))
    if user_id is None:
        raise AuthVerificationError("Bearer token missing subject claim")
    return user_id


def _build_supabase_issuer(supabase_url: str) -> str:
    return f"{supabase_url.rstrip('/')}/auth/v1"


@lru_cache(maxsize=8)
def _get_jwk_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url)
