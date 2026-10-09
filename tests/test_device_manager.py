"""Tests for services.ingestion.device_manager — IoT device registration and health."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_device_manager_register_device_unknown_type():
    from services.ingestion.device_manager import register_device

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = None  # sensor_type not found

    with pytest.raises(ValueError, match="Unknown sensor type"):
        register_device(conn, "sensor001", "nonexistent_type", "loc-001")


def test_device_manager_register_device_success():
    from services.ingestion.device_manager import register_device

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.side_effect = [
        ("type-id-001",),  # sensor_type lookup
        ("device-id-001",),  # INSERT RETURNING id
        None,  # health INSERT ON CONFLICT DO NOTHING
    ]

    result = register_device(conn, "sensor001", "air_temperature", "loc-001")

    assert result == "device-id-001"
    assert conn.commit.called


def test_device_manager_list_devices_returns_list():
    from services.ingestion.device_manager import list_devices

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = []

    result = list_devices(conn)
    assert isinstance(result, list)


def test_device_manager_get_device_health_returns_none():
    from services.ingestion.device_manager import get_device_health

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = None

    result = get_device_health(conn, "nonexistent-slug")
    assert result is None


def test_device_manager_update_health_calls_commit():
    from services.ingestion.device_manager import update_health

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

    update_health(conn, "device-001", battery_pct=85.0, signal_strength_dbm=-60.0)

    conn.commit.assert_called_once()
    cur.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
