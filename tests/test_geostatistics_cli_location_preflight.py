"""Location UUIDs are rejected before the geostatistics CLI opens a DB connection."""

import sys
from types import SimpleNamespace

import pytest

from services.geostatistics import cli

LOCATION_ID = "a0000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize(
    "argv",
    [
        ["variogram", "--location-id", "not-a-uuid", "--property", "soil_carbon"],
        ["kriging", "--location-id", "not-a-uuid", "--property", "soil_carbon"],
        ["simulate", "--location-id", "not-a-uuid", "--property", "soil_carbon"],
        ["autocorrelation", "--location-id", "not-a-uuid", "--property", "soil_carbon"],
        ["cross-validate", "--location-id", "not-a-uuid", "--property", "soil_carbon"],
        ["sensor-design", "--location-id", "not-a-uuid"],
        ["residual-kriging", "--location-id", "not-a-uuid"],
        ["spatial-cv-soc", "--location-id", "not-a-uuid"],
    ],
)
def test_all_location_commands_reject_malformed_scope_before_database(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["geostatistics", *argv])
    monkeypatch.setattr(
        "services.common.database.get_db",
        lambda: pytest.fail("invalid location must fail before opening PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2


@pytest.mark.parametrize("location_id", ["", "null", "00000000-0000-0000-0000-000000000000x"])
def test_empty_and_malformed_location_values_fail_before_database(monkeypatch, location_id):
    monkeypatch.setattr(
        sys,
        "argv",
        ["geostatistics", "residual-kriging", "--location-id", location_id],
    )
    monkeypatch.setattr(
        "services.common.database.get_db",
        lambda: pytest.fail("invalid location must fail before opening PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2


def test_valid_location_reaches_selected_handler_and_closes_connection(monkeypatch):
    connection = SimpleNamespace(closed=False)
    connection.close = lambda: setattr(connection, "closed", True)
    calls = []
    monkeypatch.setattr(
        sys,
        "argv",
        ["geostatistics", "residual-kriging", "--location-id", LOCATION_ID],
    )
    monkeypatch.setattr("services.common.database.get_db", lambda: connection)
    monkeypatch.setattr(
        "services.analytics.soc_prediction.residual_kriging_correction",
        lambda conn, location_id: calls.append((conn, location_id)) or {"ok": True},
    )
    monkeypatch.setattr(cli, "_print_result", lambda *_args: None)

    cli.main()

    assert calls == [(connection, LOCATION_ID)]
    assert connection.closed


def test_help_without_a_command_does_not_open_database(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["geostatistics"])
    monkeypatch.setattr(
        "services.common.database.get_db",
        lambda: pytest.fail("CLI help must not open PostgreSQL"),
    )

    cli.main()

