"""Successful offline legacy command parity through the unified CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["KOKONUT_ENV"] = "development"
    environment["KOKONUT_DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/unused"
    environment["DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/unused"
    environment["SOPS_AGE_KEY_FILE"] = "/__codex_no_sops_key__"
    environment.pop("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", None)
    environment.pop("KOKONUT_ALLOW_PLAINTEXT_ENV", None)
    environment.pop("SOPS_AGE_KEY", None)
    return environment


def _run(module_or_unified: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *module_or_unified],
        capture_output=True,
        text=True,
        timeout=20,
        env=environment,
    )


def _manifest() -> dict[str, object]:
    return {
        "form_id": "cli_parity_fixture",
        "version": "1.0.0",
        "name": "CLI parity fixture",
        "description": "Offline acceptance fixture.",
        "form_schema": {
            "type": "object",
            "required": ["note"],
            "properties": {"note": {"type": "string"}},
            "additionalProperties": False,
        },
        "ui_schema": {},
        "collection_type": "field_note",
        "location_id": None,
        "is_public": False,
        "status": "active",
        "consent_policy": {
            "status": "not_required",
            "data_category": "field_observation",
            "purpose": "CLI parity acceptance.",
            "scope_type": "location",
            "scope_id": None,
            "recipient_type": "location_operator",
            "recipient_party_id": None,
            "recipient_name": None,
            "version": None,
        },
        "review": {
            "reviewed_by": "fixture-reviewer",
            "reviewed_at": "2026-10-20T12:00:00Z",
            "evidence": [{"source": "test-fixture", "basis": "Synthetic acceptance fixture."}],
        },
    }


@pytest.mark.parametrize("group", ["agents", "ingestion"])
def test_offline_catalogue_output_matches_standalone_cli(group: str) -> None:
    args = ["list"] if group == "agents" else ["--list"]
    module = "services.agents.cli" if group == "agents" else "services.ingestion.cli"
    environment = _environment()

    standalone = _run(["-m", module, *args], environment)
    unified = _run(["-m", "services.cli", group, "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    assert unified.stdout == standalone.stdout
    assert unified.stderr == standalone.stderr == ""


def test_offline_form_validation_output_matches_standalone_cli(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    args = ["validate", "--manifest", str(manifest_path)]
    environment = _environment()

    standalone = _run(["-m", "services.mobile.forms_cli", *args], environment)
    unified = _run(["-m", "services.cli", "mobile-forms", "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    assert json.loads(unified.stdout) == json.loads(standalone.stdout)
    assert json.loads(unified.stdout)["manifest"]["database_write"] is False
    assert unified.stderr == standalone.stderr == ""


def test_offline_form_preview_output_matches_standalone_cli(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    args = ["preview", "--manifest", str(manifest_path)]
    environment = _environment()

    standalone = _run(["-m", "services.mobile.forms_cli", *args], environment)
    unified = _run(["-m", "services.cli", "mobile-forms", "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    standalone_output = json.loads(standalone.stdout)
    unified_output = json.loads(unified.stdout)
    assert unified_output == standalone_output
    assert unified_output["publication"] == "not applied"
    assert unified_output["change"] == "version_comparison_not_supplied"
    assert unified.stderr == standalone.stderr == ""


def test_audit_spool_missing_file_status_matches_standalone_without_creating_it(tmp_path: Path) -> None:
    journal = tmp_path / "journal.sqlite3"
    args = ["status", "--path", str(journal)]
    environment = _environment()

    standalone = _run(["-m", "services.gateway.audit_spool_cli", *args], environment)
    unified = _run(["-m", "services.cli", "audit-spool", "--", *args], environment)

    assert standalone.returncode == unified.returncode == 0
    assert json.loads(unified.stdout) == json.loads(standalone.stdout)
    assert json.loads(unified.stdout)["exists"] is False
    assert not journal.exists()
    assert unified.stderr == standalone.stderr == ""


def test_systems_module_catalogue_output_matches_standalone_cli() -> None:
    environment = _environment()

    standalone = _run(["-m", "services.systems.cli", "--list-modules"], environment)
    unified = _run(["-m", "services.cli", "systems", "--", "--list-modules"], environment)

    assert standalone.returncode == unified.returncode == 0
    assert unified.stdout == standalone.stdout
    assert "causal_loops" in unified.stdout
    assert unified.stderr == standalone.stderr == ""


def test_database_backed_capability_list_output_matches_with_stubbed_query(monkeypatch, capsys) -> None:
    from typer.testing import CliRunner

    import services.cli as unified_cli
    from services.analytics import cli_capability_map

    calls: list[dict[str, object]] = []
    result_rows = [{"id": "synthetic-capability", "name": "Soil monitoring", "status": "active"}]

    def fake_list_capabilities(*, guild_key, capability_type, status):
        calls.append({"guild_key": guild_key, "capability_type": capability_type, "status": status})
        return result_rows

    monkeypatch.setattr(cli_capability_map, "list_capabilities", fake_list_capabilities)
    original_argv = list(sys.argv)
    try:
        sys.argv = ["services.analytics.cli_capability_map", "list", "--status", "active"]
        cli_capability_map.main()
        standalone_output = capsys.readouterr().out
    finally:
        sys.argv = original_argv

    unified = CliRunner().invoke(
        unified_cli.app,
        ["capability-map", "--", "list", "--status", "active"],
    )

    assert unified.exit_code == 0, unified.output
    assert json.loads(unified.output) == json.loads(standalone_output)
    assert json.loads(unified.output) == result_rows
    assert calls == [
        {"guild_key": None, "capability_type": None, "status": "active"},
        {"guild_key": None, "capability_type": None, "status": "active"},
    ]
    assert unified.stderr == ""
