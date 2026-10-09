"""Configurable Governance Framework abstraction for Kokonut Intelligence.

This package provides a pluggable interface so Kokonut Intelligence can be
governance-framework-aware and feel native acrossDAOs. The first concrete
adapter is Moloch v3 (Baal) — the framework behind the Kokonut DAO on Gnosis
Chain. Future adapters (OpenZeppelin Governor, Aragon, Colony) follow the same
``GovernanceFramework`` contract.

The integration is **read-first**: adapters expose on-chain state (proposals,
votes, member shares/loot, governance config, shamans) but contain no
transaction/submission methods. Any write path (proposal submission, execution,
ragequit, shaman calls) is explicitly out of scope and must route through a
human-approved Agent/Governor flow per services/agents/safety.py.
"""

from __future__ import annotations

from . import adapters  # noqa: F401 - registers concrete adapters on import
from .baal import BaalReadClient
from .base import (
    GovernanceConfig,
    GovernanceFramework,
    MemberState,
    ProposalLifecycle,
    ProposalState,
    VoteChoice,
)
from .registry import FRAMEWORK_REGISTRY, get_framework, list_frameworks

__all__ = [
    "GovernanceFramework",
    "GovernanceConfig",
    "MemberState",
    "ProposalLifecycle",
    "ProposalState",
    "VoteChoice",
    "get_framework",
    "list_frameworks",
    "FRAMEWORK_REGISTRY",
    "BaalReadClient",
]
