"""Tests for the offline, redacted Baserow reconciliation preflight."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.baserow_reconciliation_dry_run import DryRunError, run_dry_run


class BaserowReconciliationDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.export_path = self.root / "export.json"
        self.manifest_path = self.root / "manifest.json"
        self.crosswalk_path = self.root / "crosswalk.md"
        self.export_data = {
            "id": 115056,
            "name": "synthetic fixture",
            "tables": [
                {
                    "id": 1,
                    "name": "Source A",
                    "fields": [
                        {"id": 101, "name": "Name", "type": "text"},
                        {"id": 102, "name": "Account", "type": "number"},
                        {"id": 103, "name": "Activity", "type": "multiple_select"},
                        {
                            "id": 104,
                            "name": "Location",
                            "type": "link_row",
                            "link_row_table_id": 2,
                        },
                    ],
                    "rows": [
                        {
                            "id": 10,
                            "field_101": "PRIVATE_CANDIDATE_SENTINEL",
                            "field_102": 123456789,
                            "field_103": ["planting", "pruning"],
                            "field_104": [20],
                        },
                        {"id": 11, "field_101": None, "field_104": []},
                    ],
                },
                {
                    "id": 2,
                    "name": "Source B",
                    "fields": [{"id": 201, "name": "Label", "type": "text"}],
                    "rows": [{"id": 20, "field_201": "PRIVATE_LABEL_SENTINEL"}],
                },
            ],
        }
        self.crosswalk = """# Crosswalk test fixture

### Source A (table ID `1`; 4 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule |
|---|---|---|---|---|
| `Name` (`101`) | `text` | `farm.name` | `CANDIDATE` | Direct mapping. |
| `Account` (`102`) | `number` | — | `EXCLUDE_SENSITIVE` | Exclude. |
| `Activity` (`103`) | `multiple_select` | `farm_activity.activity_type` | `CONDITIONAL` | Review selections. |
| `Location` (`104`) | `link_row` → Source B | `farm.location_id` | `RELATIONSHIP` | Resolve by source row ID. |

### Source B (table ID `2`; 1 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule |
|---|---|---|---|---|
| `Label` (`201`) | `text` | `location.name` | `CANDIDATE` | Direct mapping. |
"""
        self.write_fixture()

    def write_fixture(self, *, dangling_target: bool = False, wrong_hash: bool = False) -> None:
        if dangling_target:
            self.export_data["tables"][0]["rows"][0]["field_104"] = [999]
        raw = json.dumps(self.export_data, sort_keys=True).encode("utf-8")
        self.export_path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        if wrong_hash:
            digest = "0" * 64
        manifest = {
            "applications": {
                "database": {
                    "items": [
                        {
                            "id": 115056,
                            "uuid": "fixture-db",
                            "files": {"schema": f"database__fixture-db_{digest}.json"},
                        }
                    ]
                }
            }
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.crosswalk_path.write_text(self.crosswalk, encoding="utf-8")

    def test_reports_redacted_counts_and_link_integrity_without_writes(self) -> None:
        report = run_dry_run(self.export_path, self.manifest_path, self.crosswalk_path)

        self.assertEqual(report["summary"]["source_tables"], 2)
        self.assertEqual(report["summary"]["source_rows"], 3)
        self.assertEqual(report["summary"]["source_fields"], 5)
        self.assertEqual(report["summary"]["candidate_nonempty_cells"], 2)
        self.assertEqual(report["summary"]["conditional_nonempty_cells"], 1)
        self.assertEqual(report["summary"]["blocking_fields_with_data"], 1)
        self.assertEqual(report["blocking_fields"][0]["disposition"], "CONDITIONAL")
        self.assertEqual(report["summary"]["link_references"], 1)
        self.assertEqual(report["summary"]["dangling_link_references"], 0)
        self.assertEqual(report["execution"]["database_connections"], 0)
        self.assertEqual(report["execution"]["target_rows_written"], 0)

        serialized = json.dumps(report)
        self.assertNotIn("PRIVATE_CANDIDATE_SENTINEL", serialized)
        self.assertNotIn("PRIVATE_LABEL_SENTINEL", serialized)
        self.assertNotIn("123456789", serialized)

    def test_rejects_stale_crosswalk_field_type(self) -> None:
        self.crosswalk_path.write_text(
            self.crosswalk.replace("| `Name` (`101`) | `text`", "| `Name` (`101`) | `number`"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(DryRunError, "crosswalk field metadata mismatch"):
            run_dry_run(self.export_path, self.manifest_path, self.crosswalk_path)

    def test_rejects_snapshot_hash_mismatch(self) -> None:
        self.write_fixture(wrong_hash=True)
        with self.assertRaisesRegex(DryRunError, "SHA-256"):
            run_dry_run(self.export_path, self.manifest_path, self.crosswalk_path)

    def test_rejects_incomplete_crosswalk_coverage(self) -> None:
        self.crosswalk_path.write_text(self.crosswalk.replace("| `Account` (`102`) | `number` | — | `EXCLUDE_SENSITIVE` | Exclude. |\n", ""), encoding="utf-8")
        with self.assertRaisesRegex(DryRunError, "crosswalk field coverage"):
            run_dry_run(self.export_path, self.manifest_path, self.crosswalk_path)

    def test_dangling_relationship_is_reported_and_blocks_readiness(self) -> None:
        self.write_fixture(dangling_target=True)
        report = run_dry_run(self.export_path, self.manifest_path, self.crosswalk_path)

        self.assertEqual(report["summary"]["dangling_link_references"], 1)
        self.assertFalse(report["summary"]["ready_for_import"])


if __name__ == "__main__":
    unittest.main()
