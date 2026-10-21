"""The report source inventory covers the full registry without importing services."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report_generator_inventory import build_inventory, main  # noqa: E402


def test_inventory_resolves_every_registered_callable_to_source_and_inputs():
    inventory = build_inventory()
    reports = inventory["reports"]

    assert inventory["summary"] == {
        "registered_report_types": 94,
        "source_modules": 15,
        "with_location_id_parameter": 94,
        "with_period_start_or_end_parameter": 93,
    }
    assert len({report["report_type"] for report in reports}) == 94
    assert [report["report_type"] for report in reports] == sorted(
        report["report_type"] for report in reports
    )
    for report in reports:
        assert (ROOT / report["source_file"]).is_file()
        assert report["source_line"] > 0
        assert "location_id" in report["parameters"]
        assert report["source_module"].replace(".", "/") in report["source_file"]


def test_inventory_output_and_freshness_check_are_deterministic(tmp_path):
    output = tmp_path / "report-inventory.json"

    assert main(["--output", str(output)]) == 0
    first = output.read_text(encoding="utf-8")
    assert main(["--check", str(output)]) == 0
    assert json.loads(first)["summary"]["registered_report_types"] == 94

    output.write_text(first + " ", encoding="utf-8")
    assert main(["--check", str(output)]) == 1


def _static_set_assignment(tree: ast.Module, name: str) -> frozenset[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            if isinstance(node.value.func, ast.Name) and node.value.func.id == "frozenset":
                return frozenset(ast.literal_eval(node.value.args[0]))
    raise AssertionError(f"Could not statically read {name} from the report CLI")


def test_locationless_report_queries_have_explicit_network_or_multi_location_policy():
    direct_scope = json.loads((ROOT / "docs/refactor/report-generator-query-scope-inventory.json").read_text())
    helper_scope = json.loads((ROOT / "docs/refactor/report-generator-helper-scope-inventory.json").read_text())
    cli_tree = ast.parse((ROOT / "services/export/report_generator.py").read_text())
    network_only = _static_set_assignment(cli_tree, "NETWORK_SCOPE_ONLY_REPORTS")
    multi_location = _static_set_assignment(cli_tree, "MULTI_LOCATION_REPORTS")

    direct_without_location = {
        report["report_type"]
        for report in direct_scope["reports"]
        if report["classification"] == "no_bound_location_scope_visible"
    }
    helper_without_location = {
        report["report_type"]
        for report in helper_scope["reports"]
        if report["classification"] == "no_location_scope_signal_in_resolved_helper_queries"
    }

    assert direct_without_location - network_only == {"business_plan"}
    assert "business_plan" in multi_location
    assert helper_without_location - network_only == {
        "algorithmic_redistribution",
        "anti_capture_governance",
        "business_model_canvas",
        "redistribution_policy",
        "state_of_kokonut",
    }
