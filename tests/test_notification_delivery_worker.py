"""Focused checks for isolated notification delivery worker boundaries."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from services.events import notification_delivery_worker as worker


@pytest.mark.parametrize(
    ("worker_id", "limit", "lease_seconds"),
    [
        ("bad id", 1, 300),
        ("worker", 0, 300),
        ("worker", 101, 300),
        ("worker", 1, 29),
        ("worker", 1, 3601),
        ("worker", True, 300),
        ("worker", 1, True),
    ],
)
def test_run_once_rejects_invalid_bounds_before_feature_or_database(
    worker_id, limit, lease_seconds, monkeypatch
):
    feature = MagicMock()
    database = MagicMock()
    monkeypatch.setattr(worker, "require_feature", feature)
    monkeypatch.setattr(worker, "get_worker_db", database)

    with pytest.raises(ValueError):
        worker.run_once(worker_id, limit, lease_seconds)

    feature.assert_not_called()
    database.assert_not_called()


def test_run_once_requires_opt_in_before_database_access(monkeypatch):
    database = MagicMock()
    feature = MagicMock(side_effect=RuntimeError("feature disabled"))
    monkeypatch.setattr(worker, "require_feature", feature)
    monkeypatch.setattr(worker, "get_worker_db", database)

    with pytest.raises(RuntimeError, match="feature disabled"):
        worker.run_once()

    assert [call.args[0] for call in feature.call_args_list] == ["notification_delivery"]
    database.assert_not_called()


def test_run_once_requires_isolated_delivery_opt_in_before_database_access(monkeypatch):
    database = MagicMock()
    features = []

    def require(name):
        features.append(name)
        if name == "isolated_notification_delivery":
            raise RuntimeError("feature disabled")

    monkeypatch.setattr(worker, "require_feature", require)
    monkeypatch.setattr(worker, "get_worker_db", database)

    with pytest.raises(RuntimeError, match="feature disabled"):
        worker.run_once()

    assert features == ["notification_delivery", "isolated_notification_delivery"]
    database.assert_not_called()


def test_claim_commits_before_delivery_and_never_uses_shared_connection(monkeypatch):
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "source_event_id": "00000000-0000-0000-0000-000000000002",
        "event_type": "sensor_alert",
        "channel": "email",
        "destination_key": "primary",
        "payload": {"subject": "Synthetic", "body": "Only a test"},
        "attempt_count": 2,
        "lease_owner": "worker-one",
        "lease_token": "00000000-0000-0000-0000-000000000003",
    }
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchall.return_value = [row]
    get_db = MagicMock(return_value=connection)
    claim_channels = ["email", "webhook"]
    delivered = []
    finished = []
    monkeypatch.setattr(worker, "require_feature", lambda _name: None)
    monkeypatch.setattr(worker, "_configured_channels", lambda: claim_channels)
    monkeypatch.setattr(worker, "get_worker_db", get_db)
    monkeypatch.setattr(worker, "_finish", lambda _conn, _worker_id, got_row, **kwargs:
                        finished.append((got_row, kwargs)) or "succeeded")

    def deliver(got_row):
        delivered.append((got_row, connection.commit.call_count))

    monkeypatch.setattr("services.events.notification_outbox._deliver", deliver)

    result = worker.run_once("worker-one", 17, 180)

    assert result == {"claimed": 1, "delivered": 1, "failed": 0, "lease_lost": 0}
    get_db.assert_called_once_with("notification_delivery")
    sql, parameters = connection.cursor.return_value.__enter__.return_value.execute.call_args.args
    assert "claim_notification_outbox_batch" in sql
    assert parameters == ("worker-one", 17, 180, claim_channels)
    assert connection.commit.call_count == 1
    assert delivered == [(row, 1)]
    assert finished == [(row, {"success": True, "error_class": None})]
    connection.close.assert_called_once_with()


def test_claim_function_commits_success_and_rolls_back_database_error():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{"id": "synthetic"}]

    rows = worker._claim(connection, "worker", 10, 300, ["email"])

    assert rows == [{"id": "synthetic"}]
    statement, parameters = cursor.execute.call_args.args
    assert "kokonut_security.claim_notification_outbox_batch" in statement
    assert parameters == ("worker", 10, 300, ["email"])
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()

    connection.reset_mock()
    connection.cursor.return_value.__enter__.return_value.fetchall.side_effect = OSError
    with pytest.raises(OSError):
        worker._claim(connection, "worker", 10, 300, [])
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


@pytest.mark.parametrize(
    ("attempt_count", "expected_delay"),
    [(1, 15), (2, 30), (8, 1920), (9, 3600)],
)
def test_retry_backoff_matches_notification_contract(attempt_count, expected_delay):
    assert worker._retry_delay_seconds(attempt_count) == expected_delay


def test_finish_calls_bounded_function_and_commits_valid_status():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("failed",)
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "attempt_count": 3,
        "lease_token": "00000000-0000-0000-0000-000000000003",
    }

    result = worker._finish(
        connection,
        "worker-one",
        row,
        success=False,
        error_class="TimeoutError",
    )

    assert result == "failed"
    statement, parameters = cursor.execute.call_args.args
    assert "kokonut_security.finish_notification_outbox_attempt" in statement
    assert parameters == (
        row["id"], "worker-one", row["lease_token"], 3,
        False, "TimeoutError", 60,
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()


def test_finish_rolls_back_unknown_result():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ("unknown",)
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "attempt_count": 1,
        "lease_token": "00000000-0000-0000-0000-000000000003",
    }

    with pytest.raises(RuntimeError, match="invalid result"):
        worker._finish(connection, "worker-one", row, success=True, error_class=None)

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_isolated_cli_mode_routes_to_dedicated_worker(monkeypatch):
    from services.events import cli

    worker_call = MagicMock(return_value=0)
    monkeypatch.setattr(cli, "_run_worker", worker_call)
    monkeypatch.setattr(
        sys,
        "argv",
        ["services.events", "--isolated-notification-worker", "--worker-id", "worker-one"],
    )

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 0
    args, kwargs = worker_call.call_args
    assert args[0].worker_id == "worker-one"
    assert kwargs == {
        "process_events": False,
        "deliver_notifications": False,
        "isolated_notification_delivery": True,
    }
