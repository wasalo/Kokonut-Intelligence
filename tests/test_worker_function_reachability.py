"""The generated worker function graph stays aligned with direct source calls."""

from __future__ import annotations

import ast
import json
from types import SimpleNamespace

from scripts.worker_function_reachability import (
    ROOT,
    _CallVisitor,
    _DefinitionVisitor,
    _ImportContextVisitor,
    _infer_instance_types,
    _resolve_call_target,
    _serialize,
    build_inventory,
)
from services.security.execution_allowlist import (
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
    ISOLATED_WORKER_MODULES,
)

INVENTORY_PATH = ROOT / "docs" / "refactor" / "worker-function-reachability.json"


def test_saved_worker_function_graph_matches_current_sources():
    saved = INVENTORY_PATH.read_text(encoding="utf-8")
    assert saved == _serialize(build_inventory())
    assert json.loads(saved)["version"] == 1


def test_worker_function_graph_covers_allowlisted_entrypoints_and_edges():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    expected_names = (
        set(ALLOWED_SCHEDULED_MODULES)
        | set(ISOLATED_WORKER_MODULES)
        | {f"{module}.{function}" for module, function in ALLOWED_EVENT_HANDLERS}
    )
    operations = inventory["operations"]

    assert {operation["name"] for operation in operations} == expected_names
    assert inventory["summary"]["operations_without_resolved_entry_functions"] == 0
    for operation in operations:
        sources = set(operation["source_files"])
        functions = {function["key"] for function in operation["reachable_functions"]}
        assert operation["entry_functions"]
        assert {root["function"] for root in operation["entry_functions"]} <= functions
        assert len(functions) == len(operation["reachable_functions"])
        for function in operation["reachable_functions"]:
            assert function["source"] in sources
            assert (ROOT / function["source"]).is_file()
            assert function["line"] > 0
        for edge in operation["direct_call_edges"]:
            assert edge["caller"] in functions
            assert edge["callee"] in functions
            assert edge["source"] in sources
            assert edge["line"] > 0
        for edge in operation["dynamic_dispatch_edges"]:
            assert edge["caller"] in functions
            assert edge["callee"] in functions
            assert edge["source"] in sources
            assert edge["line"] > 0
            assert edge["dispatch"] in {
                "literal_function_registry",
                "literal_code_allowlisted_sensor_driver_registry",
            }

    event_roots = {
        root["function"]
        for operation in operations
        if operation["kind"] == "event_handler"
        for root in operation["entry_functions"]
    }
    assert event_roots == {f"{module}:{function}" for module, function in ALLOWED_EVENT_HANDLERS}


def test_graph_tracks_instance_methods_and_literal_metric_registry_dispatch():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    by_name = {(operation["kind"], operation["name"]): operation for operation in inventory["operations"]}

    cache_operation = by_name[("event_handler", "services.cache.events.handle_metric_computed")]
    cache_functions = {function["key"] for function in cache_operation["reachable_functions"]}
    assert "services.cache.cache:ComputationCache.invalidate" in cache_functions

    event_operation = by_name[("scheduled_module", "services.events")]
    event_functions = {function["key"] for function in event_operation["reachable_functions"]}
    assert any(key.startswith("services.events.bus:EventBus.") for key in event_functions)

    metrics_operation = by_name[("scheduled_module", "services.metrics")]
    registry_edges = metrics_operation["dynamic_dispatch_edges"]
    assert len(registry_edges) == 20
    assert {edge["registry_key"] for edge in registry_edges} == {
        "value_flowed",
        "wallet_retention",
        "digital_lego_usage",
        "attestation_coverage",
        "soil_carbon_delta",
        "biodiversity_delta",
        "operating_margin_pct",
        "crop_revenue",
        "net_crop_revenue",
        "direct_crop_cost",
        "allocated_shared_cost",
        "crop_noi",
        "loss_rate_pct",
        "baseline_revenue",
        "baseline_asset_value",
        "baseline_cash_flow",
        "baseline_cost",
        "governed_lead_time_days",
        "first_time_through_yield_pct",
        "rework_rate_pct",
    }


def test_graph_traces_code_allowlisted_scheduled_sensor_driver_methods():
    inventory = build_inventory()
    operation = next(
        item
        for item in inventory["operations"]
        if item["name"] == "services.ingestion.sensor_worker"
    )
    functions = {function["key"] for function in operation["reachable_functions"]}
    expected = {
        "services.drivers.base:BaseDriver.__init__",
        "services.ingestion.drivers.sensor_csv:Driver.discover",
        "services.ingestion.drivers.sensor_csv:Driver.fetch_scheduled",
        "services.ingestion.drivers.sensor_csv:Driver.fetch_stream",
        "services.ingestion.drivers.sensor_csv:Driver.transform",
    }
    assert expected <= functions
    assert "services/ingestion/drivers/sensor_csv.py" in operation["source_files"]

    dispatches = [
        edge
        for edge in operation["dynamic_dispatch_edges"]
        if edge["dispatch"] == "literal_code_allowlisted_sensor_driver_registry"
    ]
    assert {edge["callee"] for edge in dispatches} == {
        "services.drivers.base:BaseDriver.__init__",
        "services.ingestion.drivers.sensor_csv:Driver.discover",
        "services.ingestion.drivers.sensor_csv:Driver.fetch_scheduled",
        "services.ingestion.drivers.sensor_csv:Driver.transform",
    }
    assert {edge["registry_key"] for edge in dispatches} == {"sensor_csv"}
    assert all(edge["caller"] == "services.ingestion.sensor_worker:_prepare_records" for edge in dispatches)


def test_graph_traces_explicit_worker_persistence_constructor_injection():
    inventory = json.loads(_serialize(build_inventory()))
    by_name = {operation["name"]: operation for operation in inventory["operations"]}
    cases = {
        "services.ingestion.baal_worker": (
            "services.ingestion.baal_indexer:run",
            "services.ingestion.baal_worker:BaalWorkerPersistence",
            {
                "_scalar", "acquire_lock", "release_lock", "read_cursor", "resolve_protocol",
                "resolve_wallet", "store_governance_event", "update_status",
            },
        ),
        "services.ingestion.gnosis_worker": (
            "services.ingestion.gnosis_indexer:run",
            "services.ingestion.gnosis_worker:GnosisWorkerPersistence",
            {
                "_scalar", "acquire_lock", "release_lock", "read_cursor", "claim_event",
                "resolve_wallet", "resolve_wallet_location", "resolve_protocol",
                "store_governance_event", "store_treasury_event", "store_digital_lego_usage",
                "enqueue_projection", "update_status",
            },
        ),
        "services.ingestion.freshness_worker": (
            "services.ingestion.data_freshness:check_freshness",
            "services.ingestion.freshness_worker:FreshnessPersistence",
            {
                "_rows", "_one", "list_configs", "list_location_ids", "latest_data_at",
                "insert_check", "lock_alert_state", "persist_alert_event", "enqueue_alert_event",
                "update_alert_state", "update_check_alert",
            },
        ),
    }

    for operation_name, (processor, adapter_class, expected_methods) in cases.items():
        operation = by_name[operation_name]
        function_keys = {function["key"] for function in operation["reachable_functions"]}
        assert {f"{adapter_class}.{method}" for method in expected_methods} <= function_keys
        assert any(
            binding["callee"] == processor
            and binding["parameter"] == "persistence"
            and binding["instance_class"] == adapter_class
            for binding in operation["injected_instance_bindings"]
        )


def test_graph_follows_shared_cli_run_callback_to_the_actual_command_body():
    inventory = build_inventory()
    operation = next(
        item
        for item in inventory["operations"]
        if item["name"] == "services.analytics.carbon_credit_adjustment_check"
    )
    functions = {function["key"] for function in operation["reachable_functions"]}

    assert "services.analytics.carbon_credit_adjustment_check:main" in functions
    assert "services.analytics.carbon_credits:check_adjustments" in functions
    assert "services.credit_class.chain_sync:retire_onchain" not in functions


def test_direct_call_resolution_handles_module_and_symbol_aliases():
    function = {"module": "services.worker", "qualname": "run", "class_scope": None}
    definitions = {"services.helpers:run_job": {}, "services.helpers:run_query": {}}
    contexts = {
        "services.worker": SimpleNamespace(
            module_aliases={"services": "services"},
            symbol_aliases={"do_work": "services.helpers:run_job"},
        )
    }
    module_call = ast.parse("services.helpers.run_query()", mode="eval").body
    symbol_call = ast.parse("do_work()", mode="eval").body

    assert _resolve_call_target(function, module_call, definitions, contexts) == "services.helpers:run_query"
    assert _resolve_call_target(function, symbol_call, definitions, contexts) == "services.helpers:run_job"


def test_direct_call_resolution_tracks_class_scoped_self_methods():
    function = {"module": "services.worker", "qualname": "Writer.persist", "class_scope": "Writer"}
    definitions = {"services.worker:Writer.flush": {}}
    contexts = {"services.worker": SimpleNamespace(module_aliases={}, symbol_aliases={})}
    method_call = ast.parse("self.flush()", mode="eval").body

    assert _resolve_call_target(function, method_call, definitions, contexts) == "services.worker:Writer.flush"


def _fixture_call_graph(source: str):
    module = "services.worker_fixture"
    source_path = "services/worker_fixture.py"
    tree = ast.parse(source)
    definitions_visitor = _DefinitionVisitor(module, source_path)
    definitions_visitor.visit(tree)
    context = _ImportContextVisitor(
        module,
        source_path,
        {module},
        definitions_visitor.definitions,
        definitions_visitor.classes,
    )
    context.visit(tree)
    return definitions_visitor, {module: context}


def test_graph_tracks_types_yielded_by_connection_context_managers():
    definitions, contexts = _fixture_call_graph(
        """
class DatabaseConnection:
    def execute(self, sql):
        pass

def get_connection():
    return DatabaseConnection()

def worker():
    with get_connection() as connection:
        connection.execute('SELECT 1')
"""
    )
    function = definitions.definitions["services.worker_fixture:worker"]
    instance_types = _infer_instance_types(
        function,
        definitions.definitions,
        definitions.classes,
        contexts,
    )

    assert instance_types["connection"] == {"services.worker_fixture:DatabaseConnection"}


def test_graph_narrows_receiver_inside_positive_isinstance_branch_only():
    definitions, contexts = _fixture_call_graph(
        """
class DatabaseConnection:
    def execute(self, sql):
        pass

def query(connection):
    if isinstance(connection, DatabaseConnection):
        connection.execute('SELECT 1')

def unsafe_query(connection, enabled):
    if isinstance(connection, DatabaseConnection) or enabled:
        connection.execute('SELECT 1')
"""
    )
    query = definitions.definitions["services.worker_fixture:query"]
    query_graph = _CallVisitor(query, definitions.definitions, definitions.classes, contexts)
    query_graph.visit(query["node"])
    unsafe_query = definitions.definitions["services.worker_fixture:unsafe_query"]
    unsafe_graph = _CallVisitor(unsafe_query, definitions.definitions, definitions.classes, contexts)
    unsafe_graph.visit(unsafe_query["node"])

    assert {edge["callee"] for edge in query_graph.edges} == {"services.worker_fixture:DatabaseConnection.execute"}
    assert unsafe_graph.edges == []
