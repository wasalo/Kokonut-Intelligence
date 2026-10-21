"""Offline contracts for standalone and unified price-attestation CLI paths."""

from __future__ import annotations

import sys

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import price_attestation


class _Connection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    "arguments",
    [[], ["--commodity", "coffee"], ["--price", "2.50"], ["--commodity", "coffee", "--price", "0"]],
)
def test_incomplete_invocation_shows_help_without_opening_database(
    monkeypatch, capsys, arguments: list[str]
) -> None:
    monkeypatch.setattr(
        price_attestation, "get_db", lambda: pytest.fail("incomplete invocation opened DB")
    )

    price_attestation.main(arguments)

    assert "usage:" in capsys.readouterr().out


def test_manual_attestation_dispatch_matches_standalone_and_unified(monkeypatch) -> None:
    connections = []
    attestations = []
    outputs = []

    def get_db():
        connection = _Connection()
        connections.append(connection)
        return connection

    def attest_price(connection, commodity, price, source):
        attestations.append((connection, commodity, price, source))
        return {"status": "success", "commodity": commodity, "price": price, "source": source}

    monkeypatch.setattr(price_attestation, "get_db", get_db)
    monkeypatch.setattr(price_attestation, "attest_price", attest_price)
    monkeypatch.setattr(price_attestation, "print_json", outputs.append)
    arguments = ["--commodity", "coffee", "--price", "2.5", "--source", "world_bank"]

    price_attestation.main(arguments)
    standalone = outputs.pop()
    standalone_call = attestations.pop()

    original_argv = list(sys.argv)
    ingestion_cli.main(["price_attestation", *arguments])

    assert outputs == [standalone]
    assert len(attestations) == 1
    assert attestations[0][1:] == standalone_call[1:]
    assert [connection.closed for connection in connections] == [True, True]
    assert sys.argv == original_argv


def test_daily_attestation_uses_and_closes_database_connection(monkeypatch) -> None:
    connection = _Connection()
    calls = []
    outputs = []
    monkeypatch.setattr(price_attestation, "get_db", lambda: connection)
    monkeypatch.setattr(
        price_attestation,
        "attest_daily_prices",
        lambda conn: calls.append(conn) or {"status": "success", "prices_attested": 0},
    )
    monkeypatch.setattr(price_attestation, "print_json", outputs.append)

    price_attestation.main(["--run-daily"])

    assert calls == [connection]
    assert outputs == [{"status": "success", "prices_attested": 0}]
    assert connection.closed


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        price_attestation.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["price_attestation", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""
