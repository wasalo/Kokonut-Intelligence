"""Fresh PostgreSQL readiness must wait for the final TCP listener."""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_postgres_healthchecks_use_tcp() -> None:
    for compose_file in ROOT.glob("docker-compose*.yml"):
        config = yaml.safe_load(compose_file.read_text())
        for service in config.get("services", {}).values():
            healthcheck = service.get("healthcheck") or {}
            command = healthcheck.get("test", [])
            if "pg_isready" not in str(command):
                continue
            assert "-h 127.0.0.1" in str(command), compose_file


def test_python_postgres_readiness_probes_use_tcp() -> None:
    for script in (ROOT / "scripts").rglob("*.py"):
        tree = ast.parse(script.read_text(), filename=str(script))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            command = node.args[0]
            if not isinstance(command, (ast.List, ast.Tuple)):
                continue
            values = [
                item.value for item in command.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
            if "pg_isready" not in values:
                continue
            index = values.index("pg_isready")
            assert values[index + 1 : index + 3] == ["-h", "127.0.0.1"], script

    retention_check = (ROOT / "scripts/check-retention-policy-disposable.py").read_text()
    assert "pg_isready -h 127.0.0.1" in retention_check


def test_shell_postgres_readiness_probes_use_tcp() -> None:
    for script in (ROOT / "scripts").rglob("*.sh"):
        for line_number, line in enumerate(script.read_text().splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or "pg_isready" not in line:
                continue
            assert "-h 127.0.0.1" in line, f"{script}:{line_number}"
