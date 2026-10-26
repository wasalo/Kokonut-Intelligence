"""HTTP sensor error handling must keep request and storage details private."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from services.ingestion import http_sensor_receiver

DEVICE_SECRET = "synthetic-device-secret"
FAILURE_SECRET = "postgres://operator:password@db.invalid/sensors"
DEVICE_ID = "sensor-1"


def _request(client, payload=None):
    body = json.dumps(
        payload or {"device_id": DEVICE_ID, "value": 21.5, "unit": "%"},
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(DEVICE_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        f"/api/v1/sensors/{DEVICE_ID}/readings",
        content=body,
        headers={"content-type": "application/json", "x-signature": signature},
    )


def test_credential_lookup_failure_keeps_database_details_out_of_log_and_response(
    monkeypatch,
):
    logger = MagicMock()
    monkeypatch.setattr(http_sensor_receiver, "app", None)
    monkeypatch.setattr(http_sensor_receiver, "logger", logger)
    monkeypatch.setattr(
        http_sensor_receiver,
        "get_db",
        MagicMock(side_effect=RuntimeError(f"connect failed: {FAILURE_SECRET}")),
    )

    with TestClient(http_sensor_receiver._get_app()) as client:
        response = _request(client)

    assert response.status_code == 503
    assert response.json()["detail"] == "Sensor storage unavailable"
    assert FAILURE_SECRET not in response.text
    assert FAILURE_SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)


def test_reading_processing_failure_returns_safe_retryable_response(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(http_sensor_receiver, "app", None)
    monkeypatch.setattr(http_sensor_receiver, "logger", logger)

    auth_db = MagicMock()
    auth_db.cursor.return_value.fetchone.return_value = (DEVICE_SECRET,)
    process_db = MagicMock()
    process_db.cursor.return_value.fetchone.return_value = (
        "db-device-id",
        "location-id",
        None,
        "soil_moisture",
        DEVICE_SECRET,
    )
    monkeypatch.setattr(
        http_sensor_receiver, "get_db", MagicMock(side_effect=[auth_db, process_db])
    )
    monkeypatch.setattr(
        http_sensor_receiver,
        "get_sensor_type_ranges",
        MagicMock(side_effect=RuntimeError(f"query failed: {FAILURE_SECRET}")),
    )

    with TestClient(http_sensor_receiver._get_app()) as client:
        response = _request(client)

    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to process sensor reading"
    assert response.headers["retry-after"] == "30"
    assert FAILURE_SECRET not in response.text
    assert FAILURE_SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)
    process_db.rollback.assert_called_once_with()
    process_db.close.assert_called_once_with()


def test_clickhouse_compatibility_fallback_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(http_sensor_receiver, "logger", logger)

    with patch.object(
        http_sensor_receiver,
        "project_sensor_reading",
        side_effect=RuntimeError(f"ClickHouse URI included {FAILURE_SECRET}"),
    ):
        http_sensor_receiver._insert_ch(
            "reading",
            "location",
            None,
            "sensor",
            "soil_moisture",
            20,
            "%",
            "2026-01-01T00:00:00Z",
        )

    assert FAILURE_SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)
