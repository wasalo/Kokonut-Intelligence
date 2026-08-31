"""Tests for farm treasury operations (KI-14 D4).

Mocks SafeProposeClient and the safe_account DB lookup — verifies the agent
proposes ops on a farm SAFE, resolving address/chain from the provisioning
record when not given.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from services.treasury.ops import propose_farm_op

SAFE_TX_HASH = "0x" + "cc" * 32
FARM_SAFE = "0x4444444444444444444444444444444444444444"


class _FakeSafePropose:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def propose(self, tx):
        tx.safe_tx_hash = SAFE_TX_HASH
        return {"safeTxHash": SAFE_TX_HASH, "nonce": "0"}


class _FakeRow:
    def __init__(self, address, chain):
        self.address = address
        self.chain = chain


class _FakeConn:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params
        return self

    def fetchone(self):
        return self.row

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setenv("SAFE_DELEGATE_KEY", "0x" + "11" * 32)


def test_propose_farm_op_with_explicit_address(monkeypatch):
    captured = {}

    class _ProbePropose(_FakeSafePropose):
        def propose(self, tx):
            captured["to"] = tx.to
            captured["value"] = tx.value
            captured["data"] = tx.data
            return super().propose(tx)

    monkeypatch.setattr("services.treasury.ops.SafeProposeClient", _ProbePropose)

    result = propose_farm_op(
        safe_id="safe-1",
        to="0x5555555555555555555555555555555555555555",
        value=1_500_000_000_000_000_000,
        memo="Q3 payroll",
        safe_address=FARM_SAFE,
        safe_chain="gnosis",
    )

    assert result["proposal_status"] == "proposed"
    assert result["safe_tx_hash"] == SAFE_TX_HASH
    assert result["memo"] == "Q3 payroll"
    assert captured["to"].lower() == "0x5555555555555555555555555555555555555555"
    assert captured["value"] == 1_500_000_000_000_000_000


def test_propose_farm_op_resolves_from_db(monkeypatch):
    """Address/chain resolve from the safe_account record when not provided."""
    captured = {}

    class _ProbePropose(_FakeSafePropose):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["safe_address"] = kwargs.get("safe_address")
            captured["chain"] = kwargs.get("chain")

        def propose(self, tx):
            return super().propose(tx)

    monkeypatch.setattr("services.treasury.ops.SafeProposeClient", _ProbePropose)
    monkeypatch.setattr(
        "services.treasury.ops._db",
        lambda: _FakeConn(_FakeRow(FARM_SAFE, "gnosis")),
    )

    result = propose_farm_op(
        safe_id="safe-2",
        to="0x5555555555555555555555555555555555555555",
        value=0,
        memo="Inputs",
    )

    assert result["safe_address"].lower() == FARM_SAFE.lower()
    assert captured["safe_address"].lower() == FARM_SAFE.lower()
    assert captured["chain"] == "gnosis"


def test_propose_farm_op_rejects_unknown_safe(monkeypatch):
    monkeypatch.setattr(
        "services.treasury.ops._db",
        lambda: _FakeConn(None),  # no row -> not found
    )
    with pytest.raises(ValueError, match="safe_account not found"):
        propose_farm_op(
            safe_id="nope",
            to="0x5555555555555555555555555555555555555555",
            value=0,
            memo="test",
        )


def test_propose_farm_op_handles_decimal_value(monkeypatch):
    captured = {}

    class _ProbePropose(_FakeSafePropose):
        def propose(self, tx):
            captured["value"] = tx.value
            return super().propose(tx)

    monkeypatch.setattr("services.treasury.ops.SafeProposeClient", _ProbePropose)

    propose_farm_op(
        safe_id="safe-3",
        to="0x5555555555555555555555555555555555555555",
        value=Decimal("2.5"),
        memo="Q3 payroll part 2",
        safe_address=FARM_SAFE,
        safe_chain="gnosis",
    )
    assert captured["value"] == int(Decimal("2.5") * Decimal(10**18))
