"""Framework registry: resolve a configured governance framework by key.

Adapters are registered here so CLI code, indexers, and agents can stay
framework-agnostic. Today only ``moloch_v3_baal`` is fully implemented; the
other keys are stubs that raise a clear ``NotImplementedError`` until their
adapters land.
"""

from __future__ import annotations

from typing import Callable

from .base import GovernanceFramework

FRAMEWORK_REGISTRY: dict[str, Callable[[], GovernanceFramework]] = {}


def register(key: str, factory: Callable[[], GovernanceFramework]) -> None:
    FRAMEWORK_REGISTRY[key] = factory


def get_framework(key: str) -> GovernanceFramework:
    """Return an instantiated governance framework adapter.

    Raises ``KeyError`` for unknown frameworks and ``NotImplementedError`` when
    a registered framework has no concrete adapter yet.
    """
    if key not in FRAMEWORK_REGISTRY:
        raise KeyError(
            f"Unknown governance framework '{key}'. "
            f"Known: {sorted(FRAMEWORK_REGISTRY)}"
        )
    return FRAMEWORK_REGISTRY[key]()


def list_frameworks() -> list[dict[str, str]]:
    """List registered frameworks with their display names."""
    return [
        {"key": key, "name": _display_name(key)}
        for key in sorted(FRAMEWORK_REGISTRY)
    ]


def _display_name(key: str) -> str:
    return {
        "moloch_v3_baal": "Moloch v3 (Baal) — Kokonut DAO on Gnosis",
        "moloch_v2": "Moloch v2 (legacy Kokonut DAO)",
        "governor": "OpenZeppelin Governor (stub)",
        "aragon": "Aragon DAO (stub)",
        "colony": "Colony (existing integration)",
    }.get(key, key)
