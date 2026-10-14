"""The worker-effect inventory must stay aligned with executable allowlists."""

from __future__ import annotations

import json
from pathlib import Path

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
