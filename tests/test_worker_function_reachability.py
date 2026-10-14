"""The generated worker function graph stays aligned with direct source calls."""

from __future__ import annotations

import ast
import json
from types import SimpleNamespace

from scripts.worker_function_reachability import (
    ROOT,
    _resolve_call_target,
    _serialize,
    build_inventory,
)
from services.security.execution_allowlist import (
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
)

INVENTORY_PATH = ROOT / "docs" / "refactor" / "worker-function-reachability.json"


def test_saved_worker_function_graph_matches_current_sources():
    saved = INVENTORY_PATH.read_text(encoding="utf-8")
    assert saved == _serialize(build_inventory())
    assert json.loads(saved)["version"] == 1


def test_worker_function_graph_covers_allowlisted_entrypoints_and_edges():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    expected_names = set(ALLOWED_SCHEDULED_MODULES) | {
        f"{module}.{function}" for module, function in ALLOWED_EVENT_HANDLERS
    }
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

    event_roots = {
        root["function"]
        for operation in operations
        if operation["kind"] == "event_handler"
        for root in operation["entry_functions"]
    }
    assert event_roots == {f"{module}:{function}" for module, function in ALLOWED_EVENT_HANDLERS}


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
