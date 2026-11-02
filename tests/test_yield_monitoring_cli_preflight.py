"""CLI preflight checks for harvest-yield dates."""

from datetime import date
from unittest.mock import Mock

import pytest

from services.analytics import yield_monitoring


@pytest.mark.parametrize("harvest_date", ["bad-date", "2026-02-30"])
def test_invalid_harvest_date_fails_before_database(monkeypatch, harvest_date):
    connection_factory = Mock()
    monkeypatch.setattr(
        yield_monitoring.cli, "_connection_factory", connection_factory
    )

    with pytest.raises(SystemExit) as exc_info:
        yield_monitoring.cli.main([
            "record",
            "--location-id", "location-id",
            "--yield-amount", "2500",
            "--date", harvest_date,
        ])

    assert exc_info.value.code == 2
    connection_factory.assert_not_called()


def test_valid_harvest_date_reaches_service_as_date(monkeypatch, capsys):
    connection = Mock()
    connection_factory = Mock(return_value=connection)
    service = Mock(return_value={"harvest_date": date(2026, 2, 28)})
    monkeypatch.setattr(
        yield_monitoring.cli, "_connection_factory", connection_factory
    )
    monkeypatch.setattr(yield_monitoring, "record_yield_observation", service)

    yield_monitoring.cli.main([
        "record",
        "--location-id", "location-id",
        "--yield-amount", "2500",
        "--date", "2026-02-28",
        "--json",
    ])

    service.assert_called_once()
    assert service.call_args.args[0] is connection
    assert service.call_args.kwargs["harvest_date"] == date(2026, 2, 28)
    assert isinstance(service.call_args.kwargs["harvest_date"], date)
    connection_factory.assert_called_once_with()
    connection.close.assert_called_once_with()
    assert '"harvest_date": "2026-02-28"' in capsys.readouterr().out


def test_omitted_harvest_date_remains_none(monkeypatch, capsys):
    connection = Mock()
    connection_factory = Mock(return_value=connection)
    service = Mock(return_value={"harvest_date": None})
    monkeypatch.setattr(
        yield_monitoring.cli, "_connection_factory", connection_factory
    )
    monkeypatch.setattr(yield_monitoring, "record_yield_observation", service)

    yield_monitoring.cli.main([
        "record",
        "--location-id", "location-id",
        "--yield-amount", "2500",
        "--json",
    ])

    service.assert_called_once()
    assert service.call_args.kwargs["harvest_date"] is None
    connection.close.assert_called_once_with()
    assert '"harvest_date": null' in capsys.readouterr().out
