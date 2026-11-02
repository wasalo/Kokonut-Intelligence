"""CLI timestamp validation for equipment usage writes."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from services.analytics import equipment


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--start", "not-a-datetime"),
        ("--start", "2026-10-28T08:30:00"),
        ("--end", "not-a-datetime"),
        ("--end", "2026-10-28T09:15:00"),
    ],
)
def test_invalid_or_timezone_naive_usage_datetime_fails_before_database(
    monkeypatch, option, value
):
    connection_factory = Mock()
    monkeypatch.setattr(equipment.cli, "_connection_factory", connection_factory)

    argv = [
        "log",
        "--location-id", "location-id",
        "--asset-id", "asset-id",
        "--start", "2026-10-28T08:30:00Z",
        option, value,
    ]
    with pytest.raises(SystemExit) as exc_info:
        equipment.cli.main(argv)

    assert exc_info.value.code == 2
    connection_factory.assert_not_called()


def test_offset_aware_usage_datetimes_reach_service_as_datetimes(monkeypatch, capsys):
    connection = Mock()
    connection_factory = Mock(return_value=connection)
    service = Mock(return_value={
        "asset_id": "asset-id",
        "hours": 0.75,
        "operation_type": "inspection",
    })
    monkeypatch.setattr(equipment.cli, "_connection_factory", connection_factory)
    monkeypatch.setattr(equipment, "log_equipment_usage", service)

    equipment.cli.main([
        "log",
        "--location-id", "location-id",
        "--asset-id", "asset-id",
        "--start", "2026-10-28T08:30:00-04:00",
        "--end", "2026-10-28T09:15:00+02:00",
        "--operation", "inspection",
        "--json",
    ])

    service.assert_called_once()
    call = service.call_args
    assert call.args[0] is connection
    assert call.args[3] == datetime.fromisoformat("2026-10-28T08:30:00-04:00")
    assert call.args[4] == datetime.fromisoformat("2026-10-28T09:15:00+02:00")
    assert call.args[3].utcoffset() is not None
    assert call.args[4].utcoffset() is not None
    connection_factory.assert_called_once_with()
    connection.close.assert_called_once_with()
    assert '"asset_id": "asset-id"' in capsys.readouterr().out


def test_omitted_usage_end_remains_none(monkeypatch, capsys):
    connection = Mock()
    connection_factory = Mock(return_value=connection)
    service = Mock(return_value={
        "asset_id": "asset-id",
        "hours": None,
        "operation_type": "inspection",
    })
    monkeypatch.setattr(equipment.cli, "_connection_factory", connection_factory)
    monkeypatch.setattr(equipment, "log_equipment_usage", service)

    equipment.cli.main([
        "log",
        "--location-id", "location-id",
        "--asset-id", "asset-id",
        "--start", "2026-10-28T08:30:00Z",
        "--json",
    ])

    service.assert_called_once()
    assert service.call_args.args[3] == datetime(2026, 10, 28, 8, 30, tzinfo=timezone.utc)
    assert service.call_args.args[4] is None
    connection.close.assert_called_once_with()
    assert '"asset_id": "asset-id"' in capsys.readouterr().out
