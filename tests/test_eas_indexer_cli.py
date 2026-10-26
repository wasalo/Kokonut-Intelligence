"""Offline standalone/unified CLI contracts for the EAS indexer."""

from __future__ import annotations

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import eas_indexer


@pytest.mark.parametrize("arguments, expected_chain", [([], None), (["--chain", "celo"], "celo")])
def test_standalone_and_unified_entrypoints_forward_chain(
    monkeypatch, arguments: list[str], expected_chain: str | None
) -> None:
    calls = []
    monkeypatch.setattr(eas_indexer, "run", lambda **kwargs: calls.append(kwargs))

    eas_indexer.main(arguments)
    standalone_call = calls.pop()
    ingestion_cli.main(["eas_indexer", *arguments])

    assert calls == [standalone_call]
    assert standalone_call == {"chain": expected_chain}


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_invalid_chain_fails_before_indexer_run(monkeypatch, unified: bool) -> None:
    monkeypatch.setattr(eas_indexer, "run", lambda **_kwargs: pytest.fail("indexer must not run"))

    with pytest.raises(SystemExit) as error:
        if unified:
            ingestion_cli.main(["eas_indexer", "--chain", "unknown"])
        else:
            eas_indexer.main(["--chain", "unknown"])

    assert error.value.code == 2


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        eas_indexer.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["eas_indexer", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""
