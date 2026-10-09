"""Tests for the SAFE treasury read client (KI-12).

Uses mocked HTTP responses — no live network in CI. Verifies parsing of the
SAFE Transaction Service API shapes (safe state, balances, multisig txs).
"""

from unittest.mock import patch

import pytest

from services.treasury.safe import (
    KOKONUT_BAAL,
    KOKONUT_SAFES,
    SafeReadClient,
)

CORE_TEAM = KOKONUT_SAFES["core_team"]
DAO_TREASURY = KOKONUT_SAFES["dao_treasury"]

SAFE_STATE_FIXTURE = {
    "address": DAO_TREASURY,
    "threshold": 1,
    "owners": [KOKONUT_BAAL],
    "nonce": "0",
    "version": "1.3.0",
    "modules": [KOKONUT_BAAL],
    "guard": "0x0000000000000000000000000000000000000000",
    "fallbackHandler": "0xf48f2B2d2a534e402487b3ee7C18c33Aec0Fe5e4",
}

BALANCES_FIXTURE = [
    {
        "tokenAddress": None,
        "token": None,
        "tokenSymbol": None,
        "balance": "1000000000000000000",
        "fiatBalance": "1.00",
    },
    {
        "tokenAddress": "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
        "token": "XDAI",
        "tokenSymbol": "XDAI",
        "balance": "7561863173216885008",
        "fiatBalance": None,
    },
]

TXS_FIXTURE = {
    "results": [
        {
            "safeTxHash": "0xabc123",
            "nonce": 6,
            "to": CORE_TEAM,
            "value": "0",
            "data": None,
            "proposer": "0xF7E75e58Dfa8CE8f278444523d8564992F5E5322",
            "confirmations": [{"owner": "0xF7E7..."}, {"owner": "0x535d..."}],
            "confirmationsRequired": 2,
            "executed": None,
            "submissionDate": "2026-07-26T21:39:03Z",
            "executionDate": None,
        }
    ]
}


@pytest.fixture
def client() -> SafeReadClient:
    return SafeReadClient(chain="gnosis")


def test_chain_validation():
    with pytest.raises(ValueError):
        SafeReadClient(chain="not-a-chain")


def test_safe_state_parses(client):
    with patch.object(client._session, "get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = SAFE_STATE_FIXTURE
        state = client.safe_state(DAO_TREASURY)

    assert state.address == DAO_TREASURY
    assert state.threshold == 1
    assert state.owners == [KOKONUT_BAAL]
    # the treasury SAFE is Baal-owned AND Baal is its module (DAOHaus model)
    assert state.modules == [KOKONUT_BAAL]
    assert state.nonce == 0
    assert state.version == "1.3.0"


def test_core_team_and_treasury_are_distinct():
    # the two Kokonut SAFEs must not be conflated
    assert CORE_TEAM != DAO_TREASURY
    assert CORE_TEAM.lower() == "0x03779b674cbcbfc0b801c4cac9dfac8aacbbd5c5"
    assert DAO_TREASURY.lower() == "0xeb55b75328a8dffd45bbf34b7e7efc431a179085"


def test_balances_parse(client):
    with patch.object(client._session, "get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = BALANCES_FIXTURE
        balances = client.balances(DAO_TREASURY)

    assert len(balances) == 2
    native = balances[0]
    assert native.token_address is None  # native XDAI
    assert native.balance == "1000000000000000000"


def test_multisig_transactions_parse(client):
    with patch.object(client._session, "get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = TXS_FIXTURE
        txs = client.multisig_transactions(CORE_TEAM, limit=5)

    assert len(txs) == 1
    t = txs[0]
    assert t.safe_tx_hash == "0xabc123"
    assert t.nonce == 6
    assert t.confirmations == 2
    assert t.confirmations_required == 2


def test_known_safes_match_docs():
    """The SAFEs documented in docs/treasury.md are the canonical ones."""
    assert KOKONUT_BAAL == "0x8977c56e979f0D8B76aFB5aD85549aCd2e96422d"
    assert set(KOKONUT_SAFES) == {"core_team", "dao_treasury"}
