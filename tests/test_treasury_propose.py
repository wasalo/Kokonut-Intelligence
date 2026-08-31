"""Tests for the SAFE propose-only client (KI-14 D1).

Verifies EIP-712 safeTxHash computation against a REAL executed transaction
from the Core Team SAFE on Gnosis (nonce 6, safeTxHash 0x776c65...), plus
propose/delegate behavior with mocked HTTP.
"""

import pytest

from services.treasury.propose import SafeProposeClient, SafeTxData

CORE_TEAM_SAFE = "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5"

# Real transaction from the Core Team SAFE on Gnosis (fetched 2026-08-30)
# nonce 6, self-transfer, value 0 — the EIP-712 hash must reproduce exactly.
REAL_TX = {
    "to": CORE_TEAM_SAFE,
    "value": 0,
    "data": "0x",
    "operation": 0,
    "safeTxGas": 0,
    "baseGas": 0,
    "gasPrice": 0,
    "gasToken": "0x0000000000000000000000000000000000000000",
    "refundReceiver": "0x0000000000000000000000000000000000000000",
    "nonce": 6,
}
REAL_SAFE_TX_HASH = "0x776c654dc02de6408e826c6dd5775ecccdb6a6b3cff9334ada9ab3d69bfbc153"

DELEGATE_KEY = "0x" + "11" * 32  # deterministic test key


@pytest.fixture
def client() -> SafeProposeClient:
    return SafeProposeClient(
        chain="gnosis",
        safe_address=CORE_TEAM_SAFE,
        delegate_key=DELEGATE_KEY,
    )


def test_chain_validation():
    with pytest.raises(ValueError):
        SafeProposeClient(chain="not-a-chain")


def test_safe_tx_hash_matches_real_onchain_vector(client):
    """The EIP-712 hash reproduces a real executed transaction exactly.

    This is the critical test: it proves our hash computation matches what
    the Safe contract accepted on-chain for the Core Team SAFE.
    """
    tx = SafeTxData(
        to=REAL_TX["to"],
        value=REAL_TX["value"],
        data=REAL_TX["data"],
        nonce=REAL_TX["nonce"],
        safe_tx_gas=REAL_TX["safeTxGas"],
        base_gas=REAL_TX["baseGas"],
        gas_price=REAL_TX["gasPrice"],
    )
    h = client.compute_safe_tx_hash(tx)
    assert h == REAL_SAFE_TX_HASH


def test_safe_tx_hash_deterministic(client):
    tx = client.build_tx(to=CORE_TEAM_SAFE, value=1_000_000_000_000_000_000, nonce=0)
    h1 = client.compute_safe_tx_hash(tx)
    h2 = client.compute_safe_tx_hash(tx)
    assert h1 == h2
    assert h1.startswith("0x") and len(h1) == 66


def test_safe_tx_hash_differs_by_nonce(client):
    tx1 = client.build_tx(to=CORE_TEAM_SAFE, value=0, nonce=0)
    tx2 = client.build_tx(to=CORE_TEAM_SAFE, value=0, nonce=1)
    assert client.compute_safe_tx_hash(tx1) != client.compute_safe_tx_hash(tx2)


def test_propose_requires_delegate_key():
    client = SafeProposeClient(chain="gnosis", safe_address=CORE_TEAM_SAFE)
    tx = client.build_tx(to=CORE_TEAM_SAFE, value=0, nonce=0)
    with pytest.raises(PermissionError):
        client.propose(tx)


def test_propose_posts_payload(client):
    """propose() must POST the signed safeTxHash to the Transaction Service."""
    import json

    tx = client.build_tx(to=CORE_TEAM_SAFE, value=0, nonce=0)
    expected_hash = client.compute_safe_tx_hash(tx)

    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"safeTxHash": expected_hash, "nonce": "0"}

    class _FakeSession:
        def __init__(self):
            self.headers = {}

        def post(self, url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

    client._session = _FakeSession()
    result = client.propose(tx)

    assert result["safeTxHash"] == expected_hash
    assert captured["url"] == (
        "https://safe-transaction-gnosis-chain.safe.global/api/v1"
        f"/safes/{CORE_TEAM_SAFE}/multisig-transactions/"
    )
    payload = captured["json"]
    assert payload["sender"] == client.delegate_address
    assert payload["safeTxHash"] == expected_hash
    assert payload["nonce"] == "0"
    assert payload["origin"] == "kokonut-intelligence"
    # signature must be 65-byte ECDSA hex (0x + 130 chars)
    assert payload["signature"].startswith("0x")
    assert len(payload["signature"]) == 132


def test_build_tx_handles_wei_and_hex(client):
    tx = client.build_tx(to=CORE_TEAM_SAFE, value=10**18, data="0xdeadbeef", nonce=3)
    assert tx.value == 10**18
    assert tx.data == "0xdeadbeef"
    assert tx.nonce == 3
    assert tx.operation == 0
