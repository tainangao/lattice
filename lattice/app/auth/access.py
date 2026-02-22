from __future__ import annotations

from lattice.app.runtime.store import RuntimeStore

DEFAULT_DEMO_QUOTA = 3


def get_demo_remaining(*, store: RuntimeStore, session_id: str) -> int:
    used = store.demo_usage_by_session.get(session_id, 0)
    return max(0, DEFAULT_DEMO_QUOTA - used)


def consume_demo_query(*, store: RuntimeStore, session_id: str) -> bool:
    remaining = get_demo_remaining(store=store, session_id=session_id)
    if remaining <= 0:
        return False
    store.demo_usage_by_session[session_id] = (
        store.demo_usage_by_session.get(session_id, 0) + 1
    )
    return True


def set_runtime_key(*, store: RuntimeStore, session_id: str, runtime_key: str) -> None:
    store.runtime_keys_by_session[session_id] = runtime_key


def clear_runtime_key(*, store: RuntimeStore, session_id: str) -> None:
    store.runtime_keys_by_session.pop(session_id, None)


def has_runtime_key(*, store: RuntimeStore, session_id: str) -> bool:
    return session_id in store.runtime_keys_by_session
