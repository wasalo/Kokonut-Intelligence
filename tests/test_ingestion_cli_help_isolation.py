"""Mounted ingestion module help must not require runtime secrets."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from services.ingestion.cli import TOOLS

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_all_ingestion_module_help_paths_are_credential_free() -> None:
    env = os.environ.copy()
    env["KOKONUT_ENV"] = "production"
    env["SOPS_AGE_KEY_FILE"] = "/private/tmp/no-sops-identity"
    env.pop("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", None)
    for name in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD"):
        env.pop(name, None)

    for tool_name, tool in sorted(TOOLS.items()):
        result = subprocess.run(
            [sys.executable, "-m", tool["module"], "--help"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        assert result.returncode == 0, f"{tool_name}: {result.stderr[-500:]}"
        assert result.stdout.strip(), f"{tool_name}: help produced no output"
