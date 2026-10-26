"""The isolated outbox runner uses its dedicated identity and bounded SQL."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.ingestion import clickhouse_outbox_worker as worker


def test_invalid_batch_and_worker_ids_are_rejected_before_feature_or_database(monkeypatch):
    feature = MagicMock()
    database = MagicMock()
    monkeypatch.setattr(worker, "require_feature", feature)
    monkeypatch.setattr(worker, "get_worker_db", database)

    for limit in (0, 101, True, "10"):
        with pytest.raises(ValueError, match="batch limit"):
            worker.run_once(limit=limit)
    for worker_id in ("", "../worker", "x" * 101):
        with pytest.raises(ValueError, match="worker ID"):
            worker.run_once(worker_id=worker_id)

    feature.assert_not_called()
    database.assert_not_called()


def test_disabled_feature_fails_before_opening_database(monkeypatch):
    feature = MagicMock(side_effect=RuntimeError("feature is disabled"))
    database = MagicMock()
    monkeypatch.setattr(worker, "require_feature", feature)
    monkeypatch.setattr(worker, "get_worker_db", database)
    monkeypatch.setattr(
        worker.ProviderSettings,
        "from_environment",
        MagicMock(return_value=SimpleNamespace(clickhouse=True)),
    )

    with pytest.raises(RuntimeError, match="feature is disabled"):
        worker.run_once()

    feature.assert_called_once_with("isolated_clickhouse_outbox_worker")
    database.assert_not_called()


def test_disabled_clickhouse_provider_leaves_postgres_queue_unclaimed(monkeypatch):
    monkeypatch.setattr(worker, "require_feature", MagicMock())
    monkeypatch.setattr(
        worker.ProviderSettings,
        "from_environment",
        MagicMock(return_value=SimpleNamespace(clickhouse=False)),
    )
    database = MagicMock()
    monkeypatch.setattr(worker, "get_worker_db", database)

    assert worker.run_once() == {"claimed": 0, "delivered": 0, "failed": 0}
    database.assert_not_called()


def test_claim_and_finish_use_bounded_functions_and_commit_each_lease_transition(monkeypatch):
    row_id = uuid4()
    lease_token = uuid4()
    connection = MagicMock()
    claim_context = MagicMock()
    finish_context = MagicMock()
    claim_cursor = MagicMock()
    finish_cursor = MagicMock()
    claim_context.__enter__.return_value = claim_cursor
    finish_context.__enter__.return_value = finish_cursor
    connection.cursor.side_effect = [claim_context, finish_context]
    claim_cursor.fetchall.return_value = [
        {
            "id": row_id,
            "event_key": "test-event",
            "source_table": "sensor_reading",
            "source_id": "reading-1",
            "target_table": "sensor_readings",
            "columns": ["timestamp", "sensor_id", "location_id", "value"],
            "rows": [["2026-10-25T00:00:00Z", "sensor-1", "location-1", 1]],
            "payload_hash": "a" * 64,
            "attempt_count": 1,
            "lease_token": lease_token,
        }
    ]
    finish_cursor.fetchone.return_value = (True,)
    monkeypatch.setattr(worker, "require_feature", MagicMock())
    monkeypatch.setattr(
        worker.ProviderSettings,
        "from_environment",
        MagicMock(return_value=SimpleNamespace(clickhouse=True)),
    )
    monkeypatch.setattr(worker, "get_worker_db", MagicMock(return_value=connection))

    def deliver(rows, worker_id, finish):
        assert rows[0]["id"] == row_id
        assert finish(
            rows[0], success=False, error="synthetic failure", retry_delay_seconds=120
        )
        return {"claimed": 1, "delivered": 0, "failed": 1}

    monkeypatch.setattr(worker, "deliver_claimed_batch", deliver)

    result = worker.run_once("worker-a", 7)

    assert result == {"claimed": 1, "delivered": 0, "failed": 1}
    assert claim_cursor.execute.call_args.args[0] == (
        "SELECT * FROM kokonut_security.claim_clickhouse_outbox_batch(%s, %s)"
    )
    assert claim_cursor.execute.call_args.args[1] == ("worker-a", 7)
    assert finish_cursor.execute.call_args.args[1] == (
        row_id, "worker-a", lease_token, False, "synthetic failure", 120, False
    )
    assert connection.commit.call_count == 2
    connection.close.assert_called_once_with()
