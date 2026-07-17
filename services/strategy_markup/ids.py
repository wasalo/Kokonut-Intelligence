"""Stable identifiers used by normalized strategy projections."""

from __future__ import annotations

import re
from uuid import UUID, uuid5


STRATEGY_ID_NAMESPACE = UUID("9a2e2ce5-6fd6-5f85-9c2f-6e2e2e9c1f2a")


def stable_id(kind: str, source_id: object) -> str:
    """Return a deterministic UUID for a strategy element."""
    if not kind or not str(source_id):
        raise ValueError("stable IDs require kind and source_id")
    return str(uuid5(STRATEGY_ID_NAMESPACE, f"{kind}:{source_id}"))


def xml_id(kind: str, source_id: object) -> str:
    """Return a stable XML ID, safe for xsd:ID consumers."""
    safe_kind = re.sub(r"[^A-Za-z0-9_.-]", "-", kind)
    return f"{safe_kind}-{stable_id(kind, source_id)}"
