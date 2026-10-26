"""Standalone and unified market-data CLI contract tests."""

from __future__ import annotations

import sys

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import market_data


def _invoke(unified: bool, arguments: list[str]) -> None:
    if unified:
        ingestion_cli.main(["market_data", *arguments])
    else:
        market_data.main(arguments)


@pytest.mark.parametrize(
    ("source", "arguments"),
    [
        ("world_bank", ["--source", "world_bank", "--commodity", "COFFEE", "--month", "6", "--year", "2026"]),
        ("seed", ["--source", "seed", "--commodity", "COFFEE"]),
    ],
)
def test_standalone_and_unified_cli_forward_the_same_arguments(
    monkeypatch, source: str, arguments: list[str]
) -> None:
    calls = []
    monkeypatch.setattr(market_data, "run", lambda **kwargs: calls.append(kwargs))

    market_data.main(arguments)
    standalone_call = calls.pop()

    ingestion_cli.main(["market_data", *arguments])

    assert calls == [standalone_call]
    assert standalone_call == {
        "commodity": "COFFEE",
        "source": source,
        "month": 6 if source == "world_bank" else None,
        "year": 2026 if source == "world_bank" else None,
    }


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_invalid_world_bank_filters_fail_before_provider_or_database(
    monkeypatch, unified: bool
) -> None:
    monkeypatch.setattr(
        market_data,
        "download_pink_sheet",
        lambda: pytest.fail("invalid filters must fail before provider access"),
    )
    monkeypatch.setattr(
        market_data, "get_db", lambda: pytest.fail("invalid filters must fail before DB access")
    )
    with pytest.raises(ValueError, match="month must be between 1 and 12"):
        _invoke(unified, ["--month", "13"])


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_invalid_source_is_rejected_by_parser_before_run(monkeypatch, unified: bool) -> None:
    monkeypatch.setattr(market_data, "run", lambda **_kwargs: pytest.fail("run must not execute"))

    with pytest.raises(SystemExit) as error:
        _invoke(unified, ["--source", "unknown"])

    assert error.value.code == 2


@pytest.mark.parametrize(
    ("arguments", "raises"),
    [
        (["--source", "seed", "--commodity", "COFFEE"], False),
        (["--source", "unknown"], True),
    ],
)
def test_unified_dispatch_restores_sys_argv_on_success_and_failure(
    monkeypatch, arguments: list[str], raises: bool
) -> None:
    monkeypatch.setattr(market_data, "run", lambda **_kwargs: None)
    monkeypatch.setattr(sys, "argv", ["caller", "argument"])
    original_argv = list(sys.argv)

    if raises:
        with pytest.raises(SystemExit):
            ingestion_cli.main(["market_data", *arguments])
    else:
        ingestion_cli.main(["market_data", *arguments])

    assert sys.argv == original_argv


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        market_data.main(["--help"])
    standalone_help = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["market_data", "--help"])
    unified_help = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified_help.out == standalone_help.out
    assert unified_help.err == standalone_help.err == ""
