"""RPC wallet rows, projections, and chain status share one transaction."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import rpc_indexer
from services.ingestion.clickhouse_outbox import OutboxEnqueueError

ADDRESS = "0x" + "a" * 40


def _wallet(wallet_id="wallet-1", chain="celo", label="Kokonut"):
    return (wallet_id, ADDRESS, chain, "treasury", label)


def _activity_record():
    return {
        "wallet_id": "wallet-1",
        "chain": "celo",
        "tx_hash": "balance-check-celo-wallet-1-100",
        "block_number": 100,
        "block_timestamp": "2026-10-18T12:00:00+00:00",
        "from_address": "",
        "to_address": ADDRESS,
        "value": 1.234567891,
        "token": "ETH",
        "gas_used": 0,
        "gas_price": 0,
        "status": "success",
        "activity_type": "balance_check",
    }


def test_rpc_activity_reuses_exact_row_without_requiring_unique_tx_hash_index():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (
        "existing-id", 100, "", ADDRESS.lower(), Decimal("1.23456789"),
        "ETH", Decimal("0"), Decimal("0"), "success", "balance_check",
    )

    assert rpc_indexer.insert_activity(connection, _activity_record()) is None

    statement = cursor.execute.call_args.args[0]
    assert "SELECT id, block_number" in statement
    assert "FOR UPDATE" in statement
    assert "ON CONFLICT" not in statement
    assert cursor.execute.call_count == 1


def test_rpc_activity_rejects_changed_content_for_an_existing_identity():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (
        "existing-id", 100, "", ADDRESS, Decimal("2.00000000"),
        "ETH", Decimal("0"), Decimal("0"), "success", "balance_check",
    )

    with pytest.raises(ValueError, match="identity conflicts"):
        rpc_indexer.insert_activity(connection, _activity_record())

    assert cursor.execute.call_count == 1


def test_rpc_activity_insert_uses_no_unbacked_conflict_target():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [None, ("inserted-id",)]

    assert rpc_indexer.insert_activity(connection, _activity_record()) == "inserted-id"

    insert_statement = cursor.execute.call_args_list[1].args[0]
    assert "INSERT INTO wallet_activity_event" in insert_statement
    assert "ON CONFLICT" not in insert_statement


def _rpc_patches(connection, wallets, status_calls, events, *, balance_side_effect=None,
                 outbox_side_effect=None):
    status = MagicMock(
        side_effect=lambda *args, **kwargs: (
            status_calls.append((args, kwargs)),
            events.append(("status", args, kwargs)),
        )
    )
    outbox = MagicMock(
        side_effect=lambda *args, **kwargs: events.append(("outbox", args, kwargs))
    )
    if outbox_side_effect:
        def fail_outbox(*args, **kwargs):
            events.append(("outbox", args, kwargs))
            raise outbox_side_effect

        outbox.side_effect = fail_outbox
    return (
        patch("services.ingestion.rpc_indexer.get_db", return_value=connection),
        patch("services.ingestion.rpc_indexer.get_wallets", return_value=wallets),
        patch("services.ingestion.rpc_indexer.get_web3", return_value=object()),
        patch("services.ingestion.rpc_indexer.fetch_latest_block", return_value=100),
        patch(
            "services.ingestion.rpc_indexer.fetch_balance",
            side_effect=balance_side_effect or [10**18] * len(wallets),
        ),
        patch("services.ingestion.rpc_indexer.insert_activity", return_value="row-1"),
        patch("services.ingestion.rpc_indexer.insert_activity_clickhouse", outbox),
        patch("services.ingestion.rpc_indexer.update_indexer_status", status),
    )


def test_rpc_success_commits_wallet_rows_outbox_and_status_together():
    connection = MagicMock()
    status_calls = []
    events = []
    connection.commit.side_effect = lambda: events.append(("commit",))
    patches = _rpc_patches(connection, [_wallet()], status_calls, events)

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        rpc_indexer.run(chain="celo")

    assert status_calls == [
        (("celo", "rpc", 100, "healthy"), {"db": connection})
    ]
    assert [event[0] for event in events] == ["status", "outbox", "commit"]
    statements = [
        call.args[0]
        for call in connection.cursor.return_value.__enter__.return_value.execute.call_args_list
    ]
    assert "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))" in statements
    assert "SAVEPOINT rpc_wallet_activity" in statements
    assert "RELEASE SAVEPOINT rpc_wallet_activity" in statements
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_rpc_partial_wallet_failure_marks_chain_error_on_same_transaction():
    connection = MagicMock()
    status_calls = []
    events = []
    connection.commit.side_effect = lambda: events.append(("commit",))
    secret = "wallet-rpc-secret"
    logger = MagicMock()
    patches = _rpc_patches(
        connection,
        [_wallet("wallet-1"), _wallet("wallet-2")],
        status_calls,
        events,
        balance_side_effect=[10**18, RuntimeError(f"https://rpc.example/?token={secret}")],
    )

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patch.object(rpc_indexer, "logger", logger):
        rpc_indexer.run(chain="celo")

    assert status_calls == [
        (("celo", "rpc", None, "error", "RPC wallet request failed (RuntimeError)"), {"db": connection})
    ]
    assert secret not in str(status_calls)
    assert secret not in str(logger.error.call_args)
    assert [event[0] for event in events] == ["status", "outbox", "commit"]
    savepoint_statements = [
        call.args[0]
        for call in connection.cursor.return_value.__enter__.return_value.execute.call_args_list
    ]
    assert savepoint_statements.count("ROLLBACK TO SAVEPOINT rpc_wallet_activity") == 1
    assert savepoint_statements.count("RELEASE SAVEPOINT rpc_wallet_activity") == 2
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_rpc_outbox_failure_rolls_back_data_then_persists_error_status():
    connection = MagicMock()
    status_calls = []
    events = []
    connection.rollback.side_effect = lambda: events.append(("rollback",))
    connection.commit.side_effect = lambda: events.append(("commit",))
    patches = _rpc_patches(
        connection,
        [_wallet()],
        status_calls,
        events,
        outbox_side_effect=OutboxEnqueueError("https://ch.example/?token=rpc-outbox-secret"),
    )

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        with pytest.raises(OutboxEnqueueError, match="ClickHouse outbox enqueue failed") as error:
            rpc_indexer.run(chain="celo")

    assert [call[0][3] for call in status_calls] == ["healthy", "error"]
    assert status_calls[-1][0][4] == "ClickHouse outbox enqueue failed"
    assert "rpc-outbox-secret" not in str(error.value)
    assert error.value.__suppress_context__ is True
    assert all(call[1]["db"] is connection for call in status_calls)
    assert [event[0] for event in events] == ["status", "outbox", "rollback", "status", "commit"]
    connection.rollback.assert_called_once_with()
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()
