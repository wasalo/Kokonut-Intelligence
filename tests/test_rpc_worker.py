"""Isolated RPC wallet snapshot worker contracts use mocked providers and DB."""

import hashlib
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import rpc_worker
from services.ingestion.rpc_provider import configured_rpc_endpoints

_WALLET_ID = "11111111-1111-4111-8111-111111111111"
_ADDRESS = "0x" + "a" * 40


def _connection(wallets=((_WALLET_ID, _ADDRESS, "Treasury"),)):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = wallets
    cursor.fetchone.return_value = (True,)
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


def _provider():
    web3 = MagicMock()
    web3.eth.block_number = 100
    web3.eth.get_balance.return_value = 1234567890123456789
    web3.eth.get_block.return_value = {"timestamp": 1_700_000_000}
    return web3


def _web3_class(client):
    class FakeWeb3:
        HTTPProvider = staticmethod(lambda endpoint, request_kwargs: object())

        def __new__(cls, provider):
            return client

        @staticmethod
        def to_checksum_address(address):
            return address

    return FakeWeb3


def test_snapshot_identity_and_payload_are_deterministic_for_the_same_block():
    first = rpc_worker._snapshot_record(
        wallet_id=_WALLET_ID,
        chain="celo",
        address=_ADDRESS,
        block_number=100,
        block_timestamp=1_700_000_000,
        balance_wei=1234567890123456789,
    )
    second = rpc_worker._snapshot_record(
        wallet_id=_WALLET_ID,
        chain="celo",
        address=_ADDRESS,
        block_number=100,
        block_timestamp=1_700_000_000,
        balance_wei=1234567890123456789,
    )

    assert first == second
    record, payload_hash = first
    assert record["tx_hash"].startswith("0x")
    assert len(record["tx_hash"]) == 66
    assert record["value"] == Decimal("1.23456789")
    assert payload_hash == hashlib.sha256(
        rpc_worker._snapshot_record_json(record).encode()
    ).hexdigest()


def test_balance_rounding_matches_postgres_numeric_half_up():
    record, _ = rpc_worker._snapshot_record(
        wallet_id=_WALLET_ID,
        chain="celo",
        address=_ADDRESS,
        block_number=100,
        block_timestamp=1_700_000_000,
        balance_wei=5_000_000_000,
    )

    assert record["value"] == Decimal("0.00000001")
    payload = rpc_worker._snapshot_record_json(record)
    assert '"value":0.00000001' in payload
    assert json.loads(payload, parse_float=Decimal)["value"] == Decimal("0.00000001")


def test_large_balance_keeps_all_eight_decimal_places_in_json_number():
    balance_wei = 9_000_000_000 * 10**18 + 123456780000000000
    record, _ = rpc_worker._snapshot_record(
        wallet_id=_WALLET_ID,
        chain="celo",
        address=_ADDRESS,
        block_number=100,
        block_timestamp=1_700_000_000,
        balance_wei=balance_wei,
    )

    assert record["value"] == Decimal("9000000000.12345678")
    payload = rpc_worker._snapshot_record_json(record)
    assert json.loads(payload, parse_float=Decimal)["value"] == Decimal("9000000000.12345678")


def test_isolated_worker_commits_each_snapshot_with_its_outbox_and_status():
    connection, cursor = _connection()
    web3 = _provider()
    with (
        patch.object(rpc_worker, "get_worker_db", return_value=connection),
        patch.object(rpc_worker, "configured_rpc_endpoints", return_value={"celo": "https://rpc.example"}),
        patch.object(rpc_worker, "Web3", _web3_class(web3)),
    ):
        result = rpc_worker.ingest("celo")

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert "SELECT kokonut_security.acquire_rpc_indexer_chain_lock(%s)" in statements
    assert any("list_rpc_indexer_wallets" in statement for statement in statements)
    assert any("store_rpc_indexer_snapshot" in statement for statement in statements)
    assert any("finish_rpc_indexer_chain" in statement for statement in statements)
    assert "SELECT kokonut_security.release_rpc_indexer_chain_lock(%s)" in statements
    store_call = next(
        call for call in cursor.execute.call_args_list if "store_rpc_indexer_snapshot" in call.args[0]
    )
    record = json.loads(store_call.args[1][2])
    assert record["wallet_id"] == _WALLET_ID
    assert record["block_number"] == 100
    assert record["to_address"].lower() == _ADDRESS
    assert result == {
        "status": "success",
        "chain": "celo",
        "wallets": 1,
        "snapshots_inserted": 1,
        "last_block": 100,
    }
    assert connection.commit.call_count == 5
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_isolated_worker_anchors_all_wallets_to_one_block():
    second_wallet_id = "22222222-2222-4222-8222-222222222222"
    second_address = "0x" + "c" * 40
    connection, cursor = _connection(
        ((_WALLET_ID, _ADDRESS, "Treasury"), (second_wallet_id, second_address, "Reserve"))
    )
    web3 = _provider()
    with (
        patch.object(rpc_worker, "get_worker_db", return_value=connection),
        patch.object(
            rpc_worker,
            "configured_rpc_endpoints",
            return_value={"celo": "https://rpc.example"},
        ),
        patch.object(rpc_worker, "Web3", _web3_class(web3)),
    ):
        result = rpc_worker.ingest("celo")

    web3.eth.get_block.assert_called_once_with(100)
    assert web3.eth.get_balance.call_args_list == [
        ((_ADDRESS,), {"block_identifier": 100}),
        ((second_address,), {"block_identifier": 100}),
    ]
    stored_payloads = [
        json.loads(call.args[1][2])
        for call in cursor.execute.call_args_list
        if "store_rpc_indexer_snapshot" in call.args[0]
    ]
    assert [record["block_number"] for record in stored_payloads] == [100, 100]
    assert stored_payloads[0]["block_timestamp"] == stored_payloads[1]["block_timestamp"]
    assert result["wallets"] == 2
    assert result["last_block"] == 100


def test_block_anchor_failure_stores_no_partial_wallet_snapshots():
    connection, cursor = _connection()
    web3 = _provider()
    web3.eth.get_block.side_effect = RuntimeError("provider response contained private details")
    with (
        patch.object(rpc_worker, "get_worker_db", return_value=connection),
        patch.object(
            rpc_worker,
            "configured_rpc_endpoints",
            return_value={"celo": "https://rpc.example"},
        ),
        patch.object(rpc_worker, "Web3", _web3_class(web3)),
        pytest.raises(RuntimeError, match=r"RPC indexing failed \(RuntimeError\)") as error,
    ):
        rpc_worker.ingest("celo")

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any("store_rpc_indexer_snapshot" in statement for statement in statements)
    finish_call = next(
        call for call in cursor.execute.call_args_list if "finish_rpc_indexer_chain" in call.args[0]
    )
    assert finish_call.args[1][1] == "error"
    assert finish_call.args[1][2] == "RPC worker failed (RuntimeError)"
    assert "private details" not in str(error.value)
    web3.eth.get_balance.assert_not_called()
    connection.close.assert_called_once_with()


def test_provider_failure_records_error_without_persisting_secret_details():
    connection, cursor = _connection()
    web3 = _provider()
    secret = "private-rpc-provider-token"
    web3.eth.get_balance.side_effect = RuntimeError(f"https://rpc.example/?token={secret}")
    with (
        patch.object(rpc_worker, "get_worker_db", return_value=connection),
        patch.object(rpc_worker, "configured_rpc_endpoints", return_value={"celo": "https://rpc.example"}),
        patch.object(rpc_worker, "Web3", _web3_class(web3)),
        pytest.raises(rpc_worker.RPCWorkerIncompleteError, match="RPC indexing incomplete for celo") as error,
    ):
        rpc_worker.ingest("celo")

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any("store_rpc_indexer_snapshot" in statement for statement in statements)
    finish_call = next(
        call for call in cursor.execute.call_args_list if "finish_rpc_indexer_chain" in call.args[0]
    )
    assert finish_call.args[1][1] == "error"
    assert "RPC request failed (RuntimeError)" in finish_call.args[1][2]
    assert secret not in str(finish_call)
    assert secret not in str(error.value)
    assert connection.close.call_count == 1


def test_rpc_worker_endpoint_overrides_validate_chain_and_url_shape():
    assert configured_rpc_endpoints(environ={"KOKONUT_RPC_INDEXER_RPC_ENDPOINTS": '{"celo":"https://rpc.example/path"}'})["celo"] == "https://rpc.example/path"
    with pytest.raises(ValueError, match="unsupported chain names"):
        configured_rpc_endpoints(environ={"KOKONUT_RPC_INDEXER_RPC_ENDPOINTS": '{"polygon":"https://rpc.example"}'})
    with pytest.raises(ValueError, match="without embedded credentials"):
        configured_rpc_endpoints(environ={"KOKONUT_RPC_INDEXER_RPC_ENDPOINTS": '{"celo":"https://user:pass@rpc.example"}'})


def test_worker_cli_fails_closed_when_disabled_or_not_launched_by_worker_boundary(monkeypatch):
    monkeypatch.setattr("sys.argv", ["rpc_worker", "--chain", "celo"])
    with patch.object(rpc_worker, "is_enabled", return_value=False), patch.object(rpc_worker, "get_worker_db") as connect:
        with pytest.raises(SystemExit):
            rpc_worker.main()
    connect.assert_not_called()

    with (
        patch.object(rpc_worker, "is_enabled", return_value=True),
        patch.object(rpc_worker, "isolated_worker_key", return_value=None),
        patch.object(rpc_worker, "get_worker_db") as connect,
    ):
        with pytest.raises(SystemExit):
            rpc_worker.main()
    connect.assert_not_called()
