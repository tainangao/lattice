from __future__ import annotations

import pytest

from lattice.app.runtime.store import clear_runtime_state_persistence, runtime_store


@pytest.fixture(autouse=True)
def reset_runtime_store() -> None:
    clear_runtime_state_persistence()
    runtime_store.ingestion_jobs.clear()
    runtime_store.private_chunks_by_user.clear()
    runtime_store.queued_uploads.clear()
    runtime_store.conversation_turns_by_thread.clear()
    runtime_store.demo_usage_by_session.clear()
    runtime_store.runtime_keys_by_session.clear()
    runtime_store.oauth_pending_by_state.clear()
    runtime_store.oauth_completed_by_state.clear()
    runtime_store.query_embedding_cache.clear()
    runtime_store.retrieval_cache.clear()
    runtime_store.query_trace_log.clear()
