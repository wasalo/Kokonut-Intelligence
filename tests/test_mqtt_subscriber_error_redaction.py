"""MQTT callback and fallback errors must not expose message or credential data."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion.mqtt_subscriber import MQTTSensorSubscriber

SECRET = "mqtt-payload-or-password-secret"


def _subscriber(delivery_mode):
    subscriber = object.__new__(MQTTSensorSubscriber)
    subscriber._delivery_mode = delivery_mode
    subscriber._timestamp_mode = "legacy"
    subscriber._handle_reading = MagicMock(
        side_effect=RuntimeError(f"database URI included password={SECRET}")
    )
    return subscriber


def test_legacy_callback_logs_exception_class_without_payload_details(monkeypatch):
    from services.ingestion import mqtt_subscriber

    logger = MagicMock()
    monkeypatch.setattr(mqtt_subscriber, "logger", logger)
    subscriber = _subscriber("legacy")
    message = SimpleNamespace(
        topic="sensors/location/soil_moisture/readings", payload=b"{}", qos=0
    )

    subscriber._on_message(MagicMock(), None, message)

    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)


def test_qos1_callback_raises_sanitized_error_without_ack(monkeypatch):
    from services.ingestion import mqtt_subscriber

    logger = MagicMock()
    monkeypatch.setattr(mqtt_subscriber, "logger", logger)
    subscriber = _subscriber("qos1")
    message = SimpleNamespace(
        topic="sensors/location/soil_moisture/readings", payload=b"{}", qos=1, mid=7
    )
    client = MagicMock()

    with patch(
        "services.ingestion.mqtt_delivery.process_delivery",
        side_effect=RuntimeError(f"database URI included password={SECRET}"),
    ):
        with pytest.raises(
            RuntimeError, match=r"MQTT message processing failed \(RuntimeError\)"
        ) as error:
            subscriber._on_message(client, None, message)

    assert SECRET not in str(error.value)
    assert error.value.__suppress_context__ is True
    assert SECRET not in str(logger.error.call_args)
    client.ack.assert_not_called()


def test_clickhouse_compatibility_fallback_logs_only_exception_class(monkeypatch):
    from services.ingestion import mqtt_subscriber

    logger = MagicMock()
    monkeypatch.setattr(mqtt_subscriber, "logger", logger)
    subscriber = _subscriber("legacy")

    with patch.object(
        mqtt_subscriber,
        "project_sensor_reading",
        side_effect=RuntimeError(f"ClickHouse URI included password={SECRET}"),
    ):
        subscriber._insert_ch(
            "reading",
            "location",
            None,
            "sensor",
            "soil_moisture",
            20,
            "%",
            "2026-01-01T00:00:00Z",
        )

    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)
