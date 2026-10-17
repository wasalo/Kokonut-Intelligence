"""The worker-effect inventory must stay aligned with executable allowlists."""

from __future__ import annotations

import json
from inspect import getsourcefile
from pathlib import Path

from services.events.bus import _HANDLER_WORKER_KEYS
from services.metrics.calculators import CALCULATORS
from services.security.execution_allowlist import (
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
)

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "docs" / "refactor" / "worker-operation-map.json"
EFFECT_PATH = ROOT / "docs" / "refactor" / "worker-effect-inventory.json"


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

    assert "configured runtime PG_USER and PG_PASSWORD" in boundary["database_identity"]
    assert "worker-specific secrets are filtered" in boundary["database_identity"]
    assert "exact source-controlled mapping" in boundary["database_identity"]
    assert "Migration 405" in boundary["signed_tenant_context"]
    assert "Scheduler dispatch and the EventBus parent do not establish it" in boundary["signed_tenant_context"]
    assert "validate command_args" in boundary["module_argument_validation"]
    assert any("principals, credentials, and exact grants for remaining operations" in item
               for item in inventory["known_open_items"])
    assert any("existing enabled scheduled_task rows" in item for item in inventory["known_open_items"])
    assert "does not change grants" in boundary["deployment_effect"]


def test_signed_worker_routing_is_limited_to_integrated_handler_pairs():
    assert _HANDLER_WORKER_KEYS == {
        ("services.ingestion.anomaly_detector", "handle_sensor_reading"): ("sensor_anomaly",),
        ("services.events.handlers", "handle_stale_data"): ("notification_enqueue",),
        ("services.events.handlers", "handle_alert_notification"): ("notification_enqueue",),
        ("services.cache.events", "handle_metric_computed"): ("cache_invalidation",),
        ("services.cache.events", "handle_crisp_scored"): ("cache_invalidation",),
        ("services.cache.events", "handle_sensor_reading"): ("cache_invalidation",),
        ("services.cache.events", "handle_harvest_recorded"): ("cache_invalidation",),
    }


def test_effect_inventory_traces_current_event_runner_and_worker_secret_filter():
    effect_inventory = json.loads(EFFECT_PATH.read_text(encoding="utf-8"))
    dispatches = effect_inventory["callback_dispatches"]

    assert len(dispatches) == 1
    dispatch = dispatches[0]
    assert dispatch["child_entrypoint"] == "services.events.handler_runner:main"
    assert dispatch["request_executor"] == "services.events.handler_runner:execute_request"
    assert dispatch["worker_secret_filter"] == "services.events.bus:_handler_child_environment"
    assert dispatch["allowlist_validator"] == "services.security.execution_allowlist.validate_event_handler"
    assert dispatch["validation_precedes_dynamic_import"] is True
    assert dispatch["allowlisted_handler_targets"] == sorted(
        f"{module}.{function}" for module, function in ALLOWED_EVENT_HANDLERS
    )


def test_sensor_anomaly_effect_contract_matches_source_operation_map():
    inventory = _load_map()
    handler = next(
        entry
        for entry in inventory["event_handlers"]
        if entry["module"] == "services.ingestion.anomaly_detector"
        and entry["function"] == "handle_sensor_reading"
    )
    contract = json.loads(
        (ROOT / "docs/refactor/worker-sensor-anomaly-effects.json").read_text(encoding="utf-8")
    )
    effects = contract["effects"]

    assert contract["status"] == "implemented_disposable_accepted"
    assert contract["operation"]["event_type"] == handler["event_type"]
    assert (contract["operation"]["module"], contract["operation"]["function"]) == (
        handler["module"], handler["function"]
    )
    assert {item["relation"] for item in effects} == set(handler["reads"]) | set(handler["writes"])
    assert len({item["relation"] for item in effects}) == len(effects)
    assert all(item["required_boundary"].strip() for item in effects)
    assert all(item["current_enforcement"].strip() for item in effects)
    assert all(item["class"] for item in effects)
    assert "commit=False" in contract["transaction"]["event_publication"]
    assert "integrated anomaly worker establishes it" in contract["transaction"]["context"]
    assert "dedicated sensor_anomaly database URL and credential" in handler["scope"]
    assert "signed transaction context" in handler["scope"]
    assert "services/ingestion/sensor_anomaly_worker.py" in handler["sources"]
    assert "schemas/postgres/414_sensor_anomaly_worker_delivery.sql" in handler["sources"]
    assert "services/common/worker_environment.py" in handler["sources"]
    assert "services/events/handler_runner.py" in handler["sources"]

    by_relation = {item["relation"]: item for item in effects}
    assert "select_enabled_reference" in by_relation["public.alert_rule"]["access"]
    assert "with status draft" in by_relation["public.mrv_claim"]["required_boundary"]
    assert "Never expose claim, lease" in by_relation["public.platform_event"]["required_boundary"]
    assert "cannot approve, send, execute" in by_relation["public.actuation_log"]["required_boundary"]


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
    credit_adjustments = scheduled["services.analytics.carbon_credit_adjustment_check"]
    projections = scheduled["services.ingestion.clickhouse_outbox"]

    assert "public.noi_snapshot" in metrics["writes"]
    assert "public.v_crop_cycle_noi" in metrics["reads"]
    assert "requires exactly one --location-id" in metrics["scope"]
    assert "--all-locations mode is rejected" in metrics["scope"]
    assert "public.notification_outbox" in events["reads"]
    assert "public.notification_outbox_attempt" in events["writes"]
    assert set(credit_adjustments["reads"]) == {
        "public.carbon_credit",
        "public.climate_impact_summary",
        "public.tree_inventory",
        "public.soil_carbon_measurement",
        "public.ghg_emissions_inventory",
    }
    assert credit_adjustments["writes"] == []
    assert credit_adjustments["external_effects"] == []
    assert "read-only transaction" in credit_adjustments["idempotency"]
    assert "interactive credit-management CLI is not scheduler-allowlisted" in credit_adjustments["scope"]
    assert set(projections["reads"]) == {"public.clickhouse_outbox"}
    assert set(projections["writes"]) == {
        "public.clickhouse_outbox",
        "public.clickhouse_outbox_operator_audit",
    }
    assert "ClickHouse" in " ".join(projections["external_effects"])
    assert "--run-once" in projections["scope"]
    assert "--limit 100" in projections["scope"]


def test_scheduled_credit_check_reachability_excludes_interactive_chain_effects():
    effects = json.loads(EFFECT_PATH.read_text(encoding="utf-8"))
    operation = next(
        item
        for item in effects["operations"]
        if item["name"] == "services.analytics.carbon_credit_adjustment_check"
    )

    assert operation["candidate_effect_sites"] == []
    assert operation["category_counts"] == {}


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


def test_climate_worker_map_names_current_schema_and_provider_effects():
    climate = next(
        entry for entry in _load_map()["scheduled_modules"] if entry["module"] == "services.ingestion.climate_data"
    )

    assert set(climate["reads"]) == {"public.location", "public.plot", "public.farm"}
    assert set(climate["writes"]) == {
        "public.worldclim_climate",
        "public.ncep_weather_summary",
        "public.modis_lst_summary",
        "public.smap_soil_moisture",
        "public.sentinel1_sar_summary",
        "public.ingestion_log",
    }
    assert "latitude_proxy_v1" in " ".join(climate["external_effects"])
    assert "schemas/postgres/397_worldclim_location_baseline_key.sql" in climate["sources"]


def test_remote_sensing_job_is_bounded_and_provider_execution_is_not_claimed():
    entry = next(
        item
        for item in _load_map()["scheduled_modules"]
        if item["module"] == "services.ingestion.remote_sensing_fetcher"
    )

    assert "at most --limit jobs sequentially (1-10" in entry["scope"]
    assert "requires one explicit --location-id" in entry["scope"]
    assert "filtered by the required location" in entry["idempotency"]
    assert "one 30-minute lease at a time" in entry["idempotency"]
    assert "Google Earth Engine API requests" in entry["external_effects"]
    assert "Copernicus Data Space API requests" in entry["external_effects"]
    assert "public.remote_sensing_provider_attempt" in entry["writes"]
