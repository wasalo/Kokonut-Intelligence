"""Static and local-process tests for release and upgrade safety contracts."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import services

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"


def test_release_identity_matches_version_file():
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert version == services.__version__
    assert version.count(".") == 2
    assert all(part.isdigit() for part in version.split("."))


@pytest.mark.parametrize(
    "script", ["backup.sh", "restore.sh", "rollback.sh", "upgrade.sh", "verify-upgrade.sh"]
)
def test_upgrade_scripts_have_valid_shell_syntax(script):
    result = subprocess.run(
        ["bash", "-n", str(SCRIPTS / script)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_upgrade_does_not_pull_or_load_pilot_data_by_default():
    source = (SCRIPTS / "upgrade.sh").read_text(encoding="utf-8")

    assert "git pull" not in source
    assert "seed-pilot.sh" not in source
    assert "backup.sh" in source
    assert "--skip-backup" not in source

    seed_source = (SCRIPTS / "seed.sh").read_text(encoding="utf-8")
    assert "113_pilot_organization.sql" not in seed_source


def test_reference_only_seed_mode_skips_schema_bootstrap():
    source = (SCRIPTS / "seed.sh").read_text(encoding="utf-8")

    assert "--reference-only" in source
    assert 'if [ "$REFERENCE_ONLY" = "false" ]; then' in source
    assert "services.migration migrate --schemas-only" in source


def test_upgrade_docs_define_maintenance_window_and_manual_rollback():
    source = (PROJECT_ROOT / "docs" / "upgrades.md").read_text(encoding="utf-8")

    assert "maintenance window" in source
    assert "Rollback is never automatic" in source
    assert "scripts/rollback.sh --checkpoint" in source


def test_verify_backup_accepts_valid_manifest(tmp_path):
    artifact = tmp_path / "artifact.enc"
    artifact.write_bytes(b"test backup")
    manifest = {
        "backup_id": "test-checkpoint",
        "files": [{
            "path": artifact.name,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "size": artifact.stat().st_size,
        }],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [str(SCRIPTS / "verify-backup.sh"), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_verify_backup_rejects_tampered_artifact(tmp_path):
    artifact = tmp_path / "artifact.enc"
    artifact.write_bytes(b"original")
    manifest = {
        "backup_id": "test-checkpoint",
        "files": [{
            "path": artifact.name,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "size": artifact.stat().st_size,
        }],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    artifact.write_bytes(b"tampered")

    result = subprocess.run(
        [str(SCRIPTS / "verify-backup.sh"), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Checksum mismatch" in result.stderr


def test_rollback_requires_explicit_confirmation(tmp_path):
    result = subprocess.run(
        [str(SCRIPTS / "rollback.sh"), "--checkpoint", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--confirm" in result.stderr
