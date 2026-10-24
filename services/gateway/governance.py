"""Bounded, read-only Gateway projections for global Baal governance state.

These endpoints use a global ``governance:read`` API-key/capability scope. DAO
state is not location-owned, so the service deliberately does not create a
farm tenant context or reuse an operator location grant.
"""

from __future__ import annotations

import re
from typing import Any

EXPECTED_GNOSIS_CHAIN_ID = 100
MAX_PROPOSAL_PAGE_SIZE = 100
_WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
class GovernanceReadUnavailable(RuntimeError):
    """Raised when the configured Baal adapter cannot provide a valid read."""


class GovernanceProposalNotFound(LookupError):
    """Raised when the requested proposal is absent from Baal state/history."""


def _client(client_factory=None):
    if client_factory is None:
        # Adapter registration and provider configuration remain lazy until an
        # authenticated governance request reaches this service.
        from services.governance.adapters import register as _register_adapters  # noqa: F401
        from services.governance.registry import get_framework

        def client_factory():
            return get_framework("moloch_v3_baal")

    try:
        client = client_factory()
        chain_id = int(client.chain_id())
    except Exception as exc:
        raise GovernanceReadUnavailable from exc
    if chain_id != EXPECTED_GNOSIS_CHAIN_ID:
        raise GovernanceReadUnavailable("Baal adapter is connected to an unexpected chain")
    return client


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def read_baal_config(*, client_factory=None) -> dict[str, Any]:
    """Return normalized Baal config without transaction or raw provider data."""
    client = _client(client_factory)
    config = client.config()
    raw = config.raw or {}
    required_raw = ("baal_version", "total_shares", "total_loot", "proposal_count")
    if any(raw.get(field) is None for field in required_raw):
        raise GovernanceReadUnavailable("Baal configuration is incomplete")
    numeric_config = {
        "voting_period": _int_or_none(config.voting_period),
        "grace_period": _int_or_none(config.grace_period),
        "proposal_offering": _int_or_none(config.proposal_offering),
        "quorum_percent": _int_or_none(config.quorum_percent),
        "sponsor_threshold": _int_or_none(config.sponsor_threshold),
        "min_retention_percent": _int_or_none(config.min_retention_percent),
    }
    raw_shares = _int_or_none(raw["total_shares"])
    raw_loot = _int_or_none(raw["total_loot"])
    proposal_count = _int_or_none(raw["proposal_count"])
    if any(value is None for value in numeric_config.values()) or any(
        value is None for value in (raw_shares, raw_loot, proposal_count)
    ):
        raise GovernanceReadUnavailable("Baal configuration is incomplete")

    return {
        "framework": {"key": client.key, "name": client.name, "chain": client.chain},
        "chain_id": EXPECTED_GNOSIS_CHAIN_ID,
        "config": {
            "baal_version": str(raw["baal_version"]),
            "total_shares": str(raw_shares),
            "total_loot": str(raw_loot),
            "proposal_count": proposal_count,
            "shares_token": raw.get("shares_token"),
            "loot_token": raw.get("loot_token"),
            "avatar": raw.get("avatar"),
            **numeric_config,
        },
    }


def _proposal_projection(proposal) -> dict[str, Any]:
    raw = proposal.raw or {}
    details = proposal.details or raw.get("description")
    title = raw.get("title") or proposal.title
    return {
        "proposal_id": str(proposal.proposal_id),
        "lifecycle": getattr(proposal.lifecycle, "value", str(proposal.lifecycle)),
        "title": str(title)[:200] if title else None,
        "details": str(details)[:4000] if details else None,
        "yes_votes": str(int(proposal.yes_votes)),
        "no_votes": str(int(proposal.no_votes)),
        "voting_starts": _int_or_none(proposal.voting_starts),
        "voting_ends": _int_or_none(proposal.voting_ends),
        "grace_ends": _int_or_none(proposal.grace_ends),
        "expiration": _int_or_none(proposal.expiration),
        "passed": proposal.passed,
        "action_failed": proposal.action_failed,
    }


def read_baal_proposals(limit: int = 50, *, client_factory=None) -> dict[str, Any]:
    """Return a bounded newest-first projection of indexed or on-chain proposals."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PROPOSAL_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_PROPOSAL_PAGE_SIZE}")
    client = _client(client_factory)
    try:
        proposals = client.proposals()
    except Exception as exc:
        raise GovernanceReadUnavailable from exc
    ordered = sorted(proposals, key=lambda item: int(item.proposal_id), reverse=True)
    return {
        "framework": client.key,
        "chain_id": EXPECTED_GNOSIS_CHAIN_ID,
        "total_count": len(ordered),
        "returned_count": min(len(ordered), limit),
        "limit": limit,
        "proposals": [_proposal_projection(item) for item in ordered[:limit]],
    }


def read_baal_proposal(proposal_id: str, *, client_factory=None) -> dict[str, Any]:
    """Return one normalized proposal while excluding event/provider internals."""
    if not proposal_id.isascii() or not proposal_id.isdecimal() or len(proposal_id) > 20:
        raise ValueError("proposal_id must be a decimal integer")
    client = _client(client_factory)
    try:
        proposal = client.proposal(proposal_id)
    except ValueError as exc:
        raise GovernanceProposalNotFound from exc
    except Exception as exc:
        raise GovernanceReadUnavailable from exc
    return {
        "framework": client.key,
        "chain_id": EXPECTED_GNOSIS_CHAIN_ID,
        "proposal": _proposal_projection(proposal),
    }


def read_baal_member(wallet: str, *, client_factory=None) -> dict[str, Any]:
    """Return the requested public on-chain member position."""
    if not _WALLET_RE.fullmatch(wallet):
        raise ValueError("wallet must be a 20-byte hexadecimal address")
    client = _client(client_factory)
    try:
        member = client.member(wallet)
    except Exception as exc:
        raise GovernanceReadUnavailable from exc
    return {
        "framework": client.key,
        "chain_id": EXPECTED_GNOSIS_CHAIN_ID,
        "member": {
            "wallet": member.wallet,
            "shares": str(int(member.shares)),
            "loot": str(int(member.loot)),
            "delegate": member.delegate,
        },
    }
