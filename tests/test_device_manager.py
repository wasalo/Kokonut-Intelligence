"""Tests for services.ingestion.device_manager — IoT device registration and health."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

LOCATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_device_manager_register_device_unknown_type():
    from services.ingestion.device_manager import register_device

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = None  # sensor_type not found

    with pytest.raises(ValueError, match="Unknown sensor type"):
        register_device(conn, "sensor001", "nonexistent_type", LOCATION_ID)


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

    result = register_device(conn, "sensor001", "air_temperature", LOCATION_ID)

    assert result == "device-id-001"
    assert conn.commit.called


def test_device_manager_register_rejects_slug_conflict_from_another_location():
    from services.ingestion.device_manager import register_device

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.side_effect = [
        ("type-id-001",),
        None,
    ]

    with pytest.raises(ValueError, match="already assigned to a different location"):
        register_device(conn, "sensor001", "air_temperature", LOCATION_ID)

    conflict_sql = cur.execute.call_args_list[1].args[0]
    assert "WHERE sensor_device.location_id = EXCLUDED.location_id" in conflict_sql
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_device_manager_register_rejects_invalid_location_before_cursor():
    from services.ingestion.device_manager import register_device

    conn = MagicMock()

    with pytest.raises(ValueError, match="location_id must be a UUID"):
        register_device(conn, "sensor001", "air_temperature", "invalid")

    conn.cursor.assert_not_called()


def test_device_manager_list_devices_returns_list():
    from services.ingestion.device_manager import list_devices

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = []

    result = list_devices(conn, LOCATION_ID)
    assert isinstance(result, list)
    sql, parameters = cur.execute.call_args.args
    assert "WHERE sd.location_id = %s" in sql
    assert parameters == [LOCATION_ID]


def test_device_manager_get_device_health_returns_none():
    from services.ingestion.device_manager import get_device_health

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = None

    result = get_device_health(conn, "nonexistent-slug", LOCATION_ID)
    assert result is None
    sql, parameters = cur.execute.call_args.args
    assert "AND sd.location_id = %s" in sql
    assert parameters == ("nonexistent-slug", "nonexistent-slug", LOCATION_ID)


def test_device_manager_update_health_calls_commit():
    from services.ingestion.device_manager import update_health

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = ("device-001",)

    update_health(
        conn,
        "device-001",
        battery_pct=85.0,
        signal_strength_dbm=-60.0,
        location_id=LOCATION_ID,
    )

    conn.commit.assert_called_once()
    cur.close.assert_called_once()
    sql, parameters = cur.execute.call_args.args
    assert "AND sd.location_id = %s" in sql
    assert parameters[-1] == LOCATION_ID


def test_device_manager_update_health_rejects_device_outside_location():
    from services.ingestion.device_manager import update_health

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = None

    with pytest.raises(ValueError, match="not registered in the requested location"):
        update_health(conn, "device-001", location_id=LOCATION_ID)

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cur.close.assert_called_once()


@pytest.mark.parametrize("operation", ["list_devices", "get_device_health"])
def test_device_reads_reject_invalid_location_before_cursor(operation):
    from services.ingestion.device_manager import get_device_health, list_devices

    conn = MagicMock()
    function = {
        "list_devices": lambda: list_devices(conn, "invalid"),
        "get_device_health": lambda: get_device_health(conn, "sensor001", "invalid"),
    }[operation]

    with pytest.raises(ValueError, match="location_id must be a UUID"):
        function()

    conn.cursor.assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--list"],
        ["--health", "--device-id", "sensor001"],
        ["--register", "--device-id", "sensor001", "--sensor-type", "air_temperature"],
        ["--list", "--location-id", "invalid"],
        ["--list", "--health", "--location-id", LOCATION_ID],
    ],
)
def test_device_cli_rejects_missing_scope_or_operation_conflict_before_database(arguments, monkeypatch):
    from services.ingestion import device_manager

    monkeypatch.setattr(
        device_manager,
        "get_db",
        lambda: pytest.fail("invalid device command must fail before database access"),
    )

    with pytest.raises(SystemExit) as error:
        device_manager.main(arguments)

    assert error.value.code == 2


def test_device_cli_help_without_an_operation_is_offline(monkeypatch, capsys):
    from services.ingestion import device_manager

    monkeypatch.setattr(
        device_manager,
        "get_db",
        lambda: pytest.fail("help must not open the device database"),
    )

    device_manager.main([])

    assert "usage:" in capsys.readouterr().out


def test_device_cli_passes_location_scope_to_list_query(monkeypatch):
    from services.ingestion import device_manager

    conn = MagicMock()
    monkeypatch.setattr(device_manager, "get_db", lambda: conn)
    list_devices = MagicMock(return_value=[])
    monkeypatch.setattr(device_manager, "list_devices", list_devices)
    monkeypatch.setattr(device_manager, "print_json", lambda value: None)

    device_manager.main(["--list", "--location-id", LOCATION_ID])

    list_devices.assert_called_once_with(conn, location_id=LOCATION_ID)
    conn.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
