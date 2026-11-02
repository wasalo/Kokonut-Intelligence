"""Location preflight for optional Impact Office CLI scope."""

from uuid import uuid4

import pytest

from services.office import cli


@pytest.mark.parametrize("location_id", ["", "not-a-uuid", "1234"])
def test_invalid_location_fails_before_opening_database(monkeypatch, location_id):
    monkeypatch.setattr("sys.argv", ["office", "--alerts", "--location-id", location_id])
    monkeypatch.setattr(
        cli,
        "get_pg",
        lambda: pytest.fail("invalid location must fail before database access"),
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2


def test_supplied_location_is_canonicalized_before_optional_alert_query(monkeypatch):
    location_id = str(uuid4())
    seen = []
    connection = type("Connection", (), {"close": lambda self: seen.append("closed")})()
    monkeypatch.setattr(
        "sys.argv",
        ["office", "--alerts", "--location-id", location_id.upper()],
    )
    monkeypatch.setattr(cli, "get_pg", lambda: connection)
    monkeypatch.setattr(
        cli,
        "get_alerts",
        lambda conn, scope, open_only: seen.append((conn, scope, open_only)) or [],
    )

    cli.main()

    assert seen == [(connection, location_id, True), "closed"]


def test_omitted_location_keeps_global_alert_behavior(monkeypatch):
    seen = []
    connection = type("Connection", (), {"close": lambda self: None})()
    monkeypatch.setattr("sys.argv", ["office", "--alerts"])
    monkeypatch.setattr(cli, "get_pg", lambda: connection)
    monkeypatch.setattr(
        cli,
        "get_alerts",
        lambda conn, scope, open_only: seen.append((conn, scope, open_only)) or [],
    )

    cli.main()

    assert seen == [(connection, None, True)]

