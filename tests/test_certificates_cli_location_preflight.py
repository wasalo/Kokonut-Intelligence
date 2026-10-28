"""Certificate listing validates its farm scope before opening PostgreSQL."""

from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.certificates import cli


@pytest.mark.parametrize("location_id", ["", "not-a-uuid", "1234"])
def test_list_rejects_invalid_location_before_database(monkeypatch, location_id):
    monkeypatch.setattr(
        "sys.argv",
        ["certificates", "list", "--location-id", location_id],
    )
    monkeypatch.setattr(
        cli,
        "get_connection",
        lambda: pytest.fail("invalid location must fail before opening PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


def test_list_canonicalizes_valid_location_before_query(monkeypatch, capsys):
    location_id = str(uuid4())
    supplied_location = location_id.upper()
    connection = Mock()
    connection.execute.return_value.mappings.return_value = []

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(cli, "get_connection", get_connection)
    monkeypatch.setattr(
        "sys.argv",
        ["certificates", "list", "--location-id", supplied_location],
    )

    cli.main()

    connection.execute.assert_called_once()
    query_text = connection.text.call_args.args[0]
    assert "FROM retirement_certificate WHERE location_id = :lid" in query_text
    _query, params = connection.execute.call_args.args
    assert params == {"lid": location_id}
    assert "0 certificates" in capsys.readouterr().out


def test_help_stays_offline(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["certificates", "list", "--help"],
    )
    monkeypatch.setattr(
        cli,
        "get_connection",
        lambda: pytest.fail("help must not open PostgreSQL"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0

