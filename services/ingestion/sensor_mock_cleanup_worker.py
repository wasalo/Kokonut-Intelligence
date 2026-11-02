"""Signed, location-scoped cleanup for alerts created by mock sensors."""

from __future__ import annotations

import uuid
from typing import Any

from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db

DELETE_MOCK_SENSOR_ALERTS_SQL = """
SELECT kokonut_security.delete_mock_sensor_alerts(%s::uuid)
"""
DELETE_MOCK_SENSOR_READINGS_SQL = """
SELECT kokonut_security.delete_mock_sensor_readings(%s::uuid)
"""


class SensorMockCleanupWorkerError(RuntimeError):
    """Raised when the bounded mock-alert cleanup returns an invalid result."""


def _normalize_location_id(location_id: str) -> str:
    if not isinstance(location_id, str) or not location_id.strip():
        raise ValueError("location_id must be a UUID")
    try:
        return str(uuid.UUID(location_id.strip()))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("location_id must be a UUID") from exc


def _affected_count(row: Any, operation: str) -> int:
    if row is None or not isinstance(row, (tuple, list)) or not row:
        raise SensorMockCleanupWorkerError(f"mock {operation} cleanup returned no result")
    count = row[0]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise SensorMockCleanupWorkerError(f"mock {operation} cleanup returned an invalid count")
    return count


def delete_mock_sensor_alerts(location_id: str) -> int:
    """Delete demo-device alerts under an exact signed location scope.

    The operation uses the existing ``sensor_anomaly`` worker credential and
    login. PostgreSQL validates the signed ``sensor_reading/process`` context
    again inside the bounded function. A repeated call returns zero after the
    first successful deletion.
    """
    stable_location_id = _normalize_location_id(location_id)
    credential = get_worker_credential("sensor_anomaly")
    connection = get_worker_db("sensor_anomaly")
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=stable_location_id,
            resource="sensor_reading",
            action="process",
        )
        with connection.cursor() as cursor:
            cursor.execute(DELETE_MOCK_SENSOR_ALERTS_SQL, (stable_location_id,))
            result = _affected_count(cursor.fetchone(), "alert")
        connection.commit()
        return result
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        raise
    finally:
        connection.close()


def delete_mock_sensor_readings(location_id: str) -> int:
    """Delete marked demo readings through the same signed worker identity."""
    stable_location_id = _normalize_location_id(location_id)
    credential = get_worker_credential("sensor_anomaly")
    connection = get_worker_db("sensor_anomaly")
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=stable_location_id,
            resource="sensor_reading",
            action="process",
        )
        with connection.cursor() as cursor:
            cursor.execute(DELETE_MOCK_SENSOR_READINGS_SQL, (stable_location_id,))
            result = _affected_count(cursor.fetchone(), "reading")
        connection.commit()
        return result
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        raise
    finally:
        connection.close()
