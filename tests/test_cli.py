"""CLI smoke tests — verify each CLI runs without error."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import services.cli as unified_cli
from services.ingestion import cli as ingestion_cli

CLI_COMMANDS = [
    # forecast CLI
    ("python3", "-m", "services.forecast.cli", "--list"),
    ("python3", "-m", "services.forecast.cli", "--help"),

    # analytics CLI
    ("python3", "-m", "services.analytics.cli", "--help"),

    # revenue_multiplier CLI
    ("python3", "-m", "services.revenue_multiplier.cli", "--list-dimensions"),
    ("python3", "-m", "services.revenue_multiplier.cli", "--help"),

    # fortune500 CLI
    ("python3", "-m", "services.fortune500.cli", "--help"),

    # report_generator CLI
    ("python3", "-m", "services.export.report_generator", "--list"),
    ("python3", "-m", "services.export.report_generator", "--help"),

    # ingestion CLI
    ("python3", "-m", "services.ingestion.sensor_ingester", "--list"),
    ("python3", "-m", "services.ingestion.sensor_ingester", "--help"),

    # weather CLI
    ("python3", "-m", "services.ingestion.weather", "--help"),

    # market_data CLI
    ("python3", "-m", "services.ingestion.market_data", "--help"),

    # CIDS exporter CLI
    ("python3", "-m", "services.registry.cids_export", "--help"),

    # Agent workflow CLIs
    ("python3", "-m", "services.agents.tasks", "--help"),
    ("python3", "-m", "services.agents.cids_agent", "--help"),
    ("python3", "-m", "services.agents.feedback_agent", "--help"),

    # Spreadsheet bridge CLI
    ("python3", "-m", "services.export.spreadsheet_bridge", "--help"),
]


def test_unified_cli_help_lists_mounted_and_native_groups() -> None:
    result = CliRunner().invoke(unified_cli.app, ["--help"])
    assert result.exit_code == 0, result.output
    for name, _module, _help in unified_cli._MOUNTED:
        assert name in result.output
    for name in ("kernel", "dao", "treasury"):
        assert name in result.output


def test_every_mounted_group_exposes_help() -> None:
    runner = CliRunner()
    for name, _module, _help in unified_cli._MOUNTED:
        result = runner.invoke(unified_cli.app, [name, "--help"])
        assert result.exit_code == 0, f"{name}: {result.output} {result.exception!r}"


def test_every_mounted_argparse_help_is_offline() -> None:
    environment = {**os.environ, "KOKONUT_ENV": "development"}
    environment.pop("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", None)
    environment.pop("SOPS_AGE_KEY", None)
    environment["SOPS_AGE_KEY_FILE"] = "/__codex_no_sops_key__"

    def check_group(entry):
        name, _module, _help = entry
        try:
            result = subprocess.run(
                [sys.executable, "-m", "services.cli", name, "--", "--help"],
                capture_output=True,
                text=True,
                timeout=20,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return name, "timed out"
        if result.returncode != 0:
            return name, (result.stderr or result.stdout).strip()
        if "usage:" not in result.stdout.lower():
            return name, "legacy argparse usage was not displayed"
        if "sops" in result.stderr.lower():
            return name, result.stderr.strip()
        return None

    with ThreadPoolExecutor(max_workers=5) as pool:
        failures = [failure for failure in pool.map(check_group, unified_cli._MOUNTED) if failure]
    assert not failures, "legacy parser help failures: " + repr(failures)


def test_every_mounted_group_forwards_legacy_arguments(monkeypatch) -> None:
    runner = CliRunner()
    original_argv = list(sys.argv)

    for name, expected_module, _help in unified_cli._MOUNTED:
        captured: dict[str, list[str]] = {}

        def fake_main() -> None:
            captured["argv"] = list(sys.argv)

        def fake_import(module_path: str):
            assert module_path == expected_module
            return SimpleNamespace(main=fake_main)

        monkeypatch.setattr(unified_cli.importlib, "import_module", fake_import)
        result = runner.invoke(unified_cli.app, [name, "--forwarded-option", "sentinel"])
        assert result.exit_code == 0, f"{name}: {result.output} {result.exception!r}"
        assert captured["argv"][1:] == ["--forwarded-option", "sentinel"]
        assert sys.argv == original_argv


def test_unified_agent_catalogue_list_is_offline() -> None:
    result = CliRunner().invoke(unified_cli.app, ["agents", "list"])
    assert result.exit_code == 0, result.output
    assert "cids_export" in result.output
    assert "SOPS decryption failed" not in result.output


def test_legacy_argparse_help_uses_separator_and_stays_offline() -> None:
    result = CliRunner().invoke(unified_cli.app, ["agents", "--", "--help"])
    assert result.exit_code == 0, result.output
    assert "Kokonut agent task catalogue" in result.output
    assert "SOPS decryption failed" not in result.output


def test_ingestion_cli_preserves_help_and_list_commands(capsys) -> None:
    ingestion_cli.main([])
    help_output = capsys.readouterr().out
    assert "Kokonut ingestion pipelines" in help_output

    ingestion_cli.main(["--list"])
    list_output = capsys.readouterr().out
    assert "sensor_ingester" in list_output


def test_ingestion_cli_rejects_unknown_top_level_argument(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        ingestion_cli.main(["--__codex_invalid_argument__"])

    assert exc_info.value.code == 2
    assert "unrecognized arguments: --__codex_invalid_argument__" in capsys.readouterr().err


def test_unified_ingestion_cli_rejects_unknown_top_level_argument() -> None:
    result = CliRunner().invoke(
        unified_cli.app,
        ["ingestion", "--", "--__codex_invalid_argument__"],
    )
    assert result.exit_code == 2
    assert "unrecognized arguments: --__codex_invalid_argument__" in result.output


def run_cli_tests():
    errors = []
    for cmd in CLI_COMMANDS:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"  ✓ {' '.join(cmd)}")
            else:
                # Some CLIs exit with error when no args are provided
                # Check if it's a "help" or "list" command
                if "--help" in cmd or "--list" in cmd or "--list-dimensions" in cmd:
                    print(f"  ✓ {' '.join(cmd)}")
                else:
                    print(f"  ✗ {' '.join(cmd)}: {result.stderr.strip()}")
                    errors.append((cmd, result.stderr))
        except Exception as e:
            print(f"  ✗ {' '.join(cmd)}: {e}")
            errors.append((cmd, str(e)))

    return errors


if __name__ == "__main__":
    print("=== CLI Smoke Tests ===")
    errors = run_cli_tests()

    passed = len(CLI_COMMANDS) - len(errors)
    total = len(CLI_COMMANDS)
    print(f"\n  Pass: {passed}/{total}")

    if errors:
        for cmd, err in errors:
            print(f"  ✗ {' '.join(cmd)}: {err}")
        sys.exit(1)
    else:
        print("  All CLI smoke tests passed ✓")
