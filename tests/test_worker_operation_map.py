"""The worker-effect inventory must stay aligned with executable allowlists."""

from __future__ import annotations

import json
from inspect import getsourcefile
from pathlib import Path

from services.metrics.calculators import CALCULATORS
from services.security.execution_allowlist import (
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
)

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "docs" / "refactor" / "worker-operation-map.json"


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def test_worker_map_exactly_covers_scheduled_and_event_allowlists():
    inventory = _load_map()

    assert {entry["module"] for entry in inventory["scheduled_modules"]} == ALLOWED_SCHEDULED_MODULES
    assert {(entry["module"], entry["function"]) for entry in inventory["event_handlers"]} == ALLOWED_EVENT_HANDLERS
    assert len(inventory["scheduled_modules"]) == len(ALLOWED_SCHEDULED_MODULES)
    assert len(inventory["event_handlers"]) == len(ALLOWED_EVENT_HANDLERS)


def test_worker_map_entries_have_effect_retry_and_existing_source_evidence():
    inventory = _load_map()
    required = {"scope", "reads", "writes", "idempotency", "retry_boundary", "sources"}

    for entry in inventory["scheduled_modules"]:
        assert required <= entry.keys()
    for entry in inventory["event_handlers"]:
        assert required | {"event_type", "function"} <= entry.keys()

    for entry in (*inventory["scheduled_modules"], *inventory["event_handlers"]):
        assert entry["scope"].strip()
        assert entry["idempotency"].strip()
        assert entry["sources"]
        for source in entry["sources"]:
            assert (ROOT / source).is_file(), source


def test_worker_map_states_shared_identity_and_open_authorization_boundaries():
    inventory = _load_map()
    boundary = inventory["shared_boundary"]

    assert "inherit" in boundary["database_identity"]
    assert "Not established" in boundary["signed_tenant_context"]
    assert "validate command_args" in boundary["module_argument_validation"]
    assert any("separate worker database principal" in item for item in inventory["known_open_items"])
    assert any("existing enabled scheduled_task rows" in item for item in inventory["known_open_items"])
    assert "does not change grants" in boundary["deployment_effect"]


def test_anomaly_handler_records_database_effects_without_claiming_mqtt_delivery():
    inventory = _load_map()
    handler = next(entry for entry in inventory["event_handlers"] if entry["function"] == "handle_sensor_reading")

    assert "public.actuation_log" in handler["writes"]
    assert "public.ingestion_log" in handler["writes"]
    assert all("actuator_command" not in table for table in handler["writes"])


def test_scheduled_operation_map_covers_contract_permitted_side_effects():
    scheduled = {entry["module"]: entry for entry in _load_map()["scheduled_modules"]}
    metrics = scheduled["services.metrics"]
    events = scheduled["services.events"]

    assert "public.noi_snapshot" in metrics["writes"]
    assert "public.v_crop_cycle_noi" in metrics["reads"]
    assert "public.notification_outbox" in events["reads"]
    assert "public.notification_outbox_attempt" in events["writes"]


def test_metrics_worker_map_tracks_registered_calculator_sources():
    metrics = next(entry for entry in _load_map()["scheduled_modules"] if entry["module"] == "services.metrics")
    registered_sources = {
        Path(getsourcefile(calculator)).resolve().relative_to(ROOT.resolve()).as_posix()
        for calculator in CALCULATORS.values()
    }
    mapped_calculators = {source for source in metrics["sources"] if source.startswith("services/metrics/calculators/")}

    assert len(CALCULATORS) == 20
    assert mapped_calculators == registered_sources


def test_metrics_worker_map_covers_calculator_and_database_function_reads():
    metrics = next(entry for entry in _load_map()["scheduled_modules"] if entry["module"] == "services.metrics")
    effects = metrics["calculator_effects"]
    mapped_reads = set(metrics["reads"])
    calculator_reads = {relation for effect in effects.values() for relation in effect["reads"]}
    function_reads = {relation for effect in metrics["database_functions"].values() for relation in effect["reads"]}

    assert set(effects) == set(CALCULATORS)
    assert calculator_reads | function_reads <= mapped_reads
    for effect in effects.values():
        assert effect["reads"]
        assert all(relation.startswith("public.") for relation in effect["reads"])
        assert set(effect["calculator_calls"]) <= set(CALCULATORS)

    function = "public.farm_activity_source_eligible_for_use"
    function_effect = metrics["database_functions"][function]
    assert set(function_effect["called_by"]) == {
        key for key, effect in effects.items() if function in effect["database_function_calls"]
    }
    for source in function_effect["sources"]:
        assert source in metrics["sources"]
    for metric_key in function_effect["called_by"]:
        calculator_source = getsourcefile(CALCULATORS[metric_key])
        assert function.rsplit(".", 1)[-1] in Path(calculator_source).read_text(encoding="utf-8")


def test_freshness_worker_map_covers_fixed_source_table_map():
    from services.ingestion.data_freshness import FRESHNESS_SOURCE_TABLES

    freshness = next(
        entry for entry in _load_map()["scheduled_modules"] if entry["module"] == "services.ingestion.data_freshness"
    )
    mapped_reads = set(freshness["reads"])
    source_tables = {f"public.{table}" for table in FRESHNESS_SOURCE_TABLES.values()}

    assert len(FRESHNESS_SOURCE_TABLES) == 7
    assert source_tables <= mapped_reads
    assert {"public.data_freshness_config", "public.location", "public.sensor_device"} <= mapped_reads
