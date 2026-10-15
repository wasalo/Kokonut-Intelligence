from unittest.mock import MagicMock

import pytest

from services.events import notification_outbox


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
    monkeypatch.setattr(notification_outbox.smtplib, "SMTP", MagicMock(return_value=server))
    row = _row("outbox-123", channel="email")
    row["payload"] = {"subject": "Synthetic alert", "body": "Test message"}

    notification_outbox._deliver(row)

    notification_outbox.smtplib.SMTP.assert_called_once_with(
        "smtp.example.test", 587, timeout=10
    )
    server.__enter__.assert_called_once()
    server.ehlo.assert_called()
    server.starttls.assert_called_once()
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
        notification_outbox.smtplib,
        "SMTP",
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
