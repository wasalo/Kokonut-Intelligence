"""Core types for the configurable Governance Framework abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ProposalLifecycle(str, Enum):
    """Normalized proposal lifecycle across frameworks."""

    SUBMITTED = "submitted"
    SPONSORED = "sponsored"
    VOTING = "voting"
    GRACE = "grace"
    READY = "ready"
    EXECUTED = "executed"
    DEFEATED = "defeated"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class VoteChoice(str, Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


@dataclass
class ProposalState:
    """Framework-agnostic proposal snapshot."""

    proposal_id: str
    lifecycle: ProposalLifecycle
    title: str | None = None
    details: str | None = None
    sponsor: str | None = None
    proposer: str | None = None
    yes_votes: int = 0
    no_votes: int = 0
    voting_starts: int | None = None
    voting_ends: int | None = None
    grace_ends: int | None = None
    expiration: int | None = None
    passed: bool | None = None
    action_failed: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemberState:
    """Framework-agnostic member governance position."""

    wallet: str
    shares: int = 0
    loot: int = 0
    delegate: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceConfig:
    """Framework-agnostic governance parameters."""

    voting_period: int | None = None
    grace_period: int | None = None
    proposal_offering: int | None = None
    quorum_percent: int | None = None
    sponsor_threshold: int | None = None
    min_retention_percent: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class GovernanceFramework(Protocol):
    """Contract every governance adapter must satisfy.

    Read-only by design. Adapters may add framework-specific query helpers,
    but must not expose transaction-submitting methods.
    """

    key: str
    name: str
    chain: str

    def proposal(self, proposal_id: str) -> ProposalState: ...

    def proposals(self) -> list[ProposalState]: ...

    def member(self, wallet: str) -> MemberState: ...

    def config(self) -> GovernanceConfig: ...
