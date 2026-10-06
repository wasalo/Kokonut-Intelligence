"""Tests for the allowlisted, deterministic Baserow projection rehearsal."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.baserow_reconciliation_projection import (
    ProjectionError,
    build_projection,
    build_transaction_sql,
    load_allowlist,
    validate_allowlist,
    validate_scratch_container,
    validate_tmpfs_filesystem_output,
    validate_scratch_migration_counts,
)


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "docs" / "phase1-baserow-projection-allowlist.json"


class BaserowProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.allowlist = load_allowlist(ALLOWLIST_PATH)
        self.export = {
            "id": 115056,
            "tables": [
                {
                    "id": 317635,
                    "name": "Locations",
                    "fields": [
                        {"id": 2305684, "name": "Municipality", "type": "text"},
                        {"id": 2305685, "name": "Description", "type": "long_text"},
                        {"id": 3255476, "name": "Province", "type": "text"},
                    ],
                    "rows": [
                        {
                            "id": 10,
                            "field_2305684": "Monte Plata",
                            "field_2305685": "Fixture-only location description",
                            "field_3255476": "Monte Plata",
                        }
                    ],
                },
                {
                    "id": 305805,
                    "name": "Kokonut Farms",
                    "fields": [
                        {"id": 2202756, "name": "Title", "type": "text"},
                        {"id": 2202757, "name": "Farm Description", "type": "long_text"},
                        {"id": 2305728, "name": "Land Size", "type": "number"},
                        {"id": 2307563, "name": "Project Location", "type": "link_row", "link_row_table_id": 317635},
                    ],
                    "rows": [
                        {
                            "id": 20,
                            "field_2202756": "Fixture Farm",
                            "field_2202757": "Fixture-only farm description",
                            "field_2305728": 1250.5,
                            "field_2307563": [10],
                        }
                    ],
                },
                {
                    "id": 410138,
                    "name": "Land Lots",
                    "fields": [
                        {"id": 3136385, "name": "Name", "type": "text"},
                        {"id": 3136386, "name": "Description", "type": "long_text"},
                        {"id": 3136681, "name": "Size of Plot", "type": "number"},
                        {"id": 3136780, "name": "Kokonut Farms", "type": "link_row", "link_row_table_id": 305805},
                    ],
                    "rows": [
                        {
                            "id": 30,
                            "field_3136385": "Fixture Plot",
                            "field_3136386": "Fixture-only plot description",
                            "field_3136681": 300.25,
                            "field_3136780": [20],
                        }
                    ],
                },
                {
                    "id": 317629,
                    "name": "Species",
                    "fields": [
                        {"id": 2305620, "name": "Name", "type": "text"},
                        {"id": 2305621, "name": "Scientific Name", "type": "text"},
                        {"id": 4034419, "name": "Weeks to Maturity", "type": "number"},
                        {
                            "id": 4034223,
                            "name": "Type",
                            "type": "single_select",
                            "select_options": [
                                {"id": 3110859, "value": "Fruit"},
                                {"id": 3110860, "value": "Vegetable"},
                                {"id": 3110861, "value": "Ornamental"},
                                {"id": 3110862, "value": "Utility"},
                            ],
                        },
                    ],
                    "rows": [
                        {
                            "id": 40,
                            "field_2305620": "Fixture Crop",
                            "field_2305621": "Fixture species",
                            "field_4034419": 4,
                            "field_4034223": 3110859,
                        }
                    ],
                },
                {
                    "id": 534165,
                    "name": "F003 Activity Outputs",
                    "fields": [
                        {"id": 4258577, "name": "Deliverable Name", "type": "text"},
                        {"id": 4258578, "name": "Description", "type": "long_text"},
                        {"id": 4258787, "name": "F004 - Activity Metrics", "type": "link_row", "link_row_table_id": 534174},
                    ],
                    "rows": [
                        {
                            "id": 100,
                            "field_4258577": "Synthetic output A",
                            "field_4258578": "Synthetic output description A",
                            "field_4258787": [50, 51],
                        },
                        {
                            "id": 101,
                            "field_4258577": "Unreferenced synthetic output",
                            "field_4258578": None,
                            "field_4258787": [],
                        },
                    ],
                },
                {
                    "id": 534174,
                    "name": "F004 Activity Metrics",
                    "fields": [
                        {"id": 4258662, "name": "Indicator", "type": "text"},
                        {"id": 4258663, "name": "Value", "type": "number"},
                        {"id": 4258786, "name": "F003 - Activity Outputs", "type": "link_row", "link_row_table_id": 534165},
                        {"id": 4453489, "name": "Description", "type": "long_text"},
                    ],
                    "rows": [
                        {
                            "id": 50,
                            "field_4258662": "Synthetic indicator one",
                            "field_4258663": 1.25,
                            "field_4258786": [100],
                            "field_4453489": "Synthetic report one",
                        },
                        {
                            "id": 51,
                            "field_4258662": "Synthetic indicator two",
                            "field_4258663": 2.5,
                            "field_4258786": [100],
                            "field_4453489": "Synthetic report two",
                        },
                    ],
                },
            ],
        }

    def crosswalk_fixture(self) -> str:
        tables = {str(table["id"]): table for table in self.export["tables"]}
        rules_by_source: dict[str, dict[str, dict[str, str]]] = {}
        for spec in self.allowlist["target_tables"]:
            source_table_id = str(spec["source_table_id"])
            rules_by_source[source_table_id] = {
                str(field_id): {
                    "target": f"{spec['target_table']}.{rule['target_column']}",
                    "disposition": rule["source_disposition"],
                }
                for field_id, rule in spec["fields"].items()
            }
        for relation in self.allowlist.get("relationship_tables", []):
            source_table_id = str(relation["source_table_id"])
            related_table_id = str(relation["reciprocal_table_id"])
            target = f"{relation['target_table']} (reported_metric_id, output_id)"
            rules_by_source.setdefault(source_table_id, {})[str(relation["source_field_id"])] = {
                "target": target,
                "disposition": relation["source_disposition"],
            }
            rules_by_source.setdefault(related_table_id, {})[str(relation["reciprocal_field_id"])] = {
                "target": target,
                "disposition": "RELATIONSHIP",
            }
        lines = ["# Synthetic crosswalk fixture", ""]
        for source_table_id, rules in rules_by_source.items():
            source_table = tables[source_table_id]
            fields = {str(field["id"]): field for field in source_table["fields"]}
            lines.extend([
                f"### {source_table['name']} (table ID `{source_table_id}`; {len(rules)} fields)",
                "",
                "| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule |",
                "|---|---|---|---|---|",
            ])
            for field_id, rule in rules.items():
                field = fields[str(field_id)]
                lines.append(
                    f"| `{field['name']}` (`{field_id}`) | `{field['type']}` | "
                    f"`{rule['target']}` | `{rule['disposition']}` | Fixture mapping. |"
                )
            lines.append("")
        return "\n".join(lines)

    def relationship_test_allowlist(self) -> dict:
        """Add synthetic parent/child mappings to exercise link quarantine logic."""
        allowlist = copy.deepcopy(self.allowlist)
        allowlist["target_tables"] = [
            spec for spec in allowlist["target_tables"]
            if spec["target_table"] not in {"farm", "plot"}
        ]
        allowlist["target_tables"].extend([
            {
                "source_table_id": "305805",
                "target_table": "farm",
                "identity_columns": ["name", "location_id"],
                "required_source_fields": ["2202756", "2307563"],
                "generated_columns": {
                    "id": "uuid5_source_identity",
                    "slug": "slugify_name_plus_source_identity",
                },
                "constants": {"area_unit": "square_meters"},
                "fields": {
                    "2202756": {"target_column": "name", "source_disposition": "CANDIDATE", "transform": "required_text"},
                    "2202757": {"target_column": "description", "source_disposition": "CANDIDATE", "transform": "optional_text"},
                    "2305728": {"target_column": "total_area", "source_disposition": "CANDIDATE", "transform": "optional_nonnegative_numeric_12_4"},
                    "2307563": {"target_column": "location_id", "source_disposition": "RELATIONSHIP", "transform": "required_single_link", "linked_table_id": "317635"},
                },
            },
            {
                "source_table_id": "410138",
                "target_table": "plot",
                "identity_columns": ["name", "farm_id"],
                "required_source_fields": ["3136385", "3136780"],
                "generated_columns": {
                    "id": "uuid5_source_identity",
                    "slug": "slugify_name_plus_source_identity",
                },
                "constants": {"area_unit": "square_meters"},
                "fields": {
                    "3136385": {"target_column": "name", "source_disposition": "CANDIDATE", "transform": "required_text"},
                    "3136386": {"target_column": "description", "source_disposition": "CANDIDATE", "transform": "optional_text"},
                    "3136681": {"target_column": "area", "source_disposition": "CANDIDATE", "transform": "optional_nonnegative_numeric_12_4"},
                    "3136780": {"target_column": "farm_id", "source_disposition": "RELATIONSHIP", "transform": "required_single_link", "linked_table_id": "305805"},
                },
            },
        ])
        return allowlist

    def test_transaction_sql_escapes_text_and_always_rolls_back(self) -> None:
        rows = {
            "location": [{
                "id": "00000000-0000-5000-8000-000000000001",
                "name": "Farmer's field",
                "slug": "farm-src-test",
                "description": "Line one\nLine two",
                "country": "Dominican Republic",
                "region": None,
            }],
            "farm": [],
            "plot": [],
            "crop": [],
        }
        sql = build_transaction_sql(rows)

        self.assertIn('INSERT INTO "location"', sql)
        self.assertIn("SELECT 'DRYRUN|before|location|' || COUNT(*)::text FROM \"location\";", sql)
        self.assertIn("SELECT 'DRYRUN|after|location|' || COUNT(*)::text FROM \"location\";", sql)
        self.assertIn("'Farmer''s field'", sql)
        self.assertIn("BEGIN;", sql)
        self.assertIn("SET CONSTRAINTS ALL IMMEDIATE;", sql)
        self.assertIn("ROLLBACK;", sql)
        self.assertNotIn("COMMIT;", sql)
        self.assertIn("DRYRUN|during|location|", sql)
        self.assertIn("DRYRUN|after|location|", sql)

    def scratch_inspect_fixture(self):
        return {
            "Config": {
                "Image": "postgis/postgis:16-3.4",
                "Labels": {"kokonut.dry-run": "baserow-115056"},
                "Env": [
                    "POSTGRES_DB=ki21_scratch",
                    "POSTGRES_USER=postgres",
                    "POSTGRES_HOST_AUTH_METHOD=trust",
                ],
            },
            "HostConfig": {
                "NetworkMode": "none",
                "PortBindings": {},
                "Tmpfs": {"/var/lib/postgresql/data": "rw,size=512m"},
            },
            "Mounts": [{"Type": "bind", "Destination": "/scratch-schemas", "RW": False}],
            "State": {"Running": True, "Health": {"Status": "healthy"}},
        }

    def test_scratch_migration_counts_require_schema_only_bootstrap(self) -> None:
        verified = validate_scratch_migration_counts("351|0|0|351", 351)
        self.assertEqual(verified, {"schema_applied": 351, "seed_migrations": 0, "pending_or_failed": 0})
        with self.assertRaisesRegex(ProjectionError, "schema-only migrations"):
            validate_scratch_migration_counts("351|2|0|353", 351)

    def test_container_inspect_uses_tmpfs_config_without_volume_mount(self) -> None:
        validate_scratch_container(self.scratch_inspect_fixture())

    def test_tmpfs_filesystem_check_requires_real_mount(self) -> None:
        valid = (
            "Filesystem Type 1024-blocks Used Available Capacity Mounted on\n"
            "tmpfs tmpfs 524288 109872 414416 21% /var/lib/postgresql/data\n"
        )
        invalid = (
            "Filesystem Type 1024-blocks Used Available Capacity Mounted on\n"
            "/dev/sda1 ext4 524288 109872 414416 21% /var/lib/postgresql/data\n"
        )
        validate_tmpfs_filesystem_output(valid)
        with self.assertRaisesRegex(ProjectionError, "not mounted on tmpfs"):
            validate_tmpfs_filesystem_output(invalid)

    def test_rejects_nonisolated_scratch_container(self) -> None:
        inspect_data = self.scratch_inspect_fixture()
        inspect_data["HostConfig"]["PortBindings"] = {"5432/tcp": [{"HostPort": "5432"}]}
        with self.assertRaisesRegex(ProjectionError, "published ports"):
            validate_scratch_container(inspect_data)

    def test_rejects_wrong_image_even_with_dry_run_label(self) -> None:
        inspect_data = self.scratch_inspect_fixture()
        inspect_data["Config"]["Image"] = "postgres:18-alpine"
        with self.assertRaisesRegex(ProjectionError, "approved PostGIS image"):
            validate_scratch_container(inspect_data)

    def test_allowlist_must_cover_required_target_columns(self) -> None:
        changed = copy.deepcopy(self.allowlist)
        del changed["target_tables"][0]["fields"]["2305684"]
        changed["target_tables"][0]["required_source_fields"] = []
        with self.assertRaisesRegex(ProjectionError, "required target columns"):
            validate_allowlist(self.export, changed, self.crosswalk_fixture())

    def test_allowlist_transform_must_match_source_field_type(self) -> None:
        changed = copy.deepcopy(self.allowlist)
        changed["target_tables"][0]["fields"]["2305684"]["transform"] = (
            "optional_nonnegative_numeric_12_4"
        )
        with self.assertRaisesRegex(ProjectionError, "transform is incompatible with source type"):
            validate_allowlist(self.export, changed, self.crosswalk_fixture())

    def test_species_type_maps_every_source_option_id_deterministically(self) -> None:
        crop_spec = next(spec for spec in self.allowlist["target_tables"] if spec["target_table"] == "crop")
        rule = crop_spec["fields"]["4034223"]
        self.assertEqual(rule["source_disposition"], "CANDIDATE")
        self.assertEqual(rule["target_column"], "crop_category")
        self.assertEqual(rule["transform"], "single_select_option_map")
        self.assertEqual(rule["option_map"], {
            "3110859": "fruit",
            "3110860": "vegetable",
            "3110861": "ornamental",
            "3110862": "utility",
        })
        validate_allowlist(self.export, self.allowlist, self.crosswalk_fixture())
        result = build_projection(self.export, self.allowlist)
        self.assertEqual(result["rows_by_target"]["crop"][0]["crop_category"], "fruit")

    def test_species_type_unknown_option_quarantines_its_crop_row(self) -> None:
        self.export["tables"][3]["rows"][0]["field_4034223"] = 999999
        result = build_projection(self.export, self.allowlist)
        self.assertEqual(result["rows_by_target"]["crop"], [])
        crop_report = next(item for item in result["report"]["tables"] if item["target_table"] == "crop")
        self.assertEqual(crop_report["quarantine_reasons"], {"unmapped_single_select_option": 1})

    def test_species_type_option_map_must_cover_source_metadata_exactly(self) -> None:
        changed = copy.deepcopy(self.allowlist)
        crop_spec = next(spec for spec in changed["target_tables"] if spec["target_table"] == "crop")
        del crop_spec["fields"]["4034223"]["option_map"]["3110862"]
        with self.assertRaisesRegex(ProjectionError, "option map must cover every source option"):
            validate_allowlist(self.export, changed, self.crosswalk_fixture())

    def test_activity_metrics_use_reported_model_and_only_referenced_output_parents(self) -> None:
        validate_allowlist(self.export, self.allowlist, self.crosswalk_fixture())
        result = build_projection(self.export, self.allowlist)
        rows = result["rows_by_target"]
        self.assertEqual(len(rows["farm_activity_output"]), 1)
        self.assertEqual(len(rows["farm_activity_reported_metric"]), 2)
        self.assertEqual(len(rows["farm_activity_reported_metric_output"]), 2)
        output = rows["farm_activity_output"][0]
        metrics = rows["farm_activity_reported_metric"]
        self.assertEqual(output["output_name"], "Synthetic output A")
        self.assertEqual({row["reported_value"] for row in metrics}, {1.25, 2.5})
        self.assertTrue(all(row["reported_unit"] is None for row in metrics))
        self.assertTrue(all(row["period_start"] is None and row["period_end"] is None for row in metrics))
        self.assertTrue(all(row["source_system"] == "baserow" for row in metrics))
        self.assertTrue(all(edge["output_id"] == output["id"] for edge in rows["farm_activity_reported_metric_output"]))
        self.assertEqual(result["report"]["relationships"][0]["projected_edges"], 2)
        output_report = next(item for item in result["report"]["tables"] if item["target_table"] == "farm_activity_output")
        self.assertEqual(output_report["filtered_rows"], 1)
        self.assertEqual(output_report["quarantined_rows"], 0)
        self.assertNotIn("Synthetic output A", json.dumps(result["report"]))
        sql = build_transaction_sql(rows)
        self.assertIn('INSERT INTO "farm_activity_reported_metric"', sql)
        self.assertIn('INSERT INTO "farm_activity_reported_metric_output"', sql)
        self.assertIn("ROLLBACK;", sql)
        self.assertNotIn("COMMIT;", sql)

    def test_nonreciprocal_activity_metric_edge_is_quarantined_not_inserted(self) -> None:
        self.export["tables"][4]["rows"][0]["field_4258787"] = [50]
        result = build_projection(self.export, self.allowlist)
        self.assertEqual(len(result["rows_by_target"]["farm_activity_reported_metric"]), 2)
        self.assertEqual(len(result["rows_by_target"]["farm_activity_reported_metric_output"]), 1)
        relationship = result["report"]["relationships"][0]
        self.assertEqual(relationship["quarantined_edges"], 1)
        self.assertEqual(relationship["quarantine_reasons"], {"nonreciprocal_edge": 1})

    def test_output_support_filter_must_use_the_approved_metric_relationship(self) -> None:
        changed = copy.deepcopy(self.allowlist)
        output_spec = next(spec for spec in changed["target_tables"] if spec["target_table"] == "farm_activity_output")
        output_spec["row_filter"]["source_field_id"] = "3136390"
        with self.assertRaisesRegex(ProjectionError, "row filter must resolve to an approved source relationship"):
            validate_allowlist(self.export, changed, self.crosswalk_fixture())

    def test_allowlist_rejects_blocking_source_dispositions(self) -> None:
        changed = copy.deepcopy(self.allowlist)
        changed["target_tables"][0]["fields"]["2305684"]["source_disposition"] = "CONDITIONAL"
        crosswalk = self.crosswalk_fixture().replace("`CANDIDATE`", "`CONDITIONAL`", 1)
        with self.assertRaisesRegex(ProjectionError, "blocking source disposition"):
            validate_allowlist(self.export, changed, crosswalk)

    def test_allowlist_must_match_crosswalk_disposition(self) -> None:
        crosswalk = self.crosswalk_fixture()
        validate_allowlist(self.export, self.allowlist, crosswalk)
        changed = copy.deepcopy(self.allowlist)
        changed["target_tables"][0]["fields"]["2305684"]["source_disposition"] = "RELATIONSHIP"
        with self.assertRaisesRegex(ProjectionError, "disposition differs"):
            validate_allowlist(self.export, changed, crosswalk)

    def test_quarantines_ambiguous_parent_links_and_dependent_rows(self) -> None:
        self.export["tables"][1]["rows"][0]["field_2307563"] = [10, 11]
        result = build_projection(self.export, self.relationship_test_allowlist())

        self.assertEqual(len(result["rows_by_target"]["farm"]), 0)
        self.assertEqual(len(result["rows_by_target"]["plot"]), 0)
        by_table = {item["source_table_id"]: item for item in result["report"]["tables"]}
        self.assertEqual(by_table["305805"]["quarantine_reasons"], {"missing_or_ambiguous_link": 1})
        self.assertEqual(by_table["410138"]["quarantine_reasons"], {"unresolved_parent_link": 1})

    def test_quarantines_duplicate_identity_groups_and_dependents(self) -> None:
        second_location = dict(self.export["tables"][0]["rows"][0], id=11)
        self.export["tables"][0]["rows"].append(second_location)
        self.export["tables"][1]["rows"].append(
            dict(self.export["tables"][1]["rows"][0], id=21, field_2307563=[11])
        )
        result = build_projection(self.export, self.relationship_test_allowlist())

        self.assertEqual(len(result["rows_by_target"]["location"]), 0)
        self.assertEqual(len(result["rows_by_target"]["farm"]), 0)
        by_table = {item["source_table_id"]: item for item in result["report"]["tables"]}
        self.assertEqual(by_table["317635"]["quarantine_reasons"], {"duplicate_identity_candidate": 2})
        self.assertEqual(by_table["305805"]["quarantine_reasons"], {"unresolved_parent_link": 2})

    def test_blocking_maturity_field_is_excluded_from_crop_projection(self) -> None:
        self.export["tables"][3]["rows"][0]["field_4034419"] = 4
        result = build_projection(self.export, self.allowlist)

        self.assertNotIn("4034419", self.allowlist["target_tables"][1]["fields"])
        self.assertEqual(len(result["rows_by_target"]["crop"]), 1)
        self.assertIsNone(result["rows_by_target"]["crop"][0]["growing_season_days"])
        self.assertEqual(result["report"]["field_quarantines"], [])

    def test_projects_candidate_only_scope_deterministically(self) -> None:
        first = build_projection(self.export, self.allowlist)
        second = build_projection(self.export, self.allowlist)

        rows = first["rows_by_target"]
        self.assertEqual({target: len(items) for target, items in rows.items()}, {
            "location": 1,
            "farm": 1,
            "plot": 1,
            "crop": 1,
            "farm_activity_output": 1,
            "farm_activity_reported_metric": 2,
            "farm_activity_reported_metric_output": 2,
        })
        location = rows["location"][0]
        farm = rows["farm"][0]
        plot = rows["plot"][0]
        crop = rows["crop"][0]
        self.assertEqual(location["country"], "Dominican Republic")
        self.assertEqual(location["region"], "Monte Plata")
        self.assertEqual(farm["location_id"], location["id"])
        self.assertEqual(farm["area_unit"], "square_meters")
        self.assertEqual(plot["farm_id"], farm["id"])
        self.assertEqual(plot["area_unit"], "square_meters")
        self.assertIsNone(crop["growing_season_days"])
        self.assertEqual(crop["crop_category"], "fruit")
        self.assertEqual(first["projection_sha256"], second["projection_sha256"])
        self.assertNotIn("Fixture Farm", json.dumps(first["report"]))
        self.assertNotIn("Monte Plata", json.dumps(first["report"]))


if __name__ == "__main__":
    unittest.main()
