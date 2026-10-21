"""The unified ingestion CLI dispatches only callable module entry points."""

from __future__ import annotations

import sys

import pytest

from services.ingestion import cli


def test_missing_module_main_fails_closed_and_restores_process_arguments(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original_argv = sys.argv
    monkeypatch.setattr(cli.importlib, "import_module", lambda _module: object())

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["mock_sensors", "--cleanup"])

    assert exc_info.value.code == 2
    assert "does not expose a callable main()" in capsys.readouterr().err
    assert sys.argv is original_argv
