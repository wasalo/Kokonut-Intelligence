"""Metadata generation validates JSON input before database acquisition."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from services.metadata_api import cli


@pytest.mark.parametrize(
    ("raw_metadata", "expected_error"),
    [
        ("{", "--metadata must contain valid JSON"),
        ("not-json", "--metadata must contain valid JSON"),
        ('{"value":NaN}', "--metadata must contain valid JSON"),
        ('{"value":Infinity}', "--metadata must contain valid JSON"),
        ("[]", "--metadata must be a JSON object"),
        ("null", "--metadata must be a JSON object"),
        ('"text"', "--metadata must be a JSON object"),
        ("12", "--metadata must be a JSON object"),
    ],
)
def test_generate_rejects_invalid_metadata_before_database_access(
    monkeypatch, capsys, raw_metadata, expected_error
):
    from services.common import database

    monkeypatch.setattr(
        database,
        "get_connection",
        lambda: pytest.fail("invalid metadata attempted database access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_generate(SimpleNamespace(metadata=raw_metadata))

    assert exc_info.value.code == 2
    assert capsys.readouterr().err.strip() == f"Error: {expected_error}"


def test_generate_passes_json_object_unchanged_after_preflight(
    monkeypatch, capsys
):
    from services.common import cli as common_cli
    from services.common import database
    from services.metadata_api import resolver

    expected_metadata = {
        "@type": "location",
        "@id": "kokonut:location:11111111-1111-4111-8111-111111111111:v1",
        "name": "Kokonut Genesis",
    }
    connection = object()
    received = []
    output = []

    @contextmanager
    def connection_context():
        yield connection

    monkeypatch.setattr(database, "get_connection", connection_context)
    monkeypatch.setattr(
        resolver,
        "generate_iri_from_metadata",
        lambda conn, metadata: received.append((conn, metadata)) or "kokonut:location:test:v1",
    )
    monkeypatch.setattr(common_cli, "print_json", output.append)

    cli.cmd_generate(SimpleNamespace(metadata='{"@type":"location","@id":"kokonut:location:11111111-1111-4111-8111-111111111111:v1","name":"Kokonut Genesis"}'))

    assert received == [(connection, expected_metadata)]
    assert output == [{"iri": "kokonut:location:test:v1"}]
    assert capsys.readouterr().err == ""
