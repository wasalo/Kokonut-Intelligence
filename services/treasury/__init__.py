"""Kokonut Treasury — SAFE smart account read + propose integration.

Chain-agnostic clients for the SAFE Transaction Service API:
- Read-side (Phases A-C, KI-12): SafeReadClient
- Propose-only write path (Phase D, KI-14): SafeProposeClient — the agent
  proposes transactions, humans sign/execute.

See ``docs/treasury.md`` for the full architecture.
"""

from services.treasury.propose import SafeProposeClient, SafeTxData
from services.treasury.safe import SafeReadClient, SafeState, SafeTransaction, SafeBalance, get_client

__all__ = [
    "SafeReadClient",
    "SafeProposeClient",
    "SafeState",
    "SafeTransaction",
    "SafeBalance",
    "SafeTxData",
    "get_client",
]