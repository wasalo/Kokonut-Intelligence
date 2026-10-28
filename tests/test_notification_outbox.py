import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from services.common import smtp
from services.events import handlers, notification_outbox


def _row(row_id: str, channel: str = "webhook") -> dict:
    return {
        "id": row_id,
        "source_event_id": f"event-{row_id}",
        "event_type": "sensor_alert",
        "channel": channel,
        "destination_key": "primary",
        "payload": {"message": "Synthetic alert"},
        "attempt_count": 1,
        "lease_owner": "worker-test",
        "lease_token": f"lease-{row_id}",
    }


@pytest.mark.parametrize(
    ("limit", "lease_seconds"),
    [
        (True, 300),
        (1, True),
    ],
)
def test_claim_batch_rejects_boolean_bounds_before_database_access(limit, lease_seconds):
    conn = MagicMock()

    with pytest.raises(ValueError):
        notification_outbox.claim_batch(
            conn,
            "worker-test",
            limit,
            lease_seconds=lease_seconds,
        )

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_delivery_failure_records_only_exception_class_and_continues(monkeypatch):
    rows = [_row("failed"), _row("delivered")]
    finishes = []
    warning = MagicMock()
    monkeypatch.setattr(notification_outbox.logger, "warning", warning)
    monkeypatch.setattr(notification_outbox, "claim_batch", lambda *_args: rows)
    deliver = MagicMock(side_effect=[TimeoutError("secret URL and token"), None])
    monkeypatch.setattr(notification_outbox, "_deliver", deliver)
    monkeypatch.setattr(
        notification_outbox,
        "_finish_attempt",
        lambda _conn, row, *, success, error_class: finishes.append(
            (row["id"], success, error_class)
        ) or ("failed" if not success else "succeeded"),
    )

    result = notification_outbox.deliver_batch(object(), "worker-test")

    assert result == {"claimed": 2, "delivered": 1, "failed": 1, "lease_lost": 0}
    assert finishes == [
        ("failed", False, "TimeoutError"),
        ("delivered", True, None),
    ]
    assert "secret URL and token" not in str(warning.call_args)


def test_completion_database_failure_propagates_without_processing_next_row(monkeypatch):
    rows = [_row("first"), _row("second")]
    conn = object()
    monkeypatch.setattr(notification_outbox, "claim_batch", lambda *_args: rows)
    deliver = MagicMock()
    monkeypatch.setattr(notification_outbox, "_deliver", deliver)
    finish = MagicMock(side_effect=RuntimeError("database completion failed"))
    monkeypatch.setattr(notification_outbox, "_finish_attempt", finish)

    with pytest.raises(RuntimeError, match="database completion failed"):
        notification_outbox.deliver_batch(conn, "worker-test")

    deliver.assert_called_once_with(rows[0])
    finish.assert_called_once_with(
        conn, rows[0], success=True, error_class=None
    )


def test_notification_intent_persists_optional_location_lineage():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("outbox-row",)
    location_id = "A0000000-0000-0000-0000-000000000001"
    event_id = "a0000000-0000-0000-0000-000000000002"
    message = {"subject": "Synthetic alert"}

    with patch.object(
        notification_outbox,
        "_notification_payloads",
        return_value=[("webhook", "primary", message)],
    ):
        inserted = notification_outbox.enqueue_event_notification(
            conn,
            event_id=event_id,
            event_type="sensor_alert",
            payload={"message": "Synthetic alert"},
            location_id=location_id,
        )

    assert inserted == 1
    statement, parameters = cursor.execute.call_args.args
    assert "payload, location_id)" in statement
    assert parameters[-1] == location_id.lower()


def test_isolated_notification_intent_calls_bounded_function_and_preserves_transaction():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (2,)
    event_id = "a0000000-0000-0000-0000-000000000002"
    location_id = "A0000000-0000-0000-0000-000000000001"
    messages = [
        ("webhook", "primary", {"message": "Synthetic alert"}),
        ("directus", "primary", {"message": "Synthetic alert"}),
    ]
    with patch.object(notification_outbox, "_notification_payloads", return_value=messages):
        inserted = notification_outbox.enqueue_event_notification_isolated(
            conn,
            event_id=event_id,
            event_type="threshold_breached",
            payload={"message": "Synthetic alert"},
            location_id=location_id,
        )

    assert inserted == 2
    statement, parameters = cursor.execute.call_args.args
    assert "kokonut_security.enqueue_notification_intents" in statement
    assert parameters[:3] == (event_id, "threshold_breached", location_id.lower())
    request = json.loads(parameters[3])
    assert request == [
        {"channel": channel, "destination_key": "primary", "payload": message}
        for channel, _, message in messages
    ]
    conn.commit.assert_not_called()
    conn.rollback.assert_not_called()


def test_isolated_notification_intent_rejects_invalid_function_result():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (None,)
    with patch.object(
        notification_outbox,
        "_notification_payloads",
        return_value=[("webhook", "primary", {"message": "Synthetic alert"})],
    ):
        with pytest.raises(notification_outbox.NotificationOutboxError, match="invalid result"):
            notification_outbox.enqueue_event_notification_isolated(
                conn,
                event_id="a0000000-0000-0000-0000-000000000002",
                event_type="threshold_breached",
                payload={"message": "Synthetic alert"},
            )


def test_alert_handler_uses_exact_isolated_login_when_feature_is_enabled(monkeypatch):
    conn = MagicMock()
    worker_db = MagicMock(return_value=conn)
    isolated_enqueue = MagicMock(return_value=1)
    common_connection = MagicMock()
    monkeypatch.setattr(
        "services.common.worker_database.get_worker_db", worker_db, raising=False
    )
    monkeypatch.setattr(
        "services.core.features.is_enabled", lambda name: name == "isolated_notification_enqueue"
    )
    monkeypatch.setattr(
        notification_outbox, "enqueue_event_notification_isolated", isolated_enqueue
    )
    monkeypatch.setattr(
        "services.common.database.get_connection", common_connection
    )
    monkeypatch.setattr(notification_outbox, "_notification_payloads", lambda *_a, **_k: [
        ("webhook", "primary", {"message": "Synthetic alert"})
    ])

    handlers.handle_alert_notification(
        "threshold_breached",
        {"message": "Synthetic alert"},
        event_id="a0000000-0000-0000-0000-000000000002",
    )

    worker_db.assert_called_once_with("notification_enqueue")
    isolated_enqueue.assert_called_once()
    conn.commit.assert_called_once_with()
    conn.rollback.assert_not_called()
    conn.close.assert_called_once_with()
    common_connection.assert_not_called()


def test_alert_handler_forwards_payload_location_to_outbox(monkeypatch):
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ("outbox-row",)
    connection = MagicMock()
    connection.__enter__.return_value = conn
    monkeypatch.setattr(
        notification_outbox,
        "_notification_payloads",
        lambda *_args, **_kwargs: [("webhook", "primary", {"message": "Synthetic alert"})],
    )
    monkeypatch.setattr("services.common.database.get_connection", lambda: connection)
    event_id = "a0000000-0000-0000-0000-000000000002"
    location_id = "A0000000-0000-0000-0000-000000000001"

    handlers.handle_alert_notification(
        "threshold_breached",
        {"message": "Synthetic alert", "location_id": location_id},
        event_id=event_id,
    )

    statement, parameters = conn.cursor.return_value.__enter__.return_value.execute.call_args.args
    assert "payload, location_id)" in statement
    assert parameters[0] == event_id
    assert parameters[-1] == location_id.lower()
    connection.__enter__.assert_called_once()
    connection.__exit__.assert_called_once()


def test_alert_handler_rejects_malformed_location_before_database_write(monkeypatch):
    conn = MagicMock()
    connection = MagicMock()
    connection.__enter__.return_value = conn
    monkeypatch.setattr(
        notification_outbox,
        "_notification_payloads",
        lambda *_args, **_kwargs: [("webhook", "primary", {"message": "Synthetic alert"})],
    )
    get_connection = MagicMock(return_value=connection)
    monkeypatch.setattr("services.common.database.get_connection", get_connection)

    with pytest.raises(ValueError, match="location_id must be a valid UUID"):
        handlers.handle_alert_notification(
            "threshold_breached",
            {"message": "Synthetic alert", "location_id": "not-a-location"},
            event_id="a0000000-0000-0000-0000-000000000002",
        )

    get_connection.assert_called_once()
    conn.cursor.assert_not_called()
    connection.__exit__.assert_called_once()


def test_alert_handler_without_destination_and_event_id_does_not_connect(monkeypatch):
    monkeypatch.setattr(notification_outbox, "_notification_payloads", lambda *_args, **_kwargs: [])
    get_connection = MagicMock()
    monkeypatch.setattr("services.common.database.get_connection", get_connection)

    handlers.handle_alert_notification("threshold_breached", {"message": "No destination"})

    get_connection.assert_not_called()


def test_notification_retry_with_same_content_and_location_is_idempotent():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        None,
        (
            "threshold_breached",
            {"message": "Synthetic alert"},
            "a0000000-0000-0000-0000-000000000001",
        ),
    ]
    location_id = "a0000000-0000-0000-0000-000000000001"
    event_id = "a0000000-0000-0000-0000-000000000002"
    message = {"message": "Synthetic alert"}
    with patch.object(
        notification_outbox,
        "_notification_payloads",
        return_value=[("webhook", "primary", message)],
    ):
        inserted = notification_outbox.enqueue_event_notification(
            conn,
            event_id=event_id,
            event_type="threshold_breached",
            payload=message,
            location_id=location_id,
        )

    assert inserted == 0
    assert cursor.execute.call_count == 2
    assert "ON CONFLICT (source_event_id, channel, destination_key) DO NOTHING" in (
        cursor.execute.call_args_list[0].args[0]
    )
    assert "FOR UPDATE" in cursor.execute.call_args_list[1].args[0]


def test_notification_retry_fills_missing_location_lineage_and_rejects_conflict():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        None,
        ("sensor_alert", {"subject": "Synthetic alert"}, None),
    ]
    location_id = "a0000000-0000-0000-0000-000000000001"
    event_id = "a0000000-0000-0000-0000-000000000002"
    message = {"subject": "Synthetic alert"}

    with patch.object(
        notification_outbox,
        "_notification_payloads",
        return_value=[("webhook", "primary", message)],
    ):
        inserted = notification_outbox.enqueue_event_notification(
            conn,
            event_id=event_id,
            event_type="sensor_alert",
            payload={"message": "Synthetic alert"},
            location_id=location_id,
        )

    assert inserted == 0
    update_statement, update_parameters = cursor.execute.call_args.args
    assert "SET location_id = %s::uuid" in update_statement
    assert update_parameters == (location_id, event_id, "webhook", "primary")

    cursor.fetchone.side_effect = [
        None,
        ("sensor_alert", message, "a0000000-0000-0000-0000-000000000002"),
    ]
    with patch.object(
        notification_outbox,
        "_notification_payloads",
        return_value=[("webhook", "primary", message)],
    ):
        with pytest.raises(notification_outbox.NotificationIdempotencyConflict, match="location"):
            notification_outbox.enqueue_event_notification(
                conn,
                event_id=event_id,
                event_type="sensor_alert",
                payload={"message": "Synthetic alert"},
                location_id=location_id,
            )


def test_lost_completion_lease_is_counted_separately_and_continues(monkeypatch):
    rows = [_row("stale"), _row("owned")]
    monkeypatch.setattr(notification_outbox, "claim_batch", lambda *_args: rows)
    monkeypatch.setattr(notification_outbox, "_deliver", MagicMock())
    statuses = iter(("lease_lost", "succeeded"))
    monkeypatch.setattr(
        notification_outbox,
        "_finish_attempt",
        lambda *_args, **_kwargs: next(statuses),
    )

    result = notification_outbox.deliver_batch(object(), "worker-test")

    assert result == {"claimed": 2, "delivered": 1, "failed": 0, "lease_lost": 1}


def test_email_delivery_uses_stable_idempotency_headers_and_closes_smtp(monkeypatch):
    monkeypatch.setenv("ALERT_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("ALERT_SMTP_PORT", "587")
    monkeypatch.setenv("ALERT_EMAIL_TO", "review@example.test")
    server = MagicMock()
    server.__enter__.return_value = server
    monkeypatch.setattr("services.common.smtp.smtplib.SMTP", MagicMock(return_value=server))
    row = _row("outbox-123", channel="email")
    row["payload"] = {"subject": "Synthetic alert", "body": "Test message"}

    notification_outbox._deliver(row)

    smtp.smtplib.SMTP.assert_called_once_with(
        "smtp.example.test", 587, timeout=10
    )
    server.__enter__.assert_called_once()
    server.ehlo.assert_called()
    server.starttls.assert_called_once()
    assert "context" in server.starttls.call_args.kwargs
    server.send_message.assert_called_once()
    message = server.send_message.call_args.args[0]
    assert message["X-Kokonut-Idempotency-Key"] == "outbox-123"
    assert message["Message-ID"] == "<kokonut-outbox-outbox-123@kokonut.local>"
    server.__exit__.assert_called_once()


def test_email_provider_exception_is_recorded_by_class_only(monkeypatch):
    monkeypatch.setenv("ALERT_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("ALERT_SMTP_PORT", "25")
    monkeypatch.setenv("ALERT_EMAIL_TO", "review@example.test")
    monkeypatch.setattr(
        "services.common.smtp.smtplib.SMTP",
        MagicMock(side_effect=OSError("credential-bearing provider detail")),
    )
    row = _row("email-failure", channel="email")
    row["payload"] = {"subject": "Synthetic alert", "body": "Test message"}
    monkeypatch.setattr(notification_outbox, "claim_batch", lambda *_args: [row])
    finish = MagicMock(return_value="failed")
    monkeypatch.setattr(notification_outbox, "_finish_attempt", finish)

    result = notification_outbox.deliver_batch(object(), "worker-test")

    assert result == {"claimed": 1, "delivered": 0, "failed": 1, "lease_lost": 0}
    assert finish.call_args.kwargs == {"success": False, "error_class": "OSError"}


@pytest.mark.parametrize(
    ("smtp_settings", "error_class"),
    [
        ({"ALERT_SMTP_TLS_MODE": "disabled"}, "SMTPConfigurationError"),
        (
            {"ALERT_SMTP_TLS_MODE": "plain", "ALERT_SMTP_USER": "synthetic-user"},
            "SMTPConfigurationError",
        ),
        ({"ALERT_SMTP_PORT": "not-a-port"}, "ValueError"),
    ],
)
def test_invalid_smtp_settings_keep_email_rows_unclaimed_and_other_channels_active(
    smtp_settings, error_class, monkeypatch
):
    logger = MagicMock()
    monkeypatch.setattr(notification_outbox, "logger", logger)
    environment = {
        "ALERT_WEBHOOK_URL": "https://hooks.example.test/synthetic",
        "ALERT_SMTP_HOST": "smtp.example.test",
        "ALERT_SMTP_PORT": "587",
        "ALERT_EMAIL_TO": "review@example.test",
        **smtp_settings,
    }

    channels = notification_outbox._configured_channels(environment)

    assert channels == ["webhook"]
    assert logger.warning.call_args.args == (
        "Email notification channel is not configured (%s)",
        error_class,
    )


@pytest.mark.parametrize(
    ("result", "expected_exit"),
    [
        ({"claimed": 0, "delivered": 0, "failed": 0, "lease_lost": 0}, 0),
        ({"claimed": 1, "delivered": 0, "failed": 1, "lease_lost": 0}, 1),
        ({"claimed": 1, "delivered": 0, "failed": 0, "lease_lost": 1}, 1),
    ],
)
def test_notification_process_cli_exit_code_tracks_failures_and_lease_loss(
    result, expected_exit, monkeypatch, capsys
):
    from services.common import database
    from services.events import cli

    conn = object()
    database_context = MagicMock()
    database_context.__enter__.return_value = conn
    monkeypatch.setattr(
        sys,
        "argv",
        ["services.events", "--notification-process", "--worker-id", "worker-cli", "--batch-size", "10"],
    )
    with (
        patch.object(database, "get_connection", return_value=database_context),
        patch.object(notification_outbox, "deliver_batch", return_value=result),
    ):
        with pytest.raises(SystemExit) as exc_info:
            cli.main()

    assert exc_info.value.code == expected_exit
    assert '"claimed"' in capsys.readouterr().out
    database_context.__exit__.assert_called_once()
