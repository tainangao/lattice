from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    access_mode: str
    access_token: str | None = None
