"""Shared base for Kokonut synthesis agents.

Collapses the per-agent boilerplate that used to be copied across
``services/agents/*_agent.py``: connection handling, the
fetch -> synthesize -> (store draft) -> ``validate_output`` flow, and the
standard ``--location-id``/``--store`` CLI. Agent modules keep their
domain-specific ``synthesize_*`` query and declare task/output metadata on a
small subclass; everything else lives here (or in the existing
:mod:`services.agents.tasks` / :mod:`services.agents.safety` modules).
"""

from __future__ import annotations

import argparse
import uuid
from typing import Any, Callable, Optional

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output
from services.common.cli import print_json
from services.common.database import get_db


class SynthesisAgent:
    """A read-first synthesis agent.

    Subclasses declare their task/output metadata and implement
    :meth:`synthesize`; :meth:`run` provides the shared orchestration:

    * assert the read against the agent safety policy;
    * open one connection and always close it (even on error);
    * optionally store a draft ``ai_summary`` for human review;
    * validate the output against the registered task schema.
    """

    #: task key registered in :mod:`services.agents.tasks` (validated output schema)
    task_key: str = ""
    #: ``ai_summary.summary_type`` written for stored drafts
    summary_type: str = ""
    #: collection checked against the agent safety policy for the read
    read_collection: str = ""
    #: default ``ai_summary.model_version`` for stored drafts
    model_version: str = "agent-v1"
    #: source tables recorded on stored drafts
    source_tables: list[str] = []

    def synthesize(self, conn: Any, location_id: Optional[str] = None) -> dict[str, Any]:
        """Fetch and summarize context for a location. Implement in subclasses."""
        raise NotImplementedError

    def store_summary(
        self,
        conn: Any,
        summary: dict[str, Any],
        model_version: Optional[str] = None,
    ) -> str:
        """Store a draft ``ai_summary`` for human review (no publication)."""
        assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
        summary_id = str(uuid.uuid4())
        # Location-optional agents fall back to a sentinel subject id.
        subject_id = summary.get("location_id") or "00000000-0000-0000-0000-000000000000"
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_summary
                (id, subject_type, subject_id, summary_type, content,
                 source_tables, model_version, status)
            VALUES (%s, 'location', %s, %s, %s, %s, %s, 'draft')
            RETURNING id
            """,
            (
                summary_id,
                subject_id,
                self.summary_type,
                summary["synthesis"],
                self.source_tables,
                model_version or self.model_version,
            ),
        )
        stored_id = str(cur.fetchone()[0])
        conn.commit()
        cur.close()
        return stored_id

    def run(self, location_id: Optional[str] = None, store: bool = False) -> dict[str, Any]:
        """Run the agent: synthesize, optionally store a draft, and validate."""
        assert_agent_action_allowed("read", self.read_collection, {"location_id": location_id})
        conn = get_db()
        try:
            summary = self.synthesize(conn, location_id)
            output: dict[str, Any] = {"summary": summary}
            if store:
                output["ai_summary_id"] = self.store_summary(conn, summary)
        finally:
            conn.close()

        errors = validate_output(self.task_key, output)
        if errors:
            raise ValueError("; ".join(errors))
        return output


def run_fetch(
    task_key: str,
    read_collection: str,
    fetch: Callable[[Any, Any], dict[str, Any]],
    **ctx: Any,
) -> dict[str, Any]:
    """Shared flow for read-only agents (no draft storage).

    Asserts the read against the agent safety policy, fetches with a managed
    connection (always closed), and validates the output against the task
    schema. ``ctx`` kwargs are forwarded to ``fetch(conn, **ctx)`` and also
    used as the safety-policy payload.
    """
    assert_agent_action_allowed("read", read_collection, ctx)
    conn = get_db()
    try:
        output = fetch(conn, **ctx)
    finally:
        conn.close()

    errors = validate_output(task_key, output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def agent_cli(agent: SynthesisAgent, description: str = "", location_required: bool = True) -> None:
    """Standard synthesis-agent CLI: ``--location-id`` and ``--store``, JSON output."""
    parser = argparse.ArgumentParser(
        description=description or f"Run the Kokonut {agent.summary_type} synthesis agent"
    )
    parser.add_argument("--location-id", required=location_required, help="Location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()
    print_json(agent.run(args.location_id, store=args.store))
