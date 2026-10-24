"""Offline standalone/unified contracts for the GIS import CLI."""

from __future__ import annotations

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import gis_import


@pytest.mark.parametrize("target", ["location", "farm", "plot"])
def test_standalone_and_unified_entrypoints_forward_import_scope(
    monkeypatch, target: str
) -> None:
    calls = []
    monkeypatch.setattr(gis_import, "run", lambda **kwargs: calls.append(kwargs))
    arguments = ["--file", "synthetic.geojson", "--target", target]

    gis_import.main(arguments)
    standalone_call = calls.pop()
    ingestion_cli.main(["gis_import", *arguments])

    assert calls == [standalone_call]
    assert standalone_call == {"file_path": "synthetic.geojson", "target": target}


@pytest.mark.parametrize("arguments", [[], ["--file", "synthetic.geojson", "--target", "unknown"]])
def test_invalid_import_arguments_fail_before_run(monkeypatch, arguments: list[str]) -> None:
    monkeypatch.setattr(gis_import, "run", lambda **_kwargs: pytest.fail("run must not execute"))

    with pytest.raises(SystemExit) as standalone_error:
        gis_import.main(arguments)
    with pytest.raises(SystemExit) as unified_error:
        ingestion_cli.main(["gis_import", *arguments])

    assert standalone_error.value.code == unified_error.value.code == 2


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        gis_import.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["gis_import", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""
