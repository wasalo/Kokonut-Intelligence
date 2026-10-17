"""Shared ingestion audit/status fallbacks must not log database details."""

from unittest.mock import MagicMock

import pytest

from services.ingestion import base

SECRET = "postgres://operator:password@db.invalid/kokonut"


@pytest.mark.parametrize(
    ("operation", "expected_log"),
    [
        ("log_ingestion", "Failed to log ingestion (%s)"),
        ("update_indexer_status", "Failed to update indexer status (%s)"),
    ],
)
def test_owned_connection_failure_logs_only_exception_class(
    monkeypatch, operation, expected_log
):
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.execute.side_effect = (
        RuntimeError(f"connection string included {SECRET}")
    )
    logger = MagicMock()
    monkeypatch.setattr(base, "get_db", lambda: connection)
    monkeypatch.setattr(base, "logger", logger)

    if operation == "log_ingestion":
        base.log_ingestion(
            source_system="test",
            source_table="test_source",
            source_id="source-1",
            target_table="test_target",
            target_id=None,
            operation="insert",
            payload_hash="hash",
        )
    else:
        base.update_indexer_status("test-chain", "test-indexer")

    connection.commit.assert_not_called()
    connection.close.assert_called_once_with()
    assert logger.error.call_args.args[0] == expected_log
    assert logger.error.call_args.args[1] == "RuntimeError"
    assert SECRET not in str(logger.error.call_args)
