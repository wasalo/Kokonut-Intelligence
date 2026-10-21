"""Source inventory tests for CAP-038 agent draft-write boundaries."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.agent_write_boundary_inventory import ROOT, build_inventory, serialize

INVENTORY_PATH = ROOT / "docs/refactor/agent-write-boundary-inventory.json"


def test_saved_agent_write_boundary_inventory_matches_current_sources() -> None:
    assert INVENTORY_PATH.read_text(encoding="utf-8") == serialize(build_inventory())


def test_current_inventory_pins_no_direct_agent_writes_and_authenticated_routes() -> None:
    inventory = build_inventory()

    assert inventory["direct_agent_write_sites"] == []
    assert inventory["legacy_direct_ai_summary_inserts"] == []
    assert inventory["agent_action_log_insert_sites"] == []
    assert inventory["authenticated_operator_draft_function_calls"] == [
        {"source": "services/gateway/ai_summary_draft.py", "line": 106}
    ]
    assert inventory["authenticated_worker_draft_function_calls"] == [
        {"source": "services/agents/worker_draft.py", "line": 243}
    ]
    assert inventory["authenticated_worker_summary_function_calls"] == [
        {
            "source": "services/agents/worker_draft.py",
            "line": 165,
            "function": "get_location_ai_summary_worker_source_references",
        },
        {
            "source": "services/agents/worker_draft.py",
            "line": 192,
            "function": "get_location_ai_summary_worker_draft_request",
        },
        {
            "source": "services/agents/worker_draft.py",
            "line": 243,
            "function": "create_location_ai_summary_worker_draft",
        },
        {
            "source": "services/agents/worker_draft.py",
            "line": 255,
            "function": "set_location_ai_summary_source_references",
        },
    ]
    assert inventory["set_agent_context_call_sites"] == []
    assert inventory["audit_agent_action_call_sites"] == []
    assert inventory["summary"] == {
        "direct_agent_write_sites": 0,
        "legacy_direct_ai_summary_insert_sites": 0,
        "agent_action_log_insert_sites": 0,
        "authenticated_operator_draft_function_calls": 1,
        "authenticated_worker_draft_function_calls": 1,
        "authenticated_worker_summary_function_calls": 4,
        "set_agent_context_call_sites": 0,
        "audit_agent_action_call_sites": 0,
    }


def test_inventory_never_embeds_sql_or_runtime_values(tmp_path: Path) -> None:
    agents = tmp_path / "services/agents"
    gateway = tmp_path / "services/gateway"
    agents.mkdir(parents=True)
    gateway.mkdir(parents=True)
    (agents / "legacy.py").write_text(
        "def write(cursor, content):\n"
        "    cursor.execute(\"INSERT INTO ai_summary (content) VALUES (%s)\", (content,))\n"
        "    cursor.execute(\"INSERT INTO agent_action_log (agent_id) VALUES (%s)\", ('agent',))\n"
        "    cursor.execute(\"UPDATE ai_summary SET content = %s\", (content,))\n"
        "    cursor.execute(\"DELETE FROM agent_action_log WHERE agent_id = %s\", ('agent',))\n"
        "    set_agent_context(connection, 'not-a-principal')\n",
        encoding="utf-8",
    )
    (agents / "worker.py").write_text(
        "def create(cursor):\n"
        "    cursor.execute(\"SELECT * FROM kokonut_security.create_location_ai_summary_worker_draft(%s)\", ('value',))\n"
        "    cursor.execute(\"SELECT kokonut_security.set_location_ai_summary_source_references(%s)\", ('value',))\n"
        "    cursor.execute(\"SELECT kokonut_security.get_location_ai_summary_worker_source_references(%s)\", ('value',))\n"
        "    cursor.execute(\"SELECT * FROM kokonut_security.get_location_ai_summary_worker_draft_request(%s)\", ('value',))\n",
        encoding="utf-8",
    )
    (gateway / "draft.py").write_text(
        "def create(cursor):\n"
        "    cursor.execute(\"SELECT * FROM kokonut_security.create_location_ai_summary_draft(%s)\", ('value',))\n",
        encoding="utf-8",
    )

    inventory = build_inventory(tmp_path)
    serialized = json.dumps(inventory)

    assert inventory["legacy_direct_ai_summary_inserts"] == [
        {"source": "services/agents/legacy.py", "line": 2}
    ]
    assert inventory["direct_agent_write_sites"] == [
        {
            "source": "services/agents/legacy.py",
            "line": 2,
            "statement_kind": "insert",
            "table": "ai_summary",
        },
        {
            "source": "services/agents/legacy.py",
            "line": 3,
            "statement_kind": "insert",
            "table": "agent_action_log",
        },
        {
            "source": "services/agents/legacy.py",
            "line": 4,
            "statement_kind": "update",
            "table": "ai_summary",
        },
        {
            "source": "services/agents/legacy.py",
            "line": 5,
            "statement_kind": "delete",
            "table": "agent_action_log",
        },
    ]
    assert inventory["agent_action_log_insert_sites"] == [
        {"source": "services/agents/legacy.py", "line": 3}
    ]
    assert inventory["authenticated_operator_draft_function_calls"] == [
        {"source": "services/gateway/draft.py", "line": 2}
    ]
    assert inventory["authenticated_worker_draft_function_calls"] == [
        {"source": "services/agents/worker.py", "line": 2}
    ]
    assert inventory["authenticated_worker_summary_function_calls"] == [
        {"source": "services/agents/worker.py", "line": 2, "function": "create_location_ai_summary_worker_draft"},
        {"source": "services/agents/worker.py", "line": 3, "function": "set_location_ai_summary_source_references"},
        {"source": "services/agents/worker.py", "line": 4, "function": "get_location_ai_summary_worker_source_references"},
        {"source": "services/agents/worker.py", "line": 5, "function": "get_location_ai_summary_worker_draft_request"},
    ]
    assert inventory["set_agent_context_call_sites"] == [
        {"source": "services/agents/legacy.py", "line": 6}
    ]
    assert "INSERT INTO" not in serialized
    assert "DELETE FROM" not in serialized
    assert "UPDATE" not in serialized
    assert "not-a-principal" not in serialized
    assert "content" not in serialized
