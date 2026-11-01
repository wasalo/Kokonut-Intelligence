"""Freshness transitions use the durable event and notification pipeline."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from services.events import handlers, notification_outbox
from services.ingestion import data_freshness


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def execute(self, statement, _parameters=None):
        self.connection.statements.append(statement)

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.statements = []
        self.cursors = []
        self.commit_count = 0
        self.rollback_count = 0
        self.publish_before_commit = None

    def cursor(self, **_kwargs):
        cursor = _Cursor(self)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def _configure_stale_freshness(*, enqueue_error=None):
    location_id = "10000000-0000-0000-0000-000000000001"
    alert_id = "20000000-0000-0000-0000-000000000002"
    config = {
        "id": "30000000-0000-0000-0000-000000000003",
        "source_system": "weather",
        "stale_threshold_minutes": 30,
        "critical_threshold_minutes": 60,
        "location_scoped": True,
        "alert_cooldown_minutes": 60,
        "escalation_cooldown_minutes": 15,
    }
    state = {
        "id": "40000000-0000-0000-0000-000000000004",
        "current_status": "fresh",
        "last_event_status": "fresh",
        "last_event_at": None,
    }
    persistence = Mock()
    persistence.list_configs.return_value = [config]
    persistence.list_location_ids.return_value = [location_id]
    persistence.latest_data_at.return_value = datetime.now(timezone.utc) - timedelta(minutes=90)
    persistence.insert_check.return_value = "check-id"
    persistence.lock_alert_state.return_value = state
    persistence.persist_alert_event.return_value = alert_id
    persistence.enqueue_alert_event.return_value = alert_id
    if enqueue_error is not None:
        persistence.enqueue_alert_event.side_effect = enqueue_error
    return location_id, alert_id, persistence


def test_stale_transition_enqueues_durable_notification_through_persistence():
    connection = _Connection()
    location_id, alert_id, persistence = _configure_stale_freshness()
    result = data_freshness.check_freshness(connection, persistence=persistence)

    persistence.persist_alert_event.assert_called_once()
    persistence.enqueue_alert_event.assert_called_once_with(
        alert_id,
        "weather",
        "critical",
        90,
        persistence.latest_data_at.return_value,
        "alert",
        location_id,
    )
    persistence.update_check_alert.assert_called_once_with("check-id", False, "event_bus")
    assert connection.commit_count == 1
    assert result["results"][0]["alert_sent"] is False
    assert result["results"][0]["alert_channel"] == "event_bus"
    assert connection.statements == ["SAVEPOINT freshness_scope", "RELEASE SAVEPOINT freshness_scope"]


def test_event_publish_failure_rolls_back_freshness_transition(monkeypatch):
    connection = _Connection()
    _location_id, _alert_id, persistence = _configure_stale_freshness(
        enqueue_error=RuntimeError("synthetic event insert failure")
    )

    with pytest.raises(RuntimeError, match="synthetic event insert failure"):
        data_freshness.check_freshness(connection, persistence=persistence)

    assert connection.commit_count == 0
    assert connection.rollback_count == 1


def test_data_stale_outbox_preserves_webhook_and_email_channels_without_secrets():
    payload = {
        "alert_id": "20000000-0000-0000-0000-000000000002",
        "source_system": "weather",
        "status": "critical",
        "severity": "critical",
        "location_id": "10000000-0000-0000-0000-000000000001",
        "gap_minutes": 90,
        "last_data_at": "2026-10-22T10:00:00+00:00",
        "message": "[CRISP] Data freshness alert: weather\nStatus: critical\nGap: 90 minutes\n",
    }

    messages = notification_outbox._notification_payloads(
        "data_stale",
        payload,
        environment={
            "ALERT_WEBHOOK_URL": "https://hooks.example.test/private-token",
            "ALERT_SMTP_HOST": "smtp.example.test",
            "ALERT_EMAIL_TO": "ops@example.test",
            "KOKONUT_FEATURE_DIRECTUS": "true",
            "DIRECTUS_ADMIN_TOKEN": "synthetic-token",
        },
    )

    by_channel = {channel: message for channel, _destination, message in messages}
    assert set(by_channel) == {"webhook", "directus", "email"}
    assert by_channel["webhook"]["source"] == "weather"
    assert by_channel["webhook"]["status"] == "critical"
    assert by_channel["webhook"]["location_id"] == payload["location_id"]
    assert by_channel["directus"] == {
        "message": payload["message"],
        "severity": "critical",
    }
    assert by_channel["email"]["subject"] == "[Kokonut] Data freshness critical: weather"
    assert payload["message"] in by_channel["email"]["body"]
    encoded = str(messages)
    assert "private-token" not in encoded
    assert "synthetic-token" not in encoded
    assert "ops@example.test" not in encoded

    directus_disabled = notification_outbox._notification_payloads(
        "data_stale",
        payload,
        environment={
            "ALERT_WEBHOOK_URL": "https://hooks.example.test/private-token",
            "ALERT_SMTP_HOST": "smtp.example.test",
            "ALERT_EMAIL_TO": "ops@example.test",
            "KOKONUT_FEATURE_DIRECTUS": "false",
            "DIRECTUS_ADMIN_TOKEN": "synthetic-token",
        },
    )
    assert {channel for channel, _destination, _message in directus_disabled} == {
        "webhook",
        "email",
    }


def test_stale_data_handler_commits_outbox_intents_before_ack(monkeypatch):
    connection = MagicMock()
    enqueue = MagicMock(return_value=2)
    shared_connection = MagicMock()
    location_id = "10000000-0000-0000-0000-000000000001"
    event_id = "20000000-0000-0000-0000-000000000002"
    payload = {"location_id": location_id, "alert_id": event_id, "status": "critical"}
    monkeypatch.setattr(
        notification_outbox,
        "_notification_payloads",
        lambda *_args, **_kwargs: [("webhook", "primary", {"message": "Synthetic alert"})],
    )
    monkeypatch.setattr(
        "services.core.features.require_feature", lambda _name: None
    )
    monkeypatch.setattr(
        "services.common.worker_database.get_worker_db",
        lambda identity: connection if identity == "notification_enqueue" else None,
        raising=False,
    )
    monkeypatch.setattr(
        notification_outbox, "enqueue_event_notification_isolated", enqueue
    )
    monkeypatch.setattr(
        "services.common.database.get_connection", shared_connection
    )

    handlers.handle_stale_data("data_stale", payload, event_id=event_id)

    enqueue.assert_called_once_with(
        connection,
        event_id=event_id,
        event_type="data_stale",
        payload=payload,
        location_id=location_id,
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
    shared_connection.assert_not_called()


def test_stale_data_handler_propagates_enqueue_failure_for_event_retry(monkeypatch):
    connection = MagicMock()
    enqueue = MagicMock(side_effect=RuntimeError("synthetic enqueue failure"))
    monkeypatch.setattr(
        notification_outbox,
        "_notification_payloads",
        lambda *_args, **_kwargs: [("webhook", "primary", {"message": "Synthetic alert"})],
    )
    monkeypatch.setattr(
        "services.core.features.require_feature", lambda _name: None
    )
    monkeypatch.setattr(
        "services.common.worker_database.get_worker_db",
        lambda _identity: connection,
        raising=False,
    )
    monkeypatch.setattr(
        notification_outbox, "enqueue_event_notification_isolated", enqueue
    )

    with pytest.raises(RuntimeError, match="synthetic enqueue failure"):
        handlers.handle_stale_data(
            "data_stale",
            {"location_id": "10000000-0000-0000-0000-000000000001"},
            event_id="20000000-0000-0000-0000-000000000002",
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_existing_migration_routes_stale_events_to_callable_handler():
    migration = Path("schemas/postgres/297_event_handler_registration_fix.sql").read_text()
    registration = Path("schemas/postgres/116_event_bus.sql").read_text()

    assert "handler_name = 'data_freshness_checker'" in migration
    assert "('data_freshness_checker', 'data_stale'," in registration
    assert "module_path = 'services.events.handlers'" in migration
    assert "function_name = 'handle_stale_data'" in migration
