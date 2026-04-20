from __future__ import annotations

import os
from typing import Any


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


_HAS_KEYS = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
_FORCE_DISABLE = _env_true("LANGFUSE_FORCE_DISABLE")
_ENABLE_LANGFUSE = _HAS_KEYS and not _FORCE_DISABLE


def observe(*args: Any, **kwargs: Any):
    def decorator(func):
        return func

    return decorator


class _DummyContext:
    def update_current_trace(self, **kwargs: Any) -> None:
        return None

    def update_current_observation(self, **kwargs: Any) -> None:
        return None

    def get_current_trace_id(self) -> str | None:
        return None

    def get_current_observation_id(self) -> str | None:
        return None

    def score_current_trace(self, **kwargs: Any) -> None:
        return None

    def flush(self) -> None:
        return None


langfuse_context: Any = _DummyContext()


if _ENABLE_LANGFUSE:
    try:
        from langfuse import get_client as _get_client
        from langfuse import observe as _observe

        class _LangfuseContextAdapter:
            def __init__(self) -> None:
                self._client = _get_client()

            def update_current_trace(self, **kwargs: Any) -> None:
                self._client.update_current_trace(**kwargs)

            def update_current_observation(self, **kwargs: Any) -> None:
                if hasattr(self._client, "update_current_generation"):
                    self._client.update_current_generation(**kwargs)
                    return
                if hasattr(self._client, "update_current_span"):
                    self._client.update_current_span(**kwargs)

            def get_current_trace_id(self) -> str | None:
                return self._client.get_current_trace_id()

            def get_current_observation_id(self) -> str | None:
                return self._client.get_current_observation_id()

            def score_current_trace(self, **kwargs: Any) -> None:
                self._client.score_current_trace(**kwargs)

            def flush(self) -> None:
                self._client.flush()

        observe = _observe
        langfuse_context = _LangfuseContextAdapter()
    except Exception:
        # Keep the safe dummy fallback if Langfuse import fails.
        pass


def tracing_enabled() -> bool:
    return _ENABLE_LANGFUSE


def get_trace_id() -> str | None:
    try:
        return langfuse_context.get_current_trace_id()
    except Exception:
        return None
