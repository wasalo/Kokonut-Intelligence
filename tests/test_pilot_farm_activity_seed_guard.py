"""Regression checks for pilot seeds under migration 404's write guard."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_pilot_farm_activity_rows_insert_final_immutable_lineage():
    seed = (REPOSITORY_ROOT / "schemas/seeds/002_pilot_operations.sql").read_text()

    assert (
        "INSERT INTO farm_activity (id, location_id, crop_cycle_id, activity_type, "
        "activity_date, description, status, schema_version, source_system, source_id, source_raw) VALUES"
        in seed
    )
    activity_rows = re.findall(
        r"^\('(?P<id>b0000000-0000-0000-0000-0000000000\d+)'[^\n]+$",
        seed,
        re.MULTILINE,
    )
    assert len(activity_rows) == 30
    for activity_id in activity_rows:
        assert f"'operations-v1', 'pilot_seed', 'farm_activity:{activity_id}'" in seed
        assert (
            f"'record_type', 'farm_activity', 'record_id', '{activity_id}')"
            in seed
        )
    assert "UPDATE farm_activity" not in seed


def test_adelphi_alignment_does_not_rewrite_guarded_farm_activity():
    alignment = (REPOSITORY_ROOT / "schemas/seeds/024_adelphi_alignment.sql").read_text()

    assert "UPDATE farm_activity" not in alignment
