from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import subgraph_indexer
from services.ingestion.clickhouse_outbox import OutboxEnqueueError


def _connection():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = None
    return conn


def test_provider_failure_redacts_status_audit_and_log(monkeypatch):
    conn = _connection()
    secret = "subgraph-provider-secret"
    logger = MagicMock()
    status = MagicMock()
    audit = MagicMock()
    monkeypatch.setattr(subgraph_indexer, "get_db", lambda: conn)
    monkeypatch.setattr(
        subgraph_indexer,
        "query_subgraph",
        lambda *_args: (_ for _ in ()).throw(
            RuntimeError(f"request failed https://graph.example/?token={secret}")
        ),
    )

    with (
        patch.object(subgraph_indexer, "update_indexer_status", status),
        patch.object(subgraph_indexer, "log_ingestion", audit),
        patch.object(subgraph_indexer, "logger", logger),
    ):
        subgraph_indexer.run(protocol="eas")

    safe_error = "Subgraph indexing failed (RuntimeError)"
    status.assert_called_once_with("ethereum", "subgraph", 0, "error", safe_error)
    assert audit.call_args.kwargs["error_message"] == safe_error
    assert secret not in str(status.call_args)
    assert secret not in str(audit.call_args)
    assert secret not in str(logger.error.call_args)
    conn.commit.assert_called_once_with()
    conn.close.assert_called_once_with()


def test_outbox_failure_keeps_type_and_rollback_but_hides_detail(monkeypatch):
    conn = _connection()
    secret = "subgraph-outbox-secret"
    attestation = {
        "id": "attestation-1",
        "schema": {"id": "schema-1"},
        "blockTimestamp": "1",
        "blockNumber": "10",
    }
    monkeypatch.setattr(subgraph_indexer, "get_db", lambda: conn)
    query = MagicMock(side_effect=[{"schemaRegistrations": []}, {"attestations": [attestation]}])
    monkeypatch.setattr(
        subgraph_indexer,
        "query_subgraph",
        query,
    )
    monkeypatch.setattr(subgraph_indexer, "insert_attestation", lambda *_args: "record-1")
    monkeypatch.setattr(
        subgraph_indexer,
        "insert_clickhouse",
        lambda *_args: (_ for _ in ()).throw(
            OutboxEnqueueError(f"enqueue failed with token {secret}")
        ),
    )

    with pytest.raises(OutboxEnqueueError, match="ClickHouse outbox enqueue failed") as error:
        subgraph_indexer.run(protocol="eas")

    assert secret not in str(error.value)
    assert error.value.__suppress_context__ is True
    conn.rollback.assert_called_once_with()
    conn.commit.assert_not_called()
    conn.close.assert_called_once_with()


def test_connection_free_clickhouse_warning_redacts_provider_detail(monkeypatch):
    secret = "connection-free-secret"
    logger = MagicMock()
    monkeypatch.setattr(
        subgraph_indexer,
        "post_clickhouse_rows",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(f"token={secret}")),
    )
    monkeypatch.setattr(subgraph_indexer, "logger", logger)

    subgraph_indexer.insert_clickhouse(
        "ethereum",
        {"id": "attestation-1", "blockTimestamp": "1"},
        "published",
    )

    assert "RuntimeError" in str(logger.warning.call_args)
    assert secret not in str(logger.warning.call_args)
