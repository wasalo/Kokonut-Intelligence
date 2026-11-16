"""Tests for database configuration defaults in isolated runtimes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_blank_database_ports_use_defaults() -> None:
    """An explicitly blank optional Coolify variable should not break imports."""
    repository_root = Path(__file__).resolve().parents[1]
    environment = {
        "CH_PORT": "",
        "KOKONUT_ENV": "development",
        "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
        "PG_PORT": "",
        "PYTHONPATH": str(repository_root),
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from services.common.db import CH_PORT, PG_PORT; "
            "print(f'{PG_PORT},{CH_PORT}')",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=repository_root,
        env={"PATH": os.environ.get("PATH", ""), **environment},
    )

    assert result.stdout.strip() == "5432,8123"
