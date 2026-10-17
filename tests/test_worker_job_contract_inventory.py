"""Source-only classification for shared job contracts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from worker_job_contract_inventory import build_inventory  # noqa: E402


def test_inventory_distinguishes_location_and_sensor_driver_instance_inputs():
    inventory = build_inventory()
    jobs = {entry["job"]: entry for entry in inventory["jobs"]}

    assert inventory["summary"]["outcomes"] == {
        "default_arguments_accepted": 8,
        "required_runtime_inputs_validated": 7,
    }
    assert jobs["weather"]["required_inputs"] == ["location_id"]
    assert jobs["weather"]["status"] == "required_runtime_inputs_validated"
    assert jobs["climate"]["required_inputs"] == ["location_id"]
    assert jobs["climate"]["status"] == "required_runtime_inputs_validated"
    assert jobs["climate"]["reason"] == "schema accepts the modeled input; each scheduled instance must provide it"
    assert jobs["credit_adjustment"]["required_inputs"] == ["location_id"]
    assert jobs["credit_adjustment"]["status"] == "required_runtime_inputs_validated"
    assert jobs["metrics"]["required_inputs"] == ["location_id"]
    assert jobs["metrics"]["status"] == "required_runtime_inputs_validated"
    assert jobs["sensors"]["required_inputs"] == ["location_id", "driver_instance_id"]
    assert jobs["sensors"]["status"] == "required_runtime_inputs_validated"
    assert jobs["sensors"]["reason"] == "schema accepts the modeled input; each scheduled instance must provide it"
    assert jobs["anomaly"]["required_inputs"] == ["location_id"]
    assert jobs["anomaly"]["status"] == "required_runtime_inputs_validated"
