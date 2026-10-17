"""Alert delivery failures should not log provider credentials or payload data."""

from unittest.mock import MagicMock, patch

from services.ingestion import anomaly_detector

SECRET = "notification-provider-secret"
ALERT = {
    "alert_id": "alert-1",
    "sensor_name": "Sensor 1",
    "sensor_type": "soil_moisture",
    "location_name": "Test Farm",
    "message": "Soil moisture below threshold",
    "reading_value": 5.0,
    "threshold_value": 10.0,
    "triggered_at": "2026-10-17T12:00:00Z",
    "severity": "critical",
    "alert_rule_id": "rule-1",
    "sensor_device_id": "device-1",
    "location_id": "location-1",
}


def test_email_delivery_failure_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(anomaly_detector, "logger", logger)
    monkeypatch.setattr(anomaly_detector, "SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setattr(anomaly_detector, "ALERT_EMAIL_TO", "alerts@example.invalid")

    with patch(
        "services.ingestion.anomaly_detector.smtplib.SMTP",
        side_effect=RuntimeError(f"smtp URL included token={SECRET}"),
    ):
        assert anomaly_detector.send_email_notification(ALERT) is False

    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)


def test_directus_delivery_failure_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(anomaly_detector, "logger", logger)
    monkeypatch.setattr(anomaly_detector, "DIRECTUS_URL", "https://directus.example.invalid")
    monkeypatch.setattr(anomaly_detector, "DIRECTUS_TOKEN", "synthetic-directus-token")

    with patch(
        "services.common.http.http.post",
        side_effect=RuntimeError(f"Directus URL included token={SECRET}"),
    ):
        assert anomaly_detector.send_directus_notification(ALERT) is False

    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)


def test_critical_actuation_failure_is_redacted_and_still_requires_approval(
    monkeypatch,
):
    logger = MagicMock()
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {
        "actuator_enabled": True,
        "actuator_type": "valve",
        "actuator_command": "close",
        "actuator_topic": "devices/valve-1/commands",
        "human_approval_required": False,
    }
    monkeypatch.setattr(anomaly_detector, "logger", logger)
    monkeypatch.setattr(anomaly_detector, "get_db", lambda: connection)

    with patch(
        "services.ingestion.mqtt_actuator.send_actuation_command",
        side_effect=RuntimeError(f"broker URL included token={SECRET}"),
    ) as send_command:
        anomaly_detector.send_actuation_commands(ALERT)

    assert send_command.call_args.kwargs["human_approval_required"] is True
    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)
    connection.close.assert_called_once_with()
