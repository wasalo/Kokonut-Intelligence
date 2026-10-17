"""RPC wallet rows, projections, and chain status share one transaction."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import rpc_indexer
from services.ingestion.clickhouse_outbox import OutboxEnqueueError

ADDRESS = "0x" + "a" * 40


def _wallet(wallet_id="wallet-1", chain="celo", label="Kokonut"):
    return (wallet_id, ADDRESS, chain, "treasury", label)


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
    assert connection.cursor.return_value.__enter__.return_value.execute.call_args_list[0].args[0] == "SAVEPOINT rpc_wallet_activity"
    assert connection.cursor.return_value.__enter__.return_value.execute.call_args_list[1].args[0] == "RELEASE SAVEPOINT rpc_wallet_activity"
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_rpc_partial_wallet_failure_marks_chain_error_on_same_transaction():
    connection = MagicMock()
    status_calls = []
    events = []
    connection.commit.side_effect = lambda: events.append(("commit",))
    patches = _rpc_patches(
        connection,
        [_wallet("wallet-1"), _wallet("wallet-2")],
        status_calls,
        events,
        balance_side_effect=[10**18, RuntimeError("balance unavailable")],
    )

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        rpc_indexer.run(chain="celo")

    assert status_calls == [
        (("celo", "rpc", None, "error", "balance unavailable"), {"db": connection})
    ]
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
        outbox_side_effect=OutboxEnqueueError("outbox unavailable"),
    )

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        with pytest.raises(OutboxEnqueueError, match="outbox unavailable"):
            rpc_indexer.run(chain="celo")

    assert [call[0][3] for call in status_calls] == ["healthy", "error"]
    assert all(call[1]["db"] is connection for call in status_calls)
    assert [event[0] for event in events] == ["status", "outbox", "rollback", "status", "commit"]
    connection.rollback.assert_called_once_with()
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()
