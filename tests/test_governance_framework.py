"""Tests for the configurable Governance Framework abstraction (read-first)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from services.governance import (  # noqa: F401 - adapters import registers frameworks
    FRAMEWORK_REGISTRY,
    BaalReadClient,
    GovernanceConfig,
    MemberState,
    ProposalLifecycle,
    ProposalState,
    adapters,
    get_framework,
    list_frameworks,
)


def test_registry_contains_baal_and_stubs():
    keys = set(FRAMEWORK_REGISTRY)
    assert "moloch_v3_baal" in keys
    assert {"moloch_v2", "governor", "aragon", "colony"}.issubset(keys)


def test_get_framework_baal_returns_client():
    client = get_framework("moloch_v3_baal")
    assert isinstance(client, BaalReadClient)
    assert client.key == "moloch_v3_baal"
    assert client.chain == "gnosis"


def test_get_framework_unknown_raises():
    with pytest.raises(KeyError):
        get_framework("does_not_exist")


def test_stub_frameworks_raise_not_implemented():
    for key in ("governor", "aragon"):
        client = get_framework(key)
        with pytest.raises(NotImplementedError):
            client.proposal("1")


def test_list_frameworks_shape():
    rows = list_frameworks()
    assert any(r["key"] == "moloch_v3_baal" for r in rows)
    assert all("name" in r for r in rows)


def _fake_w3() -> MagicMock:
    w3 = MagicMock()
    w3.eth.chain_id = 100
    return w3


def _patch_client(monkeypatch, client: BaalReadClient):
    """Patch the Baal contract calls with canned data."""
    baal = MagicMock()
    baal.functions.proposals.return_value.call.return_value = (
        3, b"", "0xsponsor", 0, 0, 5, 2, 0, b"", "details text",
        1000, 2000, 2500, 3000, 1, False,
    )
    baal.functions.getProposalFlags.return_value.call.return_value = (
        True, False, False, False, True,
    )
    baal.functions.totalProposals.return_value.call.return_value = 1
    baal.functions.sharesBalance.return_value.call.return_value = 10
    baal.functions.lootBalance.return_value.call.return_value = 4
    baal.functions.delegates.return_value.call.return_value = "0xDelegate"
    baal.functions.votingPeriod.return_value.call.return_value = 86400
    baal.functions.gracePeriod.return_value.call.return_value = 43200
    baal.functions.proposalOffering.return_value.call.return_value = 0
    baal.functions.quorumPercent.return_value.call.return_value = 25
    baal.functions.sponsorThreshold.return_value.call.return_value = 1
    baal.functions.minRetentionPercent.return_value.call.return_value = 66
    baal.functions.baalVersion.return_value.call.return_value = "3.0.0"
    baal.functions.totalShares.return_value.call.return_value = 687 * 10 ** 18
    baal.functions.totalLoot.return_value.call.return_value = 8 * 10 ** 18
    baal.functions.proposalCount.return_value.call.return_value = 16
    baal.functions.sharesToken.return_value.call.return_value = "0xc6b075ac3234a7ac729114b27370b552fa284690"
    baal.functions.lootToken.return_value.call.return_value = "0x2508a11aee11ad545bae87cd42131c04613b2099"
    baal.functions.avatar.return_value.call.return_value = "0xeb55b75328a8dffd45bbf34b7e7efc431a179085"
    baal.functions.shamans.return_value.call.return_value = 7
    client._baal = baal
    return client


def test_baal_read_client_proposal_and_member(monkeypatch):
    w3 = _fake_w3()
    client = BaalReadClient(w3=w3)
    _patch_client(monkeypatch, client)

    proposal = client.proposal("3")
    assert isinstance(proposal, ProposalState)
    assert proposal.proposal_id == "3"
    assert proposal.lifecycle == ProposalLifecycle.VOTING
    assert proposal.yes_votes == 5
    assert proposal.no_votes == 2
    assert proposal.passed is True

    member = client.member("0x0000000000000000000000000000000000000ABC")
    assert isinstance(member, MemberState)
    assert member.shares == 10
    assert member.loot == 4

    cfg = client.config()
    assert isinstance(cfg, GovernanceConfig)
    assert cfg.voting_period == 86400
    assert cfg.quorum_percent == 25
    assert cfg.min_retention_percent == 66
    assert cfg.raw["total_shares"] == 687 * 10 ** 18
    assert cfg.raw["shares_token"] == "0xc6b075ac3234a7ac729114b27370b552fa284690"
    assert cfg.raw["avatar"] == "0xeb55b75328a8dffd45bbf34b7e7efc431a179085"

    assert client.shaman_permission("0x0000000000000000000000000000000000000ABC") == 7


def test_baal_normalizes_token_balance():
    w3 = _fake_w3()
    client = BaalReadClient(w3=w3)
    token = MagicMock()
    token.functions.balanceOf.return_value.call.return_value = 50 * 10 ** 18
    token.functions.decimals.return_value.call.return_value = 18
    client._token = lambda token_key: token  # type: ignore
    res = client._normalize_token_balance("shares", "0x0000000000000000000000000000000000000ABC")
    assert res["balance"] == str(Decimal(50))
    assert res["decimals"] == 18


@pytest.mark.skipif(
    not __import__("os").environ.get("RUN_LIVE_BAAL_TEST"),
    reason="set RUN_LIVE_BAAL_TEST=1 and GNOSIS_RPC_URL to hit Gnosis Chain",
)
def test_baal_live_config_and_member():
    """Optional live smoke test against the real Kokonut DAO deployment."""
    from services.ingestion.config import (
        GNOSIS_RPC_URL,
        KOKONUT_BAAL_ADDRESSES,
    )

    client = get_framework("moloch_v3_baal")
    cfg = client.config()
    assert cfg.raw["shares_token"].lower() == KOKONUT_BAAL_ADDRESSES["shares"].lower()
    assert cfg.raw["loot_token"].lower() == KOKONUT_BAAL_ADDRESSES["loot"].lower()
    assert int(cfg.raw["total_shares"]) > 0
    # proposalCount is exposed by this deployment
    assert int(cfg.raw.get("proposal_count") or 0) >= 1
    # treasury avatar resolves to the documented Gnosis Safe
    assert cfg.raw["avatar"].lower() == KOKONUT_BAAL_ADDRESSES["treasury"].lower()
    _ = GNOSIS_RPC_URL  # ensure configured


def _fake_event_rows():
    """Sample governance_event rows (event_type, proposal_id, proposal_title,
    vote_choice, tx_hash, block_number, block_timestamp, metadata)."""
    return [
        (
            "proposal_created", "15",
            "Grant Request: Finalizing Kokonut Adelphi Infrastructure", None,
            "0xtxcreate15", 41112294, "2025-07-01 00:00:00+00",
            {"title": "Grant Request: Finalizing Kokonut Adelphi Infrastructure",
             "description": "Install irrigation", "content_uri": "https://x/15",
             "proposal_type": "TRANSFER_ERC20", "voting_period": "432000",
             "self_sponsor": "True"},
        ),
        (
            "vote_cast", "15", None, "yes", "0xtxvote15a", 41112484,
            "2025-07-01 01:00:00+00", {"balance": "1000000000000000000"},
        ),
        (
            "vote_cast", "15", None, "yes", "0xtxvote15b", 41112485,
            "2025-07-01 01:01:00+00", {"balance": "1000000000000000000"},
        ),
        (
            "proposal_processed", "15", None, None, "0xtxproc15", 41251986,
            "2025-07-10 00:00:00+00", {"passed": "True", "action_failed": "False"},
        ),
        (
            "proposal_created", "16",
            "Artizen Support Boost & Onboarding Campaign", None,
            "0xtxcreate16", 46908176, "2026-01-01 00:00:00+00",
            {"title": "Artizen Support Boost & Onboarding Campaign",
             "proposal_type": "TRANSFER_ERC20"},
        ),
        (
            "proposal_processed", "16", None, None, "0xtxproc16", 47049611,
            "2026-01-10 00:00:00+00", {"passed": "True", "action_failed": "False"},
        ),
    ]


def _fake_db_with_events():
    """Build a MagicMock DB whose cursor().fetchall() returns the sample rows."""
    db = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = _fake_event_rows()
    cur.__enter__.return_value = cur
    cur.__exit__.return_value = False
    db.cursor.return_value = cur
    db.cursor().__enter__.return_value = cur
    return db


def test_baal_proposals_from_events():
    w3 = _fake_w3()
    client = BaalReadClient(w3=w3)
    db = _fake_db_with_events()
    proposals = client.proposals_from_events(conn=db)
    assert len(proposals) == 2

    by_id = {p.proposal_id: p for p in proposals}
    p15 = by_id["15"]
    assert p15.lifecycle == ProposalLifecycle.EXECUTED
    assert p15.passed is True
    assert p15.yes_votes == 2
    assert p15.no_votes == 0
    assert p15.details.startswith("Grant Request")
    assert p15.raw.get("description") == "Install irrigation"
    assert p15.raw.get("content_uri") == "https://x/15"

    p16 = by_id["16"]
    assert p16.lifecycle == ProposalLifecycle.EXECUTED
    assert p16.passed is True


def test_baal_proposals_prefers_events(monkeypatch):
    """When on-chain decode is unreliable, proposals() uses the event ledger."""
    w3 = _fake_w3()
    client = BaalReadClient(w3=w3)
    _patch_client(monkeypatch, client)
    # Simulate unreliable on-chain decode: proposals(0) returns garbage zeros.
    garbage = (0, b"", "0x0", 0, 0, 0, 0, 0, b"", "", 0, 0, 0, 0, 0, False)
    client._baal.functions.proposals.return_value.call.return_value = garbage
    client._baal.functions.getProposalFlags.return_value.call.return_value = (
        False, False, False, False, False,
    )
    db = _fake_db_with_events()
    proposals = client.proposals_from_events(conn=db)
    # proposals() should prefer the event ledger over the garbage on-chain data
    result = client.proposals()
    assert [p.proposal_id for p in result] == ["15", "16"]
    _ = proposals
