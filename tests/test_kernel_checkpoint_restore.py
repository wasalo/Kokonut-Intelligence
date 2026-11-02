"""Regression coverage for current-head recovery acceptance."""

from __future__ import annotations

import runpy
from pathlib import Path

from services.migration.cli import _discover_files

ROOT = Path(__file__).resolve().parents[1]
RECOVERY_CHECK = runpy.run_path(
    str(ROOT / "scripts" / "check-kernel-checkpoint-restore-disposable.py"),
    run_name="kernel_checkpoint_restore_test_module",
)


def test_expected_checkpoint_head_tracks_ordered_repository_schema_files() -> None:
    migrations = _discover_files(include_seeds=False)
    expected_count, latest_id = RECOVERY_CHECK["expected_schema_head"]()

    assert expected_count == len(migrations)
    assert latest_id == migrations[-1]["id"]


def test_checkpoint_fingerprint_parser_preserves_schema_identity() -> None:
    fingerprint = RECOVERY_CHECK["migration_fingerprint"](
        "653|0123456789abcdef0123456789abcdef|schema:662_example.sql"
    )

    assert fingerprint == {
        "applied": 653,
        "migration_digest_md5": "0123456789abcdef0123456789abcdef",
        "latest": "schema:662_example.sql",
    }
