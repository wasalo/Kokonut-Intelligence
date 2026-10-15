"""The report source inventory covers the full registry without importing services."""

from __future__ import annotations

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
