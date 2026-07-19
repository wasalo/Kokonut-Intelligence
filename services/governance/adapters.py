"""Register concrete governance framework adapters.

Importing this module wires the adapters into ``FRAMEWORK_REGISTRY``. The Baal
adapter is live; Governor/Aragon/Colony are declared as stubs that raise a clear
error until their adapters are implemented, so the registry stays honest about
what actually works.
"""

from __future__ import annotations

from .baal import BaalReadClient
from .base import GovernanceFramework
from .registry import register


class _StubFramework:
    """Placeholder for frameworks without a concrete adapter yet."""

    def __init__(self, key: str, name: str):
        self.key = key
        self.name = name
        self.chain = "unknown"

    def __getattr__(self, _item: str):
        raise NotImplementedError(
            f"Governance framework '{self.key}' ({self.name}) is not yet "
            "implemented. Only the Baal adapter is available in this release."
        )


def _stub(key: str, name: str) -> type[GovernanceFramework]:
    def factory() -> GovernanceFramework:
        return _StubFramework(key, name)  # type: ignore[return-value]

    return factory  # type: ignore[return-value]


register("moloch_v3_baal", BaalReadClient)
register("moloch_v2", _stub("moloch_v2", "Moloch v2 (legacy Kokonut DAO)"))
register("governor", _stub("governor", "OpenZeppelin Governor"))
register("aragon", _stub("aragon", "Aragon DAO"))
register("colony", _stub("colony", "Colony"))
