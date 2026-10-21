"""The unified ingestion CLI dispatches only callable module entry points."""

from __future__ import annotations

import sys
from pathlib import Path

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


def test_successful_cli_contract_inventory_covers_every_registered_tool() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "refactor"
        / "unified-cli-kernel-contract.md"
    )
    contract = contract_path.read_text(encoding="utf-8")
    parity_inventory = contract.split("## Successful offline command parity sample", 1)[1]
    parity_inventory = parity_inventory.split("For each row,", 1)[0]

    missing = [
        tool_name
        for tool_name in cli.TOOLS
        if f"`{tool_name} " not in parity_inventory
    ]

    assert not missing, f"registered ingestion tools missing from contract inventory: {missing}"
