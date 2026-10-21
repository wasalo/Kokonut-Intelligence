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
import re
import uuid
from typing import Any, Callable, Optional

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import (
    validate_output,
    validate_task_capabilities,
    validate_task_inputs,
)
from services.common.cli import print_json
from services.common.database import get_db

_SOURCE_TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def validate_source_tables(source_tables: Any, *, label: str) -> list[str]:
    """Validate and copy source-table names before draft persistence."""
    if (
        not isinstance(source_tables, list)
        or not 1 <= len(source_tables) <= 20
        or any(
            not isinstance(table, str) or _SOURCE_TABLE_NAME.fullmatch(table) is None
            for table in source_tables
        )
    ):
        raise ValueError(
            f"{label}: source_tables must contain 1 to 20 lowercase SQL identifiers"
        )
    return list(source_tables)


def validate_draft_content_length(content: str, *, label: str) -> None:
    """Enforce the PostgreSQL AI-summary content bound before persistence."""
    if len(content) > 20_000:
        raise ValueError(f"{label}: content must be at most 20000 characters")


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
        request_id: Optional[str] = None,
    ) -> str:
        """Store a draft through the exact-location signed worker adapter.

        ``conn`` remains in the signature for source compatibility, but is not
        used to write. Draft storage has its own authenticated connection and
        retry receipt.
        """
        validate_task_capabilities(self.task_key)
        errors = validate_output(self.task_key, {"summary": summary})
        if errors:
            raise ValueError("; ".join(errors))
        synthesis = summary.get("synthesis")
        if not isinstance(synthesis, str) or not synthesis.strip():
            raise ValueError(
                "Invalid agent draft: summary.synthesis must be a non-empty string"
            )
        validate_draft_content_length(synthesis, label="Invalid agent draft")
        inputs = {"store": True}
        location_id = summary.get("location_id")
        if location_id is not None:
            inputs["location_id"] = location_id
        errors = validate_task_inputs(self.task_key, inputs)
        if errors:
            raise ValueError("; ".join(errors))
        source_tables = validate_source_tables(
            self.source_tables, label="Invalid agent draft"
        )
        version = model_version or self.model_version
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Invalid agent draft: model_version must be a non-empty string")
        assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
        if location_id is None:
            raise ValueError("Agent draft storage requires an exact location_id")
        stable_request_id = str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
        from services.agents.worker_draft import create_worker_ai_summary_draft

        result = create_worker_ai_summary_draft(
            location_id,
            self.summary_type,
            stable_request_id,
            {
                "content": synthesis,
                "source_tables": source_tables,
                "model_version": version,
            },
        )
        return result["summary_id"]

    def run(
        self,
        location_id: Optional[str] = None,
        store: bool = False,
        request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run the agent: synthesize, optionally store a draft, and validate."""
        validate_task_capabilities(self.task_key)
        inputs = {"store": store}
        if location_id is not None:
            inputs["location_id"] = location_id
        errors = validate_task_inputs(self.task_key, inputs)
        if errors:
            raise ValueError("; ".join(errors))
        if store:
            if location_id is None:
                raise ValueError("Agent draft storage requires an exact location_id")
            stable_request_id = str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
            from services.agents.worker_cli import run_worker_synthesis

            return run_worker_synthesis(self, location_id, stable_request_id)
        if request_id is not None:
            raise ValueError("request_id is only valid when storing an agent draft")
        assert_agent_action_allowed("read", self.read_collection, {"location_id": location_id})
        conn = get_db()
        try:
            summary = self.synthesize(conn, location_id)
            output: dict[str, Any] = {"summary": summary}
            errors = validate_output(self.task_key, output)
            if errors:
                raise ValueError("; ".join(errors))
        finally:
            conn.close()
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
    validate_task_capabilities(task_key)
    errors = validate_task_inputs(task_key, ctx)
    if errors:
        raise ValueError("; ".join(errors))
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
    parser.add_argument(
        "--store",
        action="store_true",
        help="Store a location-scoped draft through the signed agent-summary worker",
    )
    parser.add_argument(
        "--request-id",
        help="Stable UUID to reuse when retrying --store (generated when omitted)",
    )
    args = parser.parse_args()
    result = agent.run(
        args.location_id, store=args.store, request_id=args.request_id
    )
    if args.store:
        # Stored synthesis can include private farm and participant context.
        # Return only the durable receipt from CLI output.
        print_json(
            {
                "ai_summary_id": result.get("ai_summary_id"),
                "request_id": result.get("request_id"),
                "resulting_status": "draft",
                "replayed": bool(result.get("replayed")),
            }
        )
    else:
        print_json(result)
