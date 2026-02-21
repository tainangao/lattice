from __future__ import annotations

import pytest

from lattice.app.runtime.store import runtime_store


@pytest.fixture(autouse=True)
def reset_runtime_store() -> None:
    runtime_store.ingestion_jobs.clear()
    runtime_store.private_chunks_by_user.clear()
    runtime_store.conversation_turns_by_thread.clear()
    runtime_store.demo_usage_by_session.clear()
    runtime_store.runtime_keys_by_session.clear()
