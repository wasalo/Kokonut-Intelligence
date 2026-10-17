"""Actuator MQTT provider errors must not expose broker credentials."""

from unittest.mock import MagicMock, patch

from services.ingestion import mqtt_actuator

SECRET = "mqtt-broker-password-secret"


def test_client_creation_error_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(mqtt_actuator, "logger", logger)

    with patch(
        "services.core.adapters.mqtt.create_client",
        side_effect=RuntimeError(f"mqtt URL included password={SECRET}"),
    ):
        result = mqtt_actuator.publish_to_mqtt(
            "location-1", "irrigation_valve", {"command": "open"}
        )

    assert result is False
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)


def test_publish_error_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    client = MagicMock()
    client.connect.side_effect = RuntimeError(f"broker auth password={SECRET}")
    monkeypatch.setattr(mqtt_actuator, "logger", logger)
    monkeypatch.setattr(mqtt_actuator, "DEFAULT_USERNAME", "synthetic-user")
    monkeypatch.setattr(mqtt_actuator, "DEFAULT_PASSWORD", "synthetic-password")

    with patch("services.core.adapters.mqtt.create_client", return_value=client):
        result = mqtt_actuator.publish_to_mqtt(
            "location-1", "irrigation_valve", {"command": "open"}
        )

    assert result is False
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)
