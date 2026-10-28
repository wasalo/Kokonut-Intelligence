"""RDF CLI location scope is validated before connecting to PostgreSQL."""

from contextlib import contextmanager
from uuid import UUID

import pytest

from services.rdf import cli


def test_build_rejects_malformed_location_before_opening_database(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["rdf", "build", "--location-id", "not-a-uuid"])
    monkeypatch.setattr(
        cli,
        "get_connection",
        lambda: pytest.fail("malformed location must fail before connecting"),
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "--location-id must be a valid UUID" in capsys.readouterr().err


def test_build_canonicalizes_valid_location_before_persisting(monkeypatch, capsys):
    supplied_location = "B0000000-0000-4000-8000-000000000001"
    expected_location = str(UUID(supplied_location))
    calls = []
    connection = object()

    @contextmanager
    def connection_context():
        calls.append("connect")
        yield connection

    monkeypatch.setattr(
        "sys.argv", ["rdf", "build", "--location-id", supplied_location]
    )
    monkeypatch.setattr(cli, "get_connection", connection_context)
    monkeypatch.setattr(
        "services.rdf.graph_builder.persist_graph",
        lambda conn, location_id: calls.append((conn, location_id)) or 3,
    )

    cli.main()

    assert calls == ["connect", (connection, expected_location)]
    assert f"Built 3 triples for location {expected_location}" in capsys.readouterr().out

