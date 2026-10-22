"""Freshness transitions use the durable event and notification pipeline."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.events import notification_outbox
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


def _configure_stale_freshness(monkeypatch, connection):
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
    monkeypatch.setattr(data_freshness, "_query_freshness_configs", lambda *_args: [config])
    monkeypatch.setattr(data_freshness, "_location_ids", lambda _conn: [location_id])
    monkeypatch.setattr(
        data_freshness,
        "_query_latest_data_at",
        lambda *_args: datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    monkeypatch.setattr(data_freshness, "_insert_check_result", lambda *_args: "check-id")
    monkeypatch.setattr(data_freshness, "_alert_state", lambda *_args: state)
    monkeypatch.setattr(data_freshness, "_persist_alert_event", lambda *_args: alert_id)
    return location_id, alert_id


def test_stale_transition_publishes_same_transaction_event_without_inline_delivery(monkeypatch):
    connection = _Connection()
    location_id, alert_id = _configure_stale_freshness(monkeypatch, connection)
    published = []

    class EventBus:
        def __init__(self, conn):
            assert conn is connection

        def publish(self, event_type, payload, **kwargs):
            published.append((event_type, payload, kwargs))
            connection.publish_before_commit = connection.commit_count == 0
            return kwargs["event_id"]

    monkeypatch.setattr("services.events.bus.EventBus", EventBus)
    result = data_freshness.check_freshness(connection)

    assert len(published) == 1
    event_type, payload, options = published[0]
    assert event_type == "data_stale"
    assert options == {
        "event_id": alert_id,
        "source_table": "data_freshness_alert_history",
        "source_id": alert_id,
        "priority": "high",
        "commit": False,
    }
    assert payload["alert_id"] == alert_id
    assert payload["location_id"] == location_id
    assert payload["source_system"] == "weather"
    assert payload["status"] == "critical"
    assert payload["severity"] == "critical"
    assert connection.publish_before_commit is True
    assert connection.commit_count == 1
    assert result["results"][0]["alert_sent"] is False
    assert result["results"][0]["alert_channel"] == "event_bus"
    assert not hasattr(data_freshness, "_send_alert")


def test_event_publish_failure_rolls_back_freshness_transition(monkeypatch):
    connection = _Connection()
    _configure_stale_freshness(monkeypatch, connection)

    class EventBus:
        def __init__(self, conn):
            assert conn is connection

        def publish(self, *_args, **_kwargs):
            raise RuntimeError("synthetic event insert failure")

    monkeypatch.setattr("services.events.bus.EventBus", EventBus)

    with pytest.raises(RuntimeError, match="synthetic event insert failure"):
        data_freshness.check_freshness(connection)

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
        },
    )

    by_channel = {channel: message for channel, _destination, message in messages}
    assert set(by_channel) == {"webhook", "email"}
    assert by_channel["webhook"]["source"] == "weather"
    assert by_channel["webhook"]["status"] == "critical"
    assert by_channel["webhook"]["location_id"] == payload["location_id"]
    assert by_channel["email"]["subject"] == "[Kokonut] Data freshness critical: weather"
    assert payload["message"] in by_channel["email"]["body"]
    encoded = str(messages)
    assert "private-token" not in encoded
    assert "ops@example.test" not in encoded


def test_existing_migration_routes_stale_events_to_callable_handler():
    migration = Path("schemas/postgres/297_event_handler_registration_fix.sql").read_text()
    registration = Path("schemas/postgres/116_event_bus.sql").read_text()

    assert "handler_name = 'data_freshness_checker'" in migration
    assert "('data_freshness_checker', 'data_stale'," in registration
    assert "module_path = 'services.events.handlers'" in migration
    assert "function_name = 'handle_stale_data'" in migration
