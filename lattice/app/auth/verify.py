from __future__ import annotations

from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError, PyJWKClient

from lattice.app.auth.config import SupabaseAuthSettings
from lattice.app.auth.contracts import AuthContext


class AuthVerificationError(Exception):
    pass


class AuthConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class _JwksClientCacheEntry:
    url: str
    client: PyJWKClient


_jwks_cache: dict[str, _JwksClientCacheEntry] = {}


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    cached = _jwks_cache.get(jwks_url)
    if cached is not None:
        return cached.client
    client = PyJWKClient(jwks_url)
    _jwks_cache[jwks_url] = _JwksClientCacheEntry(url=jwks_url, client=client)
    return client


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthVerificationError("Missing Authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthVerificationError("Authorization header must be Bearer token")
    return parts[1].strip()


def verify_supabase_bearer_token(
    authorization: str | None,
    settings: SupabaseAuthSettings,
) -> AuthContext:
    token = _extract_bearer_token(authorization)
    if not settings.jwks_url:
        raise AuthConfigurationError(
            "Supabase auth verification is not configured (missing SUPABASE_URL or SUPABASE_JWKS_URL)"
        )

    try:
        signing_key = _get_jwks_client(settings.jwks_url).get_signing_key_from_jwt(
            token
        )
        decode_kwargs: dict[str, object] = {
            "key": signing_key.key,
            "algorithms": ["RS256"],
            "options": {"verify_aud": bool(settings.jwt_audience)},
        }
        if settings.jwt_audience:
            decode_kwargs["audience"] = settings.jwt_audience
        if settings.jwt_issuer:
            decode_kwargs["issuer"] = settings.jwt_issuer
        claims = jwt.decode(token, **decode_kwargs)
    except InvalidTokenError as exc:
        raise AuthVerificationError("Token verification failed") from exc
    except Exception as exc:
        raise AuthVerificationError(
            "Unable to verify token with Supabase JWKS"
        ) from exc

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise AuthVerificationError("Token missing subject claim")
    return AuthContext(
        user_id=user_id,
        access_mode="authenticated",
        access_token=token,
    )
