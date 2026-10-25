"""Shared base for Kokonut synthesis agents.

Collapses shared orchestration for ``services/agents/*_agent.py``: the
registered signed source-reader path, optional draft persistence, output
validation, and the standard ``--location-id``/``--store`` CLI. Agent modules
keep their domain-specific queries and declare task/output/source metadata on
a small subclass; task and safety rules live in their dedicated modules.
"""

from __future__ import annotations

import argparse
import re
import uuid
from typing import Any, Callable, Optional

import psycopg2.extras

from services.agents.tasks import (
    validate_task_capabilities,
    validate_task_inputs,
)
from services.common.cli import print_json

_SOURCE_TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_PUBLIC_SOURCE_VIEW_NAME = re.compile(r"^v_public_[a-z0-9_]{1,55}$")
_SOURCE_REFERENCE_SCOPES = frozenset({"location", "network", "location_or_network"})


def require_synthesis_location_id(location_id: Any) -> str:
    """Reject unscoped synthesis reads before a query can run."""
    if not isinstance(location_id, str) or not location_id.strip():
        raise ValueError("Synthesis requires an exact location_id")
    try:
        uuid.UUID(location_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Synthesis requires a valid location_id UUID") from exc
    return location_id


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

    * require a reviewed source-view contract and exact location;
    * dispatch through the dedicated signed source-reader identity;
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
    #: exact source-table to public-view mapping for private row manifests
    source_reference_views: dict[str, str] = {}
    #: Scope for mapped source views; entries default to location-only.
    source_reference_scopes: dict[str, str] = {}
    #: Explicit reason for each declared source excluded from the row manifest.
    source_reference_exclusions: dict[str, str] = {}
    #: fixed SQL that returns source_table, row_count, and ordered record_ids
    source_reference_query: Optional[str] = None

    def synthesize(self, conn: Any, location_id: Optional[str] = None) -> dict[str, Any]:
        """Fetch and summarize context for a location. Implement in subclasses."""
        raise NotImplementedError

    def collect_source_references(
        self, conn: Any, location_id: str
    ) -> dict[str, dict[str, Any]]:
        """Return bounded row references for sources that have a safe view contract.

        The fixed or map-generated query runs only for signed draft storage, in
        the same repeatable-read transaction as :meth:`synthesize`. Every
        declared source must have a public-view mapping or a bounded explicit
        exclusion reason; unclassified sources fail before opening a cursor.
        """
        # These values define the reviewed provenance contract for the
        # registered agent class. Ignore instance shadowing here; the worker
        # entry point separately rejects metadata that differs from the class.
        source_tables = type(self).source_tables
        source_reference_views = type(self).source_reference_views
        source_reference_scopes = type(self).source_reference_scopes
        source_reference_exclusions = type(self).source_reference_exclusions
        source_reference_query = type(self).source_reference_query
        if (
            len(source_reference_views) > 20
            or len(source_tables) > 20
            or len(set(source_tables)) != len(source_tables)
            or any(table not in source_tables for table in source_reference_views)
            or any(table not in source_reference_views for table in source_reference_scopes)
            or any(table not in source_tables for table in source_reference_exclusions)
            or set(source_reference_views).intersection(source_reference_exclusions)
            or set(source_tables)
            != set(source_reference_views).union(source_reference_exclusions)
            or any(
                not isinstance(scope, str) or scope not in _SOURCE_REFERENCE_SCOPES
                for scope in source_reference_scopes.values()
            )
            or any(
                not isinstance(reason, str)
                or not reason.strip()
                or len(reason) > 300
                for reason in source_reference_exclusions.values()
            )
        ):
            raise ValueError(
                "source reference views and documented exclusions must cover declared source tables"
            )
        if not source_reference_views:
            return {}
        query = source_reference_query or self._build_source_reference_query()
        bound_scope_count = sum(
            source_reference_scopes.get(table, "location") != "network"
            for table in source_reference_views
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(query, (location_id,) * bound_scope_count)
            rows = cur.fetchall()
        finally:
            cur.close()
        references: dict[str, dict[str, Any]] = {}
        for row in rows:
            source_table = row["source_table"]
            if source_table not in source_reference_views or source_table in references:
                raise ValueError("source reference query returned an undeclared source table")
            row_count = int(row["row_count"])
            record_ids = [str(record_id) for record_id in row["record_ids"]]
            reference = {
                "record_ids": record_ids,
                "row_count": row_count,
                "truncated": row_count > len(record_ids),
            }
            scope = source_reference_scopes.get(source_table, "location")
            if scope != "location":
                reference["scope"] = scope
            references[source_table] = reference
        for source_table in source_reference_views:
            scope = source_reference_scopes.get(source_table, "location")
            empty_reference = {
                "record_ids": [],
                "row_count": 0,
                "truncated": False,
            }
            if scope != "location":
                empty_reference["scope"] = scope
            references.setdefault(source_table, empty_reference)
        return references

    def _build_source_reference_query(self) -> str:
        """Build bounded location-filtered SQL from scoped source-view metadata."""
        selects = []
        for source_table, view_name in type(self).source_reference_views.items():
            if (
                _SOURCE_TABLE_NAME.fullmatch(source_table) is None
                or _PUBLIC_SOURCE_VIEW_NAME.fullmatch(view_name) is None
            ):
                raise ValueError("source reference metadata contains an invalid SQL identifier")
            scope = type(self).source_reference_scopes.get(source_table, "location")
            if not isinstance(scope, str) or scope not in _SOURCE_REFERENCE_SCOPES:
                raise ValueError("source reference metadata contains an invalid scope")
            predicate = {
                "location": " WHERE location_id = %s",
                "network": "",
                "location_or_network": " WHERE location_id = %s OR location_id IS NULL",
            }[scope]
            selects.append(
                f"SELECT '{source_table}'::text AS source_table, id "
                f"FROM kokonut_agent_source.{view_name}{predicate}"
            )
        return f"""
            WITH sources AS MATERIALIZED (
                {' UNION ALL '.join(selects)}
            ), counts AS (
                SELECT source_table, count(*) AS row_count
                FROM sources
                GROUP BY source_table
            ), numbered AS (
                SELECT source_table, id,
                       row_number() OVER (PARTITION BY source_table ORDER BY id) AS ordinal
                FROM sources
            )
            SELECT counts.source_table, counts.row_count,
                   array_agg(numbered.id ORDER BY numbered.ordinal)
                       FILTER (WHERE numbered.ordinal <= 50) AS record_ids
            FROM counts
            JOIN numbered USING (source_table)
            GROUP BY counts.source_table, counts.row_count
            ORDER BY counts.source_table
        """

    def store_summary(
        self,
        conn: Any,
        summary: dict[str, Any],
        model_version: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """Reject the retired caller-connection draft writer.

        The signed worker must generate the synthesis and collect its bounded
        provenance references in the same read transaction before persistence.
        The old signature remains to give existing callers a direct migration
        path to :meth:`run` without touching their supplied connection.
        """
        del conn, summary, model_version, request_id
        raise RuntimeError(
            "store_summary is retired; human-triggered persistence requires an "
            "authenticated operator/request/task attribution path"
        )

    def run(
        self,
        location_id: Optional[str] = None,
        store: bool = False,
        request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run a read-only synthesis; unattributed caller persistence is disabled."""
        if store:
            raise RuntimeError(
                "Human-triggered synthesis persistence is disabled until an "
                "authenticated operator/request/task attribution path is available"
            )
        validate_task_capabilities(self.task_key)
        if location_id is None:
            raise ValueError("Synthesis requires an exact location_id")
        inputs = {"store": store}
        inputs["location_id"] = location_id
        errors = validate_task_inputs(self.task_key, inputs)
        if errors:
            raise ValueError("; ".join(errors))
        if not type(self).source_reference_views:
            raise ValueError(
                "Synthesis requires a registered signed source-reference view map"
            )
        if request_id is not None:
            raise ValueError("request_id is only valid when storing an agent draft")
        # Registered shared-synthesis agents use the dedicated signed,
        # location-scoped source identity for every read. There is no shared
        # application-database fallback for unmapped subclasses.
        from services.agents.worker_cli import run_worker_synthesis

        return run_worker_synthesis(
            self,
            location_id,
            None,
            persist_draft=False,
        )


def run_fetch(
    task_key: str,
    read_collection: str,
    fetch: Callable[[Any, Any], dict[str, Any]],
    **ctx: Any,
) -> dict[str, Any]:
    """Reject the retired shared-database helper before any callback or I/O.

    Read-only agents must use a registered source-view contract and the signed
    worker adapter. The arguments remain in the signature for a clear error to
    older callers, but are intentionally not inspected or executed here.
    """
    del task_key, read_collection, fetch, ctx
    raise RuntimeError(
        "run_fetch is retired; use a registered signed source-reader adapter"
    )


def agent_cli(agent: SynthesisAgent, description: str = "", location_required: bool = True) -> None:
    """Standard read-only synthesis CLI with an exact location and JSON output."""
    parser = argparse.ArgumentParser(
        description=description or f"Run the Kokonut {agent.summary_type} synthesis agent"
    )
    parser.add_argument(
        "--location-id",
        required=location_required or bool(type(agent).source_reference_views),
        help="Location UUID",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="Unavailable until an authenticated operator task route is implemented",
    )
    parser.add_argument(
        "--request-id",
        help="Unavailable from this unauthenticated CLI; draft storage is disabled",
    )
    args = parser.parse_args()
    if args.store:
        parser.error(
            "human-triggered synthesis draft storage requires an authenticated "
            "operator/request/task attribution path"
        )
    if args.request_id:
        parser.error("--request-id is unavailable because this CLI cannot persist drafts")
    result = agent.run(args.location_id)
    print_json(result)
