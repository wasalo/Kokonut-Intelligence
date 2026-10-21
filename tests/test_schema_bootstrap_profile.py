"""Compose contract for isolated PostgreSQL schema replay."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = "docker-compose.schema-bootstrap.yml"
PINNED_AMD64_IMAGE = (
    "postgis/postgis:16-3.4@sha256:"
    "44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
)


def _database_config(*, image_override: str | None = None) -> dict:
    env = {
        "PATH": os.environ["PATH"],
        "POSTGRES_PASSWORD": "compose-test-only",
    }
    if image_override is not None:
        env["KOKONUT_BOOTSTRAP_POSTGRES_IMAGE"] = image_override
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "/dev/null",
            "-f",
            COMPOSE_FILE,
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["services"]["database"]


def test_schema_bootstrap_default_is_pinned_and_networkless() -> None:
    database = _database_config()

    assert database["image"] == PINNED_AMD64_IMAGE
    assert database["network_mode"] == "none"
    assert not database.get("ports")
    assert not database.get("networks")
    assert database["volumes"] == [
        {
            "type": "volume",
            "source": "schema-bootstrap-data",
            "target": "/var/lib/postgresql/data",
            "volume": {},
        }
    ]


def test_schema_bootstrap_accepts_arm64_image_override_without_relaxing_isolation() -> None:
    database = _database_config(image_override="kokonut-kernel-postgis-arm64:local")

    assert database["image"] == "kokonut-kernel-postgis-arm64:local"
    assert database["network_mode"] == "none"
    assert not database.get("ports")
    assert not database.get("networks")


def test_explicit_clean_bootstrap_does_not_load_workstation_dotenv_secrets() -> None:
    script = (ROOT / "scripts" / "verify-clean-bootstrap.sh").read_text()

    assert 'KOKONUT_ENV_SECRETS_NOT_REQUIRED=true' in script
    assert "PG_USER=kokonut" in script
    assert 'PG_DB="$DB_NAME"' in script

