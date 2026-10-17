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
        "default_arguments_accepted": 5,
        "required_runtime_inputs_validated": 11,
    }
    assert jobs["noi_snapshots"]["required_inputs"] == ["location_id"]
    assert jobs["noi_snapshots"]["status"] == "required_runtime_inputs_validated"
    assert jobs["noi_snapshots"]["module"] == "services.metrics.noi_snapshot_worker"
    assert jobs["noi_snapshots"]["worker_key"] == "noi_snapshot"
    assert jobs["weather"]["required_inputs"] == ["location_id"]
    assert jobs["weather"]["status"] == "required_runtime_inputs_validated"
    assert jobs["weather"]["module"] == "services.ingestion.weather_worker"
    assert jobs["weather"]["worker_key"] == "weather"
    assert jobs["weather_forecast"]["module"] == "services.ingestion.weather_forecast_worker"
    assert jobs["weather_forecast"]["worker_key"] == "weather_forecast"
    assert jobs["weather_forecast"]["required_inputs"] == ["location_id"]
    assert jobs["weather_forecast"]["status"] == "required_runtime_inputs_validated"
    assert jobs["market_data"]["module"] == "services.ingestion.market_data_worker"
    assert jobs["market_data"]["worker_key"] == "market_data"
    assert jobs["market_data"]["status"] == "default_arguments_accepted"
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
