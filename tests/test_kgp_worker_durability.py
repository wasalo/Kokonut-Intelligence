from unittest.mock import MagicMock, call, patch

import pytest

from services.guilds.indexer import KGPIndexer


def test_worker_failure_records_cursor_error():
    indexer = object.__new__(KGPIndexer)
    indexer.db = MagicMock()
    indexer.deployment_id = "deployment-1"

    indexer._record_scan_failure("worker-1", "rpc unavailable")

    statement = indexer.db.cursor.return_value.__enter__.return_value.execute.call_args.args[0]
    assert "retry_count = retry_count + 1" in statement
    assert "status = 'failed'" in statement


def test_release_worker_lease_is_owner_scoped():
    indexer = object.__new__(KGPIndexer)
    indexer.db = MagicMock()
    indexer.deployment_id = "deployment-1"

    indexer._release_worker_lease("worker-1")

    statement = indexer.db.cursor.return_value.__enter__.return_value.execute.call_args.args[0]
    assert "lease_owner = %s" in statement


def test_run_forever_reconnects_with_a_new_bounded_connection_after_failure():
    indexer = object.__new__(KGPIndexer)
    indexer.deployment_id = "deployment-1"
    first_connection = MagicMock()
    first_connection.rollback.side_effect = OSError("connection is closed")
    second_connection = MagicMock()
    indexer._claim_worker_lease = MagicMock(side_effect=[OSError("database unavailable"), None])
    indexer._record_scan_failure = MagicMock(side_effect=OSError("database unavailable"))
    indexer.scan_once = MagicMock(return_value=0)
    indexer._heartbeat_worker_lease = MagicMock()

    with (
        patch(
            "services.common.database.get_db",
            side_effect=[first_connection, second_connection],
        ) as connect_database,
        patch("services.guilds.indexer.time.sleep", side_effect=[None, KeyboardInterrupt]),
        patch("services.guilds.indexer.logger.exception"),
        patch("services.guilds.indexer.logger.warning"),
    ):
        with pytest.raises(KeyboardInterrupt):
            indexer.run_forever(poll_interval=0.01, worker_id="kgp-test-worker")

    assert connect_database.call_args_list == [call(connect_timeout=5), call(connect_timeout=5)]
    assert indexer._claim_worker_lease.call_count == 2
    indexer._record_scan_failure.assert_called_once_with("kgp-test-worker", "database unavailable")
    indexer.scan_once.assert_called_once_with("kgp-test-worker")
    indexer._heartbeat_worker_lease.assert_called_once_with("kgp-test-worker")
    first_connection.close.assert_called_once()
    second_connection.close.assert_called_once()


def test_run_forever_rejects_invalid_poll_interval_before_connecting():
    indexer = object.__new__(KGPIndexer)
    indexer.deployment_id = "deployment-1"

    with patch("services.common.database.get_db") as connect_database:
        with pytest.raises(ValueError, match="finite positive"):
            indexer.run_forever(poll_interval=float("nan"), worker_id="kgp-test-worker")

    connect_database.assert_not_called()
