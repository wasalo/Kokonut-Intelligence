"""Source inventory tests for CAP-038 agent draft-write boundaries."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.agent_write_boundary_inventory import ROOT, build_inventory, serialize

INVENTORY_PATH = ROOT / "docs/refactor/agent-write-boundary-inventory.json"


def test_saved_agent_write_boundary_inventory_matches_current_sources() -> None:
    assert INVENTORY_PATH.read_text(encoding="utf-8") == serialize(build_inventory())


def test_current_inventory_pins_unattributed_writers_and_authenticated_route() -> None:
    inventory = build_inventory()

    assert inventory["legacy_direct_ai_summary_inserts"] == [
        {"source": "services/agents/ai_summary.py", "line": 459},
        {"source": "services/agents/base.py", "line": 116},
    ]
    assert inventory["authenticated_operator_draft_function_calls"] == [
        {"source": "services/gateway/ai_summary_draft.py", "line": 106}
    ]
    assert inventory["set_agent_context_call_sites"] == []
    assert inventory["summary"] == {
        "legacy_direct_ai_summary_insert_sites": 2,
        "authenticated_operator_draft_function_calls": 1,
        "set_agent_context_call_sites": 0,
    }


def test_inventory_never_embeds_sql_or_runtime_values(tmp_path: Path) -> None:
    agents = tmp_path / "services/agents"
    gateway = tmp_path / "services/gateway"
    agents.mkdir(parents=True)
    gateway.mkdir(parents=True)
    (agents / "legacy.py").write_text(
        "def write(cursor, content):\n"
        "    cursor.execute(\"INSERT INTO ai_summary (content) VALUES (%s)\", (content,))\n"
        "    set_agent_context(connection, 'not-a-principal')\n",
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
    assert inventory["authenticated_operator_draft_function_calls"] == [
        {"source": "services/gateway/draft.py", "line": 2}
    ]
    assert inventory["set_agent_context_call_sites"] == [
        {"source": "services/agents/legacy.py", "line": 3}
    ]
    assert "INSERT INTO" not in serialized
    assert "not-a-principal" not in serialized
    assert "content" not in serialized
