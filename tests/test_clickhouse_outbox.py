import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.core.providers import ProviderSettings
from services.ingestion import clickhouse_outbox
from services.ingestion.clickhouse_outbox import OutboxEnqueueError, deliver_batch, enqueue


def _row(row_id: str, attempt_count: int = 1) -> dict:
    return {
        "id": row_id,
        "attempt_count": attempt_count,
        "lease_token": f"lease-{row_id}",
        "event_key": f"event:{row_id}",
        "target_table": "sensor_readings",
        "columns": ["sensor_id", "value"],
        "rows": [["sensor-1", 24.5]],
    }


@pytest.mark.parametrize(
    ("attempt_count", "expected_seconds"),
    [(1, 60), (2, 120), (3, 240), (6, 1920), (7, 3600), (8, 3600), (0, 60)],
)
def test_retry_delay_grows_exponentially_and_caps(attempt_count, expected_seconds):
    assert clickhouse_outbox._retry_delay_seconds(attempt_count) == expected_seconds


@pytest.mark.parametrize("attempt_count", [True, 1.5, "2"])
def test_retry_delay_rejects_non_integer_attempt_count(attempt_count):
    with pytest.raises(ValueError, match="integer"):
        clickhouse_outbox._retry_delay_seconds(attempt_count)


def test_finish_uses_the_computed_delay_and_commits_outcome():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.rowcount = 1

    assert clickhouse_outbox._finish(
        conn,
        "outbox-id",
        "worker-1",
        "lease-token",
        success=False,
        error="offline",
        retry_delay_seconds=480,
    )

    statement, params = cursor.execute.call_args.args
    assert "(%s * INTERVAL '1 second')" in statement
    assert "INTERVAL '1 minute'" not in statement
    assert params[3] == 480
    conn.commit.assert_called_once()


def _enable_clickhouse(monkeypatch, enabled: bool = True) -> None:
    monkeypatch.setattr(
        ProviderSettings,
        "from_environment",
        classmethod(lambda _cls: SimpleNamespace(clickhouse=enabled)),
    )


def test_enqueue_is_idempotent_and_stays_in_caller_transaction():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ("outbox-id",)

    result = enqueue(
        conn,
        event_key="event:1",
        source_table="sensor_reading",
        source_id="reading-1",
        target_table="sensor_readings",
        columns=["id", "value"],
        rows=[["reading-1", 12.5]],
        payload_hash="a" * 64,
    )

    assert result == "outbox-id"
    conn.commit.assert_not_called()
    statement = conn.cursor.return_value.__enter__.return_value.execute.call_args.args[0]
    assert "ON CONFLICT (event_key)" in statement


@pytest.mark.parametrize("failure", ["database", "conflicting_projection"])
def test_enqueue_failure_has_a_distinct_transactional_error(failure):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    if failure == "database":
        cursor.execute.side_effect = RuntimeError("database unavailable")
    else:
        cursor.fetchone.return_value = None

    with pytest.raises(OutboxEnqueueError):
        enqueue(
            conn,
            event_key="event:1",
            source_table="sensor_reading",
            source_id="reading-1",
            target_table="sensor_readings",
            columns=["id", "value"],
            rows=[["reading-1", 12.5]],
            payload_hash="a" * 64,
        )

    conn.commit.assert_not_called()


@patch("services.ingestion.clickhouse_outbox.get_clickhouse")
def test_unavailable_clickhouse_does_not_claim_success(mock_client):
    mock_client.return_value = None
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.description = []
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []

    from services.ingestion.clickhouse_outbox import deliver_batch

    assert deliver_batch(conn, "worker-1") == {"claimed": 0, "delivered": 0, "failed": 0}


def test_disabled_clickhouse_does_not_claim_or_open_client(monkeypatch):
    _enable_clickhouse(monkeypatch, enabled=False)
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: pytest.fail("must not claim"))
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: pytest.fail("must not connect"))

    assert deliver_batch(object(), "worker-disabled") == {
        "claimed": 0,
        "delivered": 0,
        "failed": 0,
    }


def test_client_setup_failure_records_a_failed_outcome_for_each_claim(monkeypatch):
    _enable_clickhouse(monkeypatch)
    rows = [_row("one"), _row("two", attempt_count=3)]
    finished = []
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: rows)
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(
        clickhouse_outbox,
        "_finish",
        lambda _conn, row_id, worker, token, *, success, error, retry_delay_seconds: finished.append(
            (row_id, worker, token, success, error, retry_delay_seconds)
        ) or True,
    )

    result = deliver_batch(object(), "worker-setup")

    assert result == {"claimed": 2, "delivered": 0, "failed": 2}
    assert finished == [
        ("one", "worker-setup", "lease-one", False, "client setup failed: OSError", 60),
        ("two", "worker-setup", "lease-two", False, "client setup failed: OSError", 240),
    ]


def test_missing_client_after_enabled_provider_records_setup_failure(monkeypatch):
    _enable_clickhouse(monkeypatch)
    row = _row("one")
    finished = []
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: [row])
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: None)
    monkeypatch.setattr(
        clickhouse_outbox,
        "_finish",
        lambda _conn, row_id, _worker, _token, *, success, error, retry_delay_seconds: finished.append(
            (row_id, success, error, retry_delay_seconds)
        ) or True,
    )

    result = deliver_batch(object(), "worker-no-client")

    assert result == {"claimed": 1, "delivered": 0, "failed": 1}
    assert finished == [("one", False, "client setup failed: RuntimeError", 60)]


def test_setup_outcome_database_failure_propagates_without_retrying_finish(monkeypatch):
    _enable_clickhouse(monkeypatch)
    rows = [_row("one"), _row("two")]
    finishes = []
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: rows)
    monkeypatch.setattr(
        clickhouse_outbox,
        "get_clickhouse",
        lambda: (_ for _ in ()).throw(OSError("offline")),
    )

    def fail_finish(_conn, row_id, *_args, **_kwargs):
        finishes.append(row_id)
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(clickhouse_outbox, "_finish", fail_finish)

    with pytest.raises(RuntimeError, match="database unavailable"):
        deliver_batch(object(), "worker-setup")

    assert finishes == ["one"]


def test_partial_batch_keeps_independent_insert_and_outcome_results(monkeypatch):
    _enable_clickhouse(monkeypatch)
    rows = [_row("success"), _row("failure")]
    client = MagicMock()
    client.raw_insert.side_effect = [None, ConnectionError("connection lost")]
    finished = []
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: rows)
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)
    monkeypatch.setattr(
        clickhouse_outbox,
        "_finish",
        lambda _conn, row_id, _worker, _token, *, success, error, retry_delay_seconds: finished.append(
            (row_id, success, error, retry_delay_seconds)
        ) or True,
    )

    result = deliver_batch(object(), "worker-partial")

    assert result == {"claimed": 2, "delivered": 1, "failed": 1}
    assert [outcome[:2] for outcome in finished] == [("success", True), ("failure", False)]
    assert finished[1][2] == "connection lost"
    assert finished[1][3] == 60
    assert client.raw_insert.call_count == 2
    client.close.assert_called_once()


def test_completion_database_error_propagates_after_insert_without_second_finish(monkeypatch):
    _enable_clickhouse(monkeypatch)
    client = MagicMock()
    finishes = []
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: [_row("one")])
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)

    def fail_finish(_conn, row_id, *_args, **_kwargs):
        finishes.append(row_id)
        raise RuntimeError("completion database failed")

    monkeypatch.setattr(clickhouse_outbox, "_finish", fail_finish)

    with pytest.raises(RuntimeError, match="completion database failed"):
        deliver_batch(object(), "worker-completion")

    assert client.raw_insert.call_count == 1
    assert finishes == ["one"]
    client.close.assert_called_once()


def test_successful_insert_with_lost_fence_counts_as_failed(monkeypatch):
    _enable_clickhouse(monkeypatch)
    client = MagicMock()
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: [_row("one")])
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)
    finish = MagicMock(return_value=False)
    monkeypatch.setattr(clickhouse_outbox, "_finish", finish)

    result = deliver_batch(object(), "stale-worker")

    assert result == {"claimed": 1, "delivered": 0, "failed": 1}
    assert finish.call_args.kwargs["success"] is True
    client.close.assert_called_once()


def test_client_close_failure_propagates_after_outcome_is_recorded(monkeypatch):
    _enable_clickhouse(monkeypatch)
    client = MagicMock()
    client.close.side_effect = RuntimeError("client close failed")
    finish = MagicMock(return_value=True)
    monkeypatch.setattr(clickhouse_outbox, "claim_batch", lambda *_args: [_row("one")])
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)
    monkeypatch.setattr(clickhouse_outbox, "_finish", finish)

    with pytest.raises(RuntimeError, match="client close failed"):
        deliver_batch(object(), "worker-close")

    assert finish.call_args.kwargs["success"] is True
    client.close.assert_called_once()


def test_run_once_cli_exits_nonzero_when_any_projection_failed(monkeypatch, capsys):
    conn = object()
    database_context = MagicMock()
    database_context.__enter__.return_value = conn
    monkeypatch.setattr(sys, "argv", ["clickhouse_outbox", "--run-once", "--worker-id", "worker-cli"])
    with (
        patch.object(clickhouse_outbox, "get_connection", return_value=database_context),
        patch.object(clickhouse_outbox, "deliver_batch", return_value={"claimed": 1, "delivered": 0, "failed": 1}),
    ):
        with pytest.raises(SystemExit) as exc_info:
            clickhouse_outbox.main()

    assert exc_info.value.code == 1
    assert '"failed": 1' in capsys.readouterr().out
    database_context.__exit__.assert_called_once()


def test_run_once_cli_accepts_empty_or_successful_batch(monkeypatch, capsys):
    database_context = MagicMock()
    database_context.__enter__.return_value = object()
    monkeypatch.setattr(sys, "argv", ["clickhouse_outbox", "--run-once", "--worker-id", "worker-cli"])
    with (
        patch.object(clickhouse_outbox, "get_connection", return_value=database_context),
        patch.object(clickhouse_outbox, "deliver_batch", return_value={"claimed": 0, "delivered": 0, "failed": 0}),
    ):
        assert clickhouse_outbox.main() is None

    assert '"failed": 0' in capsys.readouterr().out
    database_context.__exit__.assert_called_once()
