"""Offline standalone/unified CLI contracts for the Gnosis indexer."""

from __future__ import annotations

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import gnosis_indexer


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], {"from_block": None, "to_block": None}),
        (["--from-block", "350", "--to-block", "375"], {"from_block": 350, "to_block": 375}),
    ],
)
def test_standalone_and_unified_entrypoints_forward_block_interval(
    monkeypatch, arguments: list[str], expected: dict[str, int | None]
) -> None:
    calls = []
    monkeypatch.setattr(gnosis_indexer, "run", lambda **kwargs: calls.append(kwargs))

    gnosis_indexer.main(arguments)
    standalone_call = calls.pop()
    ingestion_cli.main(["gnosis_indexer", *arguments])

    assert calls == [standalone_call]
    assert standalone_call == expected


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_non_integer_block_fails_before_indexer_run(monkeypatch, unified: bool) -> None:
    monkeypatch.setattr(
        gnosis_indexer, "run", lambda **_kwargs: pytest.fail("indexer must not run")
    )

    with pytest.raises(SystemExit) as error:
        if unified:
            ingestion_cli.main(["gnosis_indexer", "--from-block", "invalid"])
        else:
            gnosis_indexer.main(["--from-block", "invalid"])

    assert error.value.code == 2


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--from-block", "-1"], "--from-block must be non-negative"),
        (["--from-block", "10", "--to-block", "9"], "--to-block must be greater than or equal"),
    ],
)
@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_invalid_block_interval_fails_before_provider_or_database(
    monkeypatch, arguments: list[str], message: str, unified: bool
) -> None:
    monkeypatch.setattr(
        gnosis_indexer, "get_web3", lambda: pytest.fail("invalid range reached provider")
    )
    monkeypatch.setattr(
        gnosis_indexer, "get_db", lambda: pytest.fail("invalid range opened database")
    )

    with pytest.raises(ValueError, match=message):
        if unified:
            ingestion_cli.main(["gnosis_indexer", *arguments])
        else:
            gnosis_indexer.main(arguments)


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        gnosis_indexer.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["gnosis_indexer", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""
