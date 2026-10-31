"""Strategic Reserve seed-vault location scope is checked before PostgreSQL."""

from uuid import uuid4

import pytest

from services.strategic_reserve import cli


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize("location_id", ["", "not-a-uuid", "1234"])
def test_seed_vault_rejects_invalid_location_before_database(monkeypatch, location_id):
    monkeypatch.setattr(
        "sys.argv",
        ["strategic-reserve", "seed-vault", "--location-id", location_id],
    )
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid location must fail before opening PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


def test_seed_vault_canonicalizes_valid_location_before_health_query(monkeypatch):
    connection = _Connection()
    location_id = str(uuid4())
    health_calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli.health,
        "seed_vault_health",
        lambda conn, requested_location: health_calls.append((conn, requested_location)) or {},
    )
    monkeypatch.setattr(cli, "print_json", lambda _result: None)
    monkeypatch.setattr(
        "sys.argv",
        ["strategic-reserve", "seed-vault", "--location-id", location_id.upper()],
    )

    cli.main()

    assert health_calls == [(connection, location_id)]
    assert connection.closed


def test_direct_seed_vault_command_rejects_invalid_location_before_database(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid location must fail before opening PostgreSQL"),
    )

    with pytest.raises(ValueError, match="valid UUID"):
        cli.cmd_seed_vault("invalid")


def test_unscoped_health_command_remains_unscoped(monkeypatch):
    connection = _Connection()
    health_calls = []
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(
        cli.health,
        "reserve_health",
        lambda conn: health_calls.append(conn) or {},
    )
    monkeypatch.setattr(cli, "print_json", lambda _result: None)
    monkeypatch.setattr("sys.argv", ["strategic-reserve", "health"])

    cli.main()

    assert health_calls == [connection]
    assert connection.closed

