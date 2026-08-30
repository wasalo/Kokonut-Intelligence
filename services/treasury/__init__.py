"""Kokonut Treasury — SAFE smart account read-side integration.

Chain-agnostic read client for the SAFE Transaction Service API.
Mirrors the read-first pattern of ``services/governance/``.

See ``docs/treasury.md`` for the full architecture.
"""

from services.treasury.safe import SafeReadClient, SafeState, SafeTransaction, SafeBalance, get_client

__all__ = [
    "SafeReadClient",
    "SafeState",
    "SafeTransaction",
    "SafeBalance",
    "get_client",
]