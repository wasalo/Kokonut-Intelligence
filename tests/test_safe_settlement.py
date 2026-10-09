"""Tests for SAFE marketplace settlement (KI-14 D3).

Mocks SafeProposeClient — verifies credit transfer + fee proposals are
built and submitted correctly without touching a real chain.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from services.credit_class.safe_settlement import (
    CREDIT_TOKEN,
    SETTLEMENT_CHAIN,
    SETTLEMENT_SAFE,
    propose_farm_op,
    propose_settlement,
)

SAFE_TX_HASH = "0x" + "bb" * 32


class _FakeSafePropose:
    def __init__(self, *args, **kwargs):
        pass

    def propose(self, tx):
        tx.safe_tx_hash = SAFE_TX_HASH
        return {"safeTxHash": SAFE_TX_HASH, "nonce": "0"}


@pytest.fixture(autouse=True)
def _patch_propose(monkeypatch):
    monkeypatch.setattr(
        "services.credit_class.safe_settlement.SafeProposeClient",
        _FakeSafePropose,
    )
    monkeypatch.setenv("SAFE_DELEGATE_KEY", "0x" + "11" * 32)


def test_propose_settlement_builds_credit_transfer(monkeypatch):
    """The credit transfer call must be a transferFrom on the credit token."""
    captured = {"calls": []}

    class _ProbePropose(_FakeSafePropose):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["chain"] = kwargs.get("chain")
            captured["safe_address"] = kwargs.get("safe_address")

        def propose(self, tx):
            captured["calls"].append(
                {"to": tx.to, "data": tx.data, "value": tx.value}
            )
            return super().propose(tx)

    monkeypatch.setattr(
        "services.credit_class.safe_settlement.SafeProposeClient",
        _ProbePropose,
    )

    seller = "0x1111111111111111111111111111111111111111"
    buyer = "0x2222222222222222222222222222222222222222"
    result = propose_settlement(
        order_id="order-1",
        seller=seller,
        buyer=buyer,
        quantity=Decimal("10"),
        fee=Decimal("1"),
        fee_recipient="0x3333333333333333333333333333333333333333",
    )

    assert result["proposal_status"] == "proposed"
    assert result["safe_tx_hash"] == SAFE_TX_HASH
    # main transfer + fee transfer = 2 proposals
    assert len(captured["calls"]) == 2
    main_tx, fee_tx = captured["calls"]
    # the main transfer must target the credit token
    assert main_tx["to"].lower() == CREDIT_TOKEN.lower()
    # transferFrom selector
    assert main_tx["data"].startswith("0x23b872dd")
    # from = the settlement SAFE (holds the credits)
    assert SETTLEMENT_SAFE[2:].lower() in main_tx["data"]
    # buyer encoded in the main transfer
    assert buyer[2:].lower() in main_tx["data"]
    # value 10 * 10^18
    assert hex(int(Decimal("10") * Decimal(10**18)))[2:].zfill(64) in main_tx["data"]
    # fee transfer targets the fee recipient
    assert "0x3333333333333333333333333333333333333333"[2:].lower() in fee_tx["data"]


def test_propose_settlement_defaults_to_core_team_safe(monkeypatch):
    captured = {}

    class _ProbePropose(_FakeSafePropose):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["chain"] = kwargs.get("chain")
            captured["safe_address"] = kwargs.get("safe_address")

        def propose(self, tx):
            return super().propose(tx)

    monkeypatch.setattr(
        "services.credit_class.safe_settlement.SafeProposeClient",
        _ProbePropose,
    )

    propose_settlement(
        order_id="order-2",
        seller="0x1111111111111111111111111111111111111111",
        buyer="0x2222222222222222222222222222222222222222",
        quantity=Decimal("5"),
    )

    assert captured["chain"] == SETTLEMENT_CHAIN
    assert captured["safe_address"].lower() == SETTLEMENT_SAFE.lower()


def test_propose_farm_op_builds_proposal(monkeypatch):
    captured = {}

    class _ProbePropose(_FakeSafePropose):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["safe_address"] = kwargs.get("safe_address")

        def propose(self, tx):
            captured["to"] = tx.to
            captured["value"] = tx.value
            captured["data"] = tx.data
            return super().propose(tx)

    monkeypatch.setattr(
        "services.credit_class.safe_settlement.SafeProposeClient",
        _ProbePropose,
    )

    farm_safe = "0x4444444444444444444444444444444444444444"
    result = propose_farm_op(
        safe_id="safe-123",
        to="0x5555555555555555555555555555555555555555",
        value=1_500_000_000_000_000_000,
        data="0x",
        memo="Q3 payroll",
        safe_address=farm_safe,
        safe_chain="gnosis",
    )

    assert result["safe_id"] == "safe-123"
    assert result["memo"] == "Q3 payroll"
    assert result["safe_tx_hash"] == SAFE_TX_HASH
    assert captured["safe_address"].lower() == farm_safe.lower()
    assert captured["to"].lower() == "0x5555555555555555555555555555555555555555"
    assert captured["value"] == 1_500_000_000_000_000_000
