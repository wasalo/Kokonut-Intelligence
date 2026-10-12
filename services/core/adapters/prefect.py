"""Explicit boundary for legacy Prefect workflow decorators.

Importing this adapter alone does not load Prefect. Requesting a decorator
selects the existing orchestration implementation and returns its real object,
preserving deployment discovery and retry behavior.
"""

from __future__ import annotations

from typing import Any

_DECORATORS = {"flow", "task"}


def __getattr__(name: str) -> Any:
    if name not in _DECORATORS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import prefect

    return getattr(prefect, name)
