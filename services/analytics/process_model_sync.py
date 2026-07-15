"""Sync per-entity-type process models from registered WorkflowSpecs.

Keeps the ``process_model`` table (186) in sync with the canonical workflow
specifications so conformance / prediction / escalation use the same state
machine the services enforce. Types without a spec (``market_order``,
``metric_value``) are seeded explicitly in 186 and left untouched here.

Run with: ``python3 -m services.analytics.process_model_sync``
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from services.ingestion.base import get_db
from services.workflow_specs.registry import list_specs, load_builtin_specs

# Terminal states that represent failure rather than successful completion.
_FAILURE_TERMINALS = {"cancelled", "rejected"}


def spec_to_rows(spec) -> List[Dict[str, Any]]:
    """Derive process_model rows from a WorkflowSpec's steps/transitions."""
    states: Dict[str, Dict[str, Any]] = {}
    initial = None
    for step in spec.steps:
        state = step.current_state
        allowed = [t.next_state for t in step.transitions]
        terminal = bool(step.terminal)
        is_goal = terminal and state not in _FAILURE_TERMINALS
        if step.entry:
            initial = state
        states[state] = {
            "is_terminal": terminal,
            "allowed_next": allowed,
            "is_goal": is_goal,
        }
    rows: List[Dict[str, Any]] = []
    for state, node in states.items():
        rows.append(
            {
                "entity_type": spec.id,
                "status": state,
                "is_terminal": node["is_terminal"],
                "allowed_next": node["allowed_next"],
                "is_goal": node["is_goal"],
                "is_initial": state == initial,
            }
        )
    return rows


def sync_process_models(conn) -> int:
    """Upsert a process_model row per spec state. Returns rows written."""
    load_builtin_specs()
    cur = conn.cursor()
    updated = 0
    for spec in list_specs():
        expected_states = []
        for row in spec_to_rows(spec):
            expected_states.append(row["status"])
            cur.execute(
                """
                INSERT INTO process_model
                    (entity_type, status, is_terminal, allowed_next,
                     is_goal, is_initial)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (entity_type, status) DO UPDATE SET
                    is_terminal = EXCLUDED.is_terminal,
                    allowed_next = EXCLUDED.allowed_next,
                    is_goal = EXCLUDED.is_goal,
                    is_initial = EXCLUDED.is_initial
                """,
                (
                    row["entity_type"],
                    row["status"],
                    row["is_terminal"],
                    json.dumps(row["allowed_next"]),
                    row["is_goal"],
                    row["is_initial"],
                ),
            )
            updated += 1
        placeholders = ", ".join(["%s"] * len(expected_states))
        cur.execute(
            f"DELETE FROM process_model WHERE entity_type = %s "
            f"AND status NOT IN ({placeholders})",
            [spec.id, *expected_states],
        )
    conn.commit()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync process_model rows from registered workflow specs"
    )
    parser.parse_args()
    conn = get_db()
    try:
        n = sync_process_models(conn)
        print(json.dumps({"synced_rows": n}, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
