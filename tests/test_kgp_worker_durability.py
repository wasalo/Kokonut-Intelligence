from unittest.mock import MagicMock

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
