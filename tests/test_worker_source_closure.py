"""The generated worker import closure must remain aligned with source."""

from __future__ import annotations

import json

from scripts.worker_source_closure import ROOT, _serialize, build_inventory
from services.security.execution_allowlist import (
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
    ISOLATED_WORKER_MODULES,
)

INVENTORY_PATH = ROOT / "docs" / "refactor" / "worker-source-closure.json"


def test_saved_worker_source_closure_matches_current_python_sources():
    saved = INVENTORY_PATH.read_text(encoding="utf-8")
    assert saved == _serialize(build_inventory())
    assert json.loads(saved)["version"] == 1


def test_worker_source_closure_covers_all_allowlisted_entrypoints():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    operations = inventory["operations"]
    scheduled = {item["name"] for item in operations if item["kind"] == "scheduled_module"}
    isolated = {item["name"] for item in operations if item["kind"] == "isolated_worker"}
    handlers = {item["name"] for item in operations if item["kind"] == "event_handler"}

    assert scheduled == ALLOWED_SCHEDULED_MODULES
    assert isolated == ISOLATED_WORKER_MODULES
    assert handlers == {f"{module}.{function}" for module, function in ALLOWED_EVENT_HANDLERS}
    assert len(operations) == (
        len(ALLOWED_SCHEDULED_MODULES)
        + len(ISOLATED_WORKER_MODULES)
        + len(ALLOWED_EVENT_HANDLERS)
    )


def test_worker_import_closures_resolve_source_edges_and_surface_dynamic_dispatch():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    for operation in inventory["operations"]:
        modules = set(operation["modules"])
        sources = set(operation["source_files"])
        assert operation["unresolved_local_modules"] == []
        assert sources
        assert sources == {path for path in sources if (ROOT / path).is_file()}
        for edge in operation["local_import_edges"]:
            assert edge["source"] in sources
            assert edge["target"] in modules

    event_bus = "services/events/bus.py"
    dynamic_event_dispatch = [
        site
        for operation in inventory["operations"]
        for site in operation["dynamic_import_sites"]
        if site["source"] == event_bus
    ]
    assert dynamic_event_dispatch
    assert all(site["kind"] == "dynamic module expression" for site in dynamic_event_dispatch)


def test_package_worker_entrypoints_include_the_executed_main_module():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    metrics = next(
        item
        for item in inventory["operations"]
        if item["kind"] == "scheduled_module" and item["name"] == "services.metrics"
    )
    assert "services/metrics/__main__.py" in metrics["source_files"]


def test_agent_worker_closure_contains_exact_registered_synthesis_modules():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    operation = next(
        item
        for item in inventory["operations"]
        if item["kind"] == "isolated_worker"
        and item["name"] == "services.agents.worker_cli"
    )
    targets = operation["registered_agent_targets"]

    assert len(targets) == 12
    assert len({target["task_key"] for target in targets}) == 12
    assert all(target["module"].replace(".", "/") + ".py" in operation["source_files"] for target in targets)
    target_modules = {target["module"] for target in targets}
    registry_edges = [
        edge
        for edge in operation["local_import_edges"]
        if edge["source"] == "services/agents/worker_cli.py"
        and edge["target"] in target_modules
    ]
    assert len(registry_edges) == 12
    assert {edge["kind"] for edge in registry_edges} == {"registered-agent"}
