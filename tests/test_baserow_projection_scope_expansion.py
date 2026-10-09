"""Regression tests for the owner-approved Baserow projection scope expansion."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.baserow_reconciliation_projection as projection_module
from scripts.baserow_reconciliation_apply import validate_apply_plan

from scripts.baserow_reconciliation_projection import (
    build_projection,
    load_allowlist,
    validate_allowlist,
)


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "docs" / "phase1-baserow-projection-allowlist.json"


class BaserowProjectionScopeExpansionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._row_quarantine_patch = patch.object(projection_module, "ROW_QUARANTINE_OVERRIDES", {})
        self._row_quarantine_patch.start()
        self.addCleanup(self._row_quarantine_patch.stop)

    def _validator_fixture(self, allowlist: dict) -> tuple[dict, dict, str]:
        allowlist = copy.deepcopy(allowlist)
        included_targets = {"location", "farm", "plot", "farm_task", "farm_activity", "expense_event"}
        allowlist["target_tables"] = [
            spec for spec in allowlist["target_tables"] if spec["target_table"] in included_targets
        ]
        allowlist["relationship_tables"] = []

        source_field_info = {
            "317635": {
                "2305684": ("Municipality", "text", None),
                "2305685": ("Description", "long_text", None),
                "3255476": ("Province", "text", None),
            },
            "305805": {
                "2202756": ("Title", "text", None),
                "2202757": ("Farm Description", "long_text", None),
                "2305728": ("Land Size", "number", None),
                "2307563": ("Project Location", "link_row", "317635"),
                "2305092": ("Expense Links", "link_row", "317575"),
                "2202768": ("Farm Individual Tasks", "link_row", "305801"),
                "2350183": ("KKN-GEN-F001", "link_row", "322673"),
                "3136781": ("Plot of Land", "link_row", "410138"),
            },
            "410138": {
                "3136385": ("Name", "text", None),
                "3136386": ("Description", "long_text", None),
                "3136681": ("Size of Plot", "number", None),
                "3136780": ("Kokonut Farms", "link_row", "305805"),
            },
            "305801": {
                "2202698": ("Title", "text", None),
                "2202699": ("Start", "date", None),
                "2202701": ("Duration in days", "number", None),
                "2202703": ("Project", "link_row", "305805"),
                "2202708": ("Actual end date", "date", None),
                "2202712": ("Category", "single_select", None),
                "3143320": ("Daily Activity Report", "link_row", "322673"),
                "2330116": ("Expense Links", "link_row", "317575"),
                "3919095": ("Description", "long_text", None),
            },
            "322673": {
                "4258323": ("Activity Name", "text", None),
                "2350133": ("Start Date", "date", None),
                "2350134": ("Actividad", "multiple_select", None),
                "2350135": ("Activity Description", "long_text", None),
                "2350182": ("Project", "link_row", "305805"),
                "3135643": ("Duration", "duration", None),
                "3143319": ("Farms Individual Tasks", "link_row", "305801"),
                "3143346": ("Plot of Land", "link_row", "410138"),
                "4258345": ("Activity End date", "date", None),
            },
            "317575": {
                "2305088": ("Expense Description", "text", None),
                "2305089": ("Expense Notes", "long_text", None),
                "2305091": ("Farm", "link_row", "305805"),
                "2330113": ("Expense Date", "date", None),
                "2330114": ("Category", "single_select", None),
                "2330115": ("Task", "link_row", "305801"),
                "2356443": ("Amount", "number", None),
                "3932281": ("Exchange Rate", "number", None),
                "4244464": ("Payment State", "single_select", None),
                "4261434": ("People Count", "number", None),
            },
        }
        table_names = {
            "317635": "Locations",
            "305805": "Kokonut Farms",
            "410138": "Land Lots",
            "305801": "Kokonut Farm Tasks",
            "322673": "F001 — Activity Report",
            "317575": "Synthetic Expense Records",
        }
        task_labels = [
            "Agricultural Work",
            "Components & Materials",
            "Construction",
            "Equipment",
            "Infrastructure",
            "Operations",
            "Sustainability",
        ]
        expense_spec = next(spec for spec in allowlist["target_tables"] if spec["target_table"] == "expense_event")
        category_rule = expense_spec["fields"]["2330114"]
        labor_option_ids = sorted(category_rule["option_map"], key=int)
        source_labor_label = category_rule.get("source_label", "labor")
        synthetic_nonlabor_option_id = max(int(option_id) for option_id in labor_option_ids) + 1
        activity_option_ids = [
            "1775855", "1775856", "1775857", "1775858", "1791551", "1811741",
            "2144652", "2144653", "2144654", "2144655", "2357582", "2367695",
            "2381925", "2381926", "2427447", "6259982",
        ]
        tables = []
        for table_id, fields in source_field_info.items():
            serialized_fields = []
            for field_id, (name, field_type, linked_table_id) in fields.items():
                field = {"id": int(field_id), "name": name, "type": field_type}
                if linked_table_id is not None:
                    field["link_row_table_id"] = int(linked_table_id)
                if field_id == "2202712":
                    field["select_options"] = [
                        {"id": 9000 + index, "value": label}
                        for index, label in enumerate(task_labels)
                    ]
                elif field_id == "2330114":
                    field["select_options"] = [
                        {"id": int(option_id), "value": source_labor_label}
                        for option_id in labor_option_ids
                    ] + [{"id": synthetic_nonlabor_option_id, "value": "synthetic non-labor"}]
                elif field_id == "2350134":
                    field["select_options"] = [
                        {"id": int(option_id), "value": f"Synthetic option {index + 1}"}
                        for index, option_id in enumerate(activity_option_ids)
                    ]
                elif field_id == "4244464":
                    field["select_options"] = [
                        {"id": option_id, "value": f"Synthetic payment state {index + 1}"}
                        for index, option_id in enumerate((3234299, 3234300, 3234301, 3234429, 3236127))
                    ]
                serialized_fields.append(field)
            tables.append(
                {"id": int(table_id), "name": table_names[table_id], "fields": serialized_fields, "rows": []}
            )

        rules_by_source: dict[str, dict[str, dict[str, str]]] = {}
        for spec in allowlist["target_tables"]:
            table_id = str(spec["source_table_id"])
            for field_id, rule in spec["fields"].items():
                target = f"{spec['target_table']}.{rule['target_column']}"
                if field_id == "2350134":
                    target += "; farm_activity.activity_type_source_options"
                elif field_id == "3143346":
                    target += "; farm_activity_plot(activity_id, plot_id)"
                elif field_id == "2202712":
                    target += "; farm_task.metadata.baserow_legacy.category_label"
                elif field_id == "3932281":
                    target = "expense_event.source_raw.baserow_legacy.usd_dop_rate"
                rules_by_source.setdefault(table_id, {})[field_id] = {
                    "target": target,
                    "disposition": rule["source_disposition"],
                }
        for check in allowlist.get("relationship_checks", []):
            target = f"{check['source_entity_target']}.{check['source_target_column']}"
            for table_id, field_id in (
                (str(check["source_table_id"]), str(check["source_field_id"])),
                (str(check["reciprocal_table_id"]), str(check["reciprocal_field_id"])),
            ):
                source_rules = rules_by_source.setdefault(table_id, {})
                existing = source_rules.get(field_id)
                if existing is None:
                    source_rules[field_id] = {"target": target, "disposition": "RELATIONSHIP"}
                elif target not in existing["target"]:
                    existing["target"] += f"; {target}"

        crosswalk_lines = ["# Synthetic crosswalk fixture", ""]
        for table_id, rules in rules_by_source.items():
            field_info = source_field_info[table_id]
            crosswalk_lines.extend(
                [
                    f"### {table_names[table_id]} (table ID `{table_id}`; {len(rules)} fields)",
                    "",
                    "| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule |",
                    "|---|---|---|---|---|",
                ]
            )
            for field_id, rule in rules.items():
                name, field_type, linked_table_id = field_info[field_id]
                link_label = f"; linked table `{linked_table_id}`" if linked_table_id else ""
                crosswalk_lines.append(
                    f"| `{name}` (`{field_id}`) | `{field_type}`{link_label} | `{rule['target']}` | "
                    f"`{rule['disposition']}` | Synthetic fixture. |"
                )
            crosswalk_lines.append("")
        return allowlist, {"id": 115056, "tables": tables}, "\n".join(crosswalk_lines)

    def test_activity_and_required_task_support_project_only_referenced_tasks(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        allowlist, export, crosswalk = self._validator_fixture(allowlist)
        tables = {str(table["id"]): table for table in export["tables"]}
        tables["317635"]["rows"] = [
            {"id": 10, "field_2305684": "Fixture Location", "field_2305685": None, "field_3255476": "Fixture Region"}
        ]
        tables["305805"]["rows"] = [
            {
                "id": 20,
                "field_2202756": "Fixture Farm",
                "field_2202757": None,
                "field_2305728": 1000,
                "field_2307563": [10],
                "field_2202768": [60, 61],
                "field_2350183": [70],
                "field_3136781": [30],
            }
        ]
        tables["410138"]["rows"] = [
            {
                "id": 30,
                "field_3136385": "Fixture Plot",
                "field_3136386": None,
                "field_3136681": 100,
                "field_3136780": [20],
            }
        ]
        tables["305801"]["rows"] = [
            {
                "id": 60,
                "field_2202698": "Synthetic support task",
                "field_2202699": "2026-09-01",
                "field_2202701": 3,
                "field_2202703": [20],
                "field_2202708": "2026-09-10",
                "field_2202712": 9000,
                "field_3143320": [70],
                "field_3919095": "Synthetic task description",
            },
            {
                "id": 61,
                "field_2202698": "Unreferenced synthetic task",
                "field_2202703": [20],
                "field_3143320": [],
            },
        ]
        tables["322673"]["rows"] = [
            {
                "id": 70,
                "field_4258323": "Synthetic activity name",
                "field_2350133": "2026-09-05",
                "field_2350134": [1775855, 1811741],
                "field_2350135": "Synthetic activity description",
                "field_2350182": [20],
                "field_3135643": 3600,
                "field_3143319": [60],
                "field_3143346": [30],
                "field_4258345": "2026-09-06",
            }
        ]

        validate_allowlist(export, allowlist, crosswalk)
        result = build_projection(export, allowlist)
        task_rows = result["rows_by_target"]["farm_task"]
        activity_rows = result["rows_by_target"]["farm_activity"]
        self.assertEqual(len(activity_rows), 1, json.dumps(result["report"]["tables"]))
        task = task_rows[0]
        activity = activity_rows[0]

        self.assertEqual(len(task_rows), 1)
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["priority"], "medium")
        self.assertEqual(task["category"], "other")
        self.assertEqual(task["duration_days"], 3)
        self.assertEqual(task["metadata"], {"baserow_legacy": {"category_label": "Agricultural Work"}})
        self.assertEqual(task["location_id"], result["rows_by_target"]["farm"][0]["location_id"])
        self.assertEqual(activity["activity_type"], "Synthetic option 1")
        self.assertEqual(
            activity["activity_type_source_options"],
            [
                {"option_id": 1775855, "label": "Synthetic option 1"},
                {"option_id": 1811741, "label": "Synthetic option 6"},
            ],
        )
        self.assertEqual(activity["farm_task_id"], task["id"])
        self.assertEqual(activity["plot_id"], result["rows_by_target"]["plot"][0]["id"])
        self.assertEqual(activity["location_id"], task["location_id"])
        self.assertEqual(activity["activity_date"], "2026-09-05")
        self.assertEqual(activity["activity_end_date"], "2026-09-06")
        self.assertEqual(activity["duration_minutes"], 60)
        self.assertEqual(activity["notes"], "Activity Name: Synthetic activity name")
        self.assertEqual(activity["description"], "Synthetic activity description")
        self.assertEqual(activity["status"], "draft")
        task_report = next(item for item in result["report"]["tables"] if item["target_table"] == "farm_task")
        self.assertEqual(task_report["filtered_rows"], 1)
        self.assertNotIn("Synthetic activity name", json.dumps(result["report"]))

    def test_blank_f001_activity_type_is_quarantined_without_fallback(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        allowlist, export, crosswalk = self._validator_fixture(allowlist)
        tables = {str(table["id"]): table for table in export["tables"]}
        tables["317635"]["rows"] = [{"id": 10, "field_2305684": "Fixture Location"}]
        tables["305805"]["rows"] = [
            {"id": 20, "field_2202756": "Fixture Farm", "field_2307563": [10]}
        ]
        tables["322673"]["rows"] = [
            {"id": 70, "field_2350133": "2026-09-05", "field_2350134": [], "field_2350182": [20]}
        ]

        validate_allowlist(export, allowlist, crosswalk)
        result = build_projection(export, allowlist)

        self.assertEqual(result["rows_by_target"]["farm_activity"], [])
        activity_report = next(
            item for item in result["report"]["tables"] if item["target_table"] == "farm_activity"
        )
        self.assertEqual(activity_report["quarantine_reasons"], {"missing_required_activity_type": 1})

    def test_expanded_target_schema_matches_crosswalk_and_typed_sources(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        allowlist, export, crosswalk = self._validator_fixture(allowlist)

        validate_allowlist(export, allowlist, crosswalk)

    def test_allowlist_covers_f001_and_only_directly_required_task_and_edge_scope(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        specs = {str(spec["source_table_id"]): spec for spec in allowlist["target_tables"]}

        self.assertEqual(specs["322673"]["target_table"], "farm_activity")
        self.assertEqual(specs["305801"]["target_table"], "farm_task")
        self.assertEqual(specs["305801"]["row_filter"]["kind"], "linked_from_any")
        self.assertEqual(
            {
                (str(link["source_table_id"]), str(link["source_field_id"]))
                for link in specs["305801"]["row_filter"]["links"]
            },
            {("322673", "3143319"), ("317575", "2330115")},
        )
        self.assertEqual(specs["305801"]["constants"]["status"], "pending")
        self.assertEqual(specs["305801"]["constants"]["priority"], "medium")
        self.assertNotIn("2350178", specs["322673"]["fields"])

        relations = {
            (
                str(item["source_table_id"]),
                str(item["source_field_id"]),
                item["target_table"],
            )
            for item in allowlist["relationship_tables"]
        }
        self.assertIn(("322673", "3143346", "farm_activity_plot"), relations)
        self.assertIn(("322673", "4270927", "farm_activity_output_activity"), relations)
        self.assertEqual(
            specs["534165"]["row_filter"]["kind"],
            "linked_from_any",
        )
        self.assertEqual(
            {
                (str(link["source_table_id"]), str(link["source_field_id"]))
                for link in specs["534165"]["row_filter"]["links"]
            },
            {("322673", "4270927"), ("534174", "4258786")},
        )

    def test_only_labor_expenses_project_and_excluded_expenses_do_not_pull_task_support(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        allowlist, export, crosswalk = self._validator_fixture(allowlist)
        specs = {str(spec["source_table_id"]): spec for spec in allowlist["target_tables"]}
        self.assertIn("317575", specs, "the approved expense target is missing from the allow-list")
        labor_option_ids = sorted(specs["317575"]["fields"]["2330114"]["option_map"], key=int)
        labor_option_id = int(labor_option_ids[0])
        nonlabor_option_id = max(int(option_id) for option_id in labor_option_ids) + 1
        lowercase_option_id = nonlabor_option_id + 1

        tables = {str(table["id"]): table for table in export["tables"]}
        category_field = next(field for field in tables["317575"]["fields"] if str(field["id"]) == "2330114")
        category_field["select_options"].append({"id": lowercase_option_id, "value": "labor"})
        tables["317635"]["rows"] = [
            {"id": 10, "field_2305684": "Synthetic Location", "field_2305685": None, "field_3255476": "Synthetic Region"}
        ]
        tables["305805"]["rows"] = [
            {
                "id": 20,
                "field_2202756": "Synthetic Farm",
                "field_2202757": None,
                "field_2305728": 1000,
                "field_2307563": [10],
                "field_2305092": [100, 101, 102, 103],
                "field_2202768": [60, 61, 62, 63],
                "field_2350183": [70],
                "field_3136781": [],
            }
        ]
        tables["410138"]["rows"] = []
        tables["305801"]["rows"] = [
            {
                "id": 60,
                "field_2202698": "Synthetic support task",
                "field_2202699": "2026-09-01",
                "field_2202701": 3,
                "field_2202703": [20],
                "field_2202708": None,
                "field_2202712": 9000,
                "field_3143320": [70],
                "field_2330116": [100],
                "field_3919095": None,
            },
            {
                "id": 61,
                "field_2202698": "Held expense task one",
                "field_2202703": [20],
                "field_3143320": [],
                "field_2330116": [101],
            },
            {
                "id": 62,
                "field_2202698": "Held expense task two",
                "field_2202703": [20],
                "field_3143320": [],
                "field_2330116": [102],
            },
            {
                "id": 63,
                "field_2202698": "Held lowercase-category task",
                "field_2202703": [20],
                "field_3143320": [],
                "field_2330116": [103],
            },
        ]
        tables["322673"]["rows"] = [
            {
                "id": 70,
                "field_4258323": "Synthetic activity name",
                "field_2350133": "2026-09-05",
                "field_2350134": [1775855],
                "field_2350135": "Synthetic activity description",
                "field_2350182": [20],
                "field_3135643": 3600,
                "field_3143319": [60],
                "field_3143346": [],
                "field_4258345": None,
            }
        ]
        tables["317575"]["rows"] = [
            {
                "id": 100,
                "field_2305088": "Synthetic expense description",
                "field_2305089": "Synthetic expense note",
                "field_2305091": [20],
                "field_2330113": "2026-09-07",
                "field_2330114": labor_option_id,
                "field_2330115": [60],
                "field_2356443": 42.50,
                "field_3932281": 1.25,
                "field_4244464": 3234301,
                "field_4261434": 3,
            },
            {
                "id": 101,
                "field_2305088": "Held non-labor expense",
                "field_2305091": [20],
                "field_2330113": "2026-09-08",
                "field_2330114": nonlabor_option_id,
                "field_2330115": [61],
                "field_2356443": 50.00,
                "field_4244464": 3234300,
                "field_4261434": 1,
            },
            {
                "id": 102,
                "field_2305088": "Held blank-category expense",
                "field_2305091": [20],
                "field_2330113": "2026-09-09",
                "field_2330114": None,
                "field_2330115": [62],
                "field_2356443": 60.00,
                "field_4244464": 3234301,
                "field_4261434": 4,
            },
            {
                "id": 103,
                "field_2305088": "Held lowercase-category expense",
                "field_2305091": [20],
                "field_2330113": "2026-09-10",
                "field_2330114": lowercase_option_id,
                "field_2330115": [63],
                "field_2356443": 55.00,
                "field_4244464": 3234301,
                "field_4261434": 2,
            },
        ]

        validate_allowlist(export, allowlist, crosswalk)
        result = build_projection(export, allowlist)
        apply_targets = validate_apply_plan(result["rows_by_target"], allowlist)

        expenses = result["rows_by_target"]["expense_event"]
        self.assertIn("expense_event", apply_targets)
        tasks = result["rows_by_target"]["farm_task"]
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0]["category"], "labor")
        self.assertEqual(expenses[0]["payment_status"], "Synthetic payment state 3")
        self.assertEqual(expenses[0]["people_impacted_count"], 3)
        self.assertEqual(expenses[0]["currency"], "DOP")
        self.assertEqual(expenses[0]["status"], "draft")
        self.assertEqual(expenses[0]["source_raw"], {"baserow_legacy": {"usd_dop_rate": 1.25}})
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_name"], "Synthetic support task")
        expense_report = next(item for item in result["report"]["tables"] if item["target_table"] == "expense_event")
        self.assertEqual(expense_report["projected_rows"], 1)
        self.assertEqual(expense_report["quarantined_rows"], 3)
        self.assertEqual(expense_report["quarantine_reasons"], {
            "missing_required_value": 1,
            "unmapped_single_select_option": 2,
        })
        task_report = next(item for item in result["report"]["tables"] if item["target_table"] == "farm_task")
        self.assertEqual(task_report["filtered_rows"], 3)
        self.assertNotIn("Synthetic expense description", json.dumps(result["report"]))
        self.assertNotIn("Held non-labor expense", json.dumps(result["report"]))
        self.assertNotIn("Held lowercase-category expense", json.dumps(result["report"]))

    def test_partial_category_option_ids_follow_exact_source_labor_labels(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        expense_spec = next(spec for spec in allowlist["target_tables"] if spec["target_table"] == "expense_event")
        current_ids = [int(option_id) for option_id in expense_spec["fields"]["2330114"]["option_map"]]
        alternate_labor_option_id = str(max(current_ids) + 100)
        expense_spec["fields"]["2330114"]["option_map"] = {alternate_labor_option_id: "labor"}
        allowlist, export, crosswalk = self._validator_fixture(allowlist)

        validate_allowlist(export, allowlist, crosswalk)

    def test_owner_approved_capitalized_category_label_maps_to_canonical_labor(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        expense_spec = next(spec for spec in allowlist["target_tables"] if spec["target_table"] == "expense_event")
        category_rule = expense_spec["fields"]["2330114"]
        category_rule["source_label"] = "Labor"
        category_rule["owner_decision_ref"] = "exact-Labor-to-labor-2026-10-08"
        allowlist, export, crosswalk = self._validator_fixture(allowlist)

        validate_allowlist(export, allowlist, crosswalk)


    def test_source_raw_target_accepts_its_documented_provenance_annotation(self) -> None:
        allowlist = load_allowlist(ALLOWLIST_PATH)
        allowlist, export, crosswalk = self._validator_fixture(allowlist)
        target = "`expense_event.source_raw.baserow_legacy.usd_dop_rate`"
        annotated = crosswalk.replace(
            f"| {target} | `PROVENANCE_ONLY` |",
            f"| {target} (source-record provenance only) | `PROVENANCE_ONLY` |",
            1,
        )
        self.assertNotEqual(annotated, crosswalk)

        validate_allowlist(export, allowlist, annotated)


if __name__ == "__main__":
    unittest.main()
