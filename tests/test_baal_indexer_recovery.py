from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import baal_indexer


def _run_patches(
    connection,
    *,
    get_logs,
    decode=None,
    persist=None,
    protocol_lookup=None,
    last_synced_block=7,
):
    web3 = MagicMock()
    web3.eth.block_number = 10
    client = SimpleNamespace(_baal=MagicMock())
    event = MagicMock()
    event.get_logs.side_effect = get_logs if isinstance(get_logs, Exception) else None
    if not isinstance(get_logs, Exception):
        event.get_logs.return_value = get_logs
    client._baal.events = {"SubmitProposal": MagicMock(return_value=event)}
    return (
        patch.object(baal_indexer, "Web3", return_value=web3),
        patch.object(baal_indexer, "BaalReadClient", return_value=client),
        patch.object(baal_indexer, "get_db", return_value=connection),
        patch.object(baal_indexer, "get_last_synced_block", return_value=last_synced_block),
        patch.object(baal_indexer, "batch_ranges", return_value=[(1, 10)]),
        patch.object(
            baal_indexer,
            "_get_protocol_id",
            protocol_lookup or MagicMock(return_value="protocol-1"),
        ),
        patch.object(baal_indexer, "_decode_event", decode or MagicMock(return_value={"wallet_id": None})),
        patch.object(baal_indexer, "insert_governance_event", persist or MagicMock()),
    )


def test_event_query_failure_redacts_detail_and_does_not_advance_cursor():
    connection = MagicMock()
    secret = "baal-provider-secret"
    logger = MagicMock()
    status = MagicMock()
    patches = _run_patches(
        connection,
        get_logs=RuntimeError(f"https://rpc.gnosis.example/?token={secret}"),
    )

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
        patch.object(baal_indexer, "update_indexer_status", status),
        patch.object(baal_indexer, "logger", logger),
        pytest.raises(
            baal_indexer.BaalIndexingError, match=r"Baal event SubmitProposal fetch failed \(RuntimeError\)"
        ) as error,
    ):
        baal_indexer.run(from_block=1, to_block=10)

    assert secret not in str(error.value)
    assert error.value.__suppress_context__ is True
    status.assert_called_once_with(
        baal_indexer.KOKONUT_DAO_CHAIN,
        baal_indexer.INDEXER_TYPE,
        7,
        "failed",
        "Baal event SubmitProposal fetch failed (RuntimeError)",
        db=connection,
    )
    assert not any(call.args[2] == 10 for call in status.call_args_list)
    assert secret not in str(logger.error.call_args)
    connection.rollback.assert_called_once_with()
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_event_persistence_failure_redacts_detail_and_keeps_cursor_unadvanced():
    connection = MagicMock()
    secret = "baal-database-secret"
    logger = MagicMock()
    status = MagicMock()
    patches = _run_patches(
        connection,
        get_logs=[object()],
        persist=MagicMock(side_effect=RuntimeError(f"database URL {secret}")),
    )

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
        patch.object(baal_indexer, "update_indexer_status", status),
        patch.object(baal_indexer, "logger", logger),
        pytest.raises(baal_indexer.BaalIndexingError, match=r"Baal indexer failed \(RuntimeError\)") as error,
    ):
        baal_indexer.run(from_block=1, to_block=10)

    assert secret not in str(error.value)
    assert status.call_args.args[2:] == (7, "failed", "Baal indexer failed (RuntimeError)")
    assert secret not in str(status.call_args)
    assert secret not in str(logger.error.call_args)
    connection.rollback.assert_called_once_with()
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_protocol_lookup_failure_is_sanitized_and_closes_connection():
    connection = MagicMock()
    secret = "baal-db-lookup-secret"
    logger = MagicMock()
    status = MagicMock()
    patches = _run_patches(
        connection,
        get_logs=[],
        protocol_lookup=MagicMock(side_effect=RuntimeError(f"postgres URL {secret}")),
    )

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
        patch.object(baal_indexer, "update_indexer_status", status),
        patch.object(baal_indexer, "logger", logger),
        pytest.raises(baal_indexer.BaalIndexingError, match=r"Baal indexer failed \(RuntimeError\)") as error,
    ):
        baal_indexer.run(from_block=1, to_block=10)

    assert secret not in str(error.value)
    assert status.call_args.args[2:] == (7, "failed", "Baal indexer failed (RuntimeError)")
    assert secret not in str(status.call_args)
    assert secret not in str(logger.error.call_args)
    connection.rollback.assert_called_once_with()
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_latest_block_provider_failure_is_sanitized_before_database_open():
    secret = "baal-rpc-secret"
    web3 = MagicMock()
    type(web3.eth).block_number = property(lambda _self: (_ for _ in ()).throw(RuntimeError(f"rpc URL {secret}")))
    with (
        patch.object(baal_indexer, "Web3", return_value=web3),
        patch.object(baal_indexer, "BaalReadClient", return_value=SimpleNamespace(_baal=MagicMock())),
        patch.object(baal_indexer, "get_db") as get_db,
        pytest.raises(
            baal_indexer.BaalIndexingError,
            match=r"Baal provider initialization failed \(RuntimeError\)",
        ) as error,
    ):
        baal_indexer.run(from_block=1)

    assert secret not in str(error.value)
    get_db.assert_not_called()
