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


def _invoke(unified: bool, arguments: list[str]) -> None:
    if unified:
        ingestion_cli.main(["price_attestation", *arguments])
    else:
        price_attestation.main(arguments)


@pytest.mark.parametrize(
    "arguments",
    [[], ["--commodity", "coffee"], ["--price", "2.50"]],
)
def test_incomplete_invocation_shows_help_without_opening_database(
    monkeypatch, capsys, arguments: list[str]
) -> None:
    monkeypatch.setattr(
        price_attestation, "get_db", lambda: pytest.fail("incomplete invocation opened DB")
    )

    price_attestation.main(arguments)

    assert "usage:" in capsys.readouterr().out


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--commodity", "coffee", "--price", "0"], "greater than zero"),
        (["--commodity", "coffee", "--price", "-2"], "greater than zero"),
        (["--commodity", "coffee", "--price", "nan"], "finite number"),
        (["--commodity", "coffee", "--price", "inf"], "finite number"),
        (["--commodity", " ", "--price", "2"], "commodity must be"),
        (["--commodity", "coffee", "--price", "2", "--source", " "], "source must be"),
    ],
)
def test_invalid_manual_attestation_fails_before_database_access(
    monkeypatch, capsys, unified: bool, arguments: list[str], message: str
) -> None:
    monkeypatch.setattr(
        price_attestation,
        "get_db",
        lambda: pytest.fail("invalid price input must fail before DB access"),
    )

    with pytest.raises(SystemExit) as error:
        _invoke(unified, arguments)

    assert error.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_daily_mode_rejects_manual_arguments_before_database_access(
    monkeypatch, unified: bool
) -> None:
    monkeypatch.setattr(
        price_attestation,
        "get_db",
        lambda: pytest.fail("conflicting operation modes must fail before DB access"),
    )

    with pytest.raises(SystemExit) as error:
        _invoke(
            unified,
            ["--run-daily", "--commodity", "coffee", "--price", "2.5"],
        )

    assert error.value.code == 2


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"price": 0}, "greater than zero"),
        ({"price": True}, "greater than zero"),
        ({"price": float("nan")}, "finite number"),
        ({"source_count": 0}, "positive integer"),
        ({"source_count": True}, "positive integer"),
        ({"confidence": -0.1}, "between zero and one"),
        ({"confidence": float("inf")}, "between zero and one"),
        ({"confidence": True}, "between zero and one"),
        ({"commodity": " "}, "commodity must be"),
    ],
)
def test_attest_price_validates_before_opening_cursor(overrides: dict, message: str) -> None:
    class NoCursorConnection:
        def cursor(self):
            pytest.fail("invalid attestation input must fail before cursor creation")

    arguments = {
        "commodity": "coffee",
        "price": 2.5,
        "source": "test",
        "source_count": 1,
        "confidence": 1.0,
        "currency": "USD",
        "chain": "celo",
    }
    arguments.update(overrides)

    with pytest.raises(ValueError, match=message):
        price_attestation.attest_price(NoCursorConnection(), **arguments)


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
