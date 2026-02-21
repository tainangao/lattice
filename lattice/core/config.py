from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_version: str
    environment: str


def load_app_config() -> AppConfig:
    return AppConfig(
        app_name=os.getenv("APP_NAME", "Lattice Agentic Graph RAG"),
        app_version=os.getenv("APP_VERSION", "0.2.0"),
        environment=os.getenv("APP_ENV", "development"),
    )
