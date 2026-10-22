"""One-shot signed worker entry point for AI-summary and synthesis drafts."""

from __future__ import annotations

import argparse
import importlib
import json
import re
from typing import Any
from uuid import UUID

from services.agents.ai_summary import build_summary
from services.agents.worker_draft import (
    DETERMINISTIC_SUMMARY_TYPES,
    SYNTHESIS_SUMMARY_TYPES,
    create_worker_ai_summary_draft,
    get_worker_ai_summary_draft,
)
from services.common.tenant_context import (
    set_agent_source_tenant_context,
    set_agent_summary_source_tenant_context,
)
from services.common.worker_database import get_worker_credential, get_worker_db

_SUMMARY_TYPES = DETERMINISTIC_SUMMARY_TYPES
_SUMMARY_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,99}$")

_SYNTHESIS_AGENT_MODULES = {
    "bio_factory_synthesis": "services.agents.bio_factory_agent",
    "capital_efficiency_synthesis": "services.agents.capital_efficiency_agent",
    "commons_liberation_synthesis": "services.agents.commons_agent",
    "feedback_synthesis": "services.agents.feedback_agent",
    "gnh_alignment_synthesis": "services.agents.gnh_agent",
    "holistic_wellbeing_synthesis": "services.agents.wellbeing_agent",
    "kokonut_commons_synthesis": "services.agents.kokonut_commons_agent",
    "open_source_capitalist_synthesis": "services.agents.open_source_capitalist_agent",
    "financial_resilience_synthesis": "services.agents.resilience_agent",
    "regenerator_synthesis": "services.agents.regenerator_agent",
}


def resolve_synthesis_agent(task_key: str) -> Any:
    """Load one explicitly registered shared synthesis agent for the worker."""
    module_name = _SYNTHESIS_AGENT_MODULES.get(task_key)
    if module_name is None:
        raise ValueError("task_key is not a registered synthesis agent")
    module = importlib.import_module(module_name)
    agent = getattr(module, "agent", None)
    if getattr(agent, "task_key", None) != task_key:
        raise RuntimeError("registered synthesis agent task key does not match")
    return agent


def run_worker_synthesis(
    agent: Any,
    location_id: str,
    request_id: str | None,
    *,
    persist_draft: bool = True,
    connection_factory=None,
    existing_reader=None,
    draft_writer=None,
) -> dict[str, Any]:
    """Run a registered synthesis agent through its signed source boundary.

    All source reads use the dedicated public-view reader login in a
    repeatable-read, read-only transaction after installing a signed
    exact-location context; scoped database wrapper views enforce that context
    independently of query filters. When ``persist_draft`` is true, exact
    request lookup precedes source queries and persistence uses the separate
    signed worker connection and immutable retry receipt. Read-only runs return
    the same summary payload without looking up a receipt or writing a draft.
    """
    from services.agents.base import validate_source_tables
    from services.agents.safety import assert_agent_action_allowed
    from services.agents.tasks import (
        validate_output,
        validate_task_capabilities,
        validate_task_inputs,
    )

    if persist_draft:
        try:
            location_id = str(UUID(str(location_id)))
            request_id = str(UUID(str(request_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("location_id and request_id must be UUIDs") from exc
    else:
        try:
            location_id = str(UUID(str(location_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("location_id must be a UUID") from exc
        if request_id is not None:
            raise ValueError("request_id is only valid when persisting an agent draft")
    if not isinstance(getattr(agent, "task_key", None), str):
        raise ValueError("agent task is not registered for the synthesis worker")
    registered_agent = resolve_synthesis_agent(agent.task_key)
    if type(agent) is not type(registered_agent):
        raise ValueError("agent instance does not match its registered synthesis task")
    if (
        not agent.task_key
        or not isinstance(agent.summary_type, str)
        or _SUMMARY_TYPE_PATTERN.fullmatch(agent.summary_type) is None
        or agent.summary_type not in SYNTHESIS_SUMMARY_TYPES
    ):
        raise ValueError("registered synthesis agent metadata is incomplete")
    if any(
        getattr(agent, name, None) != getattr(type(agent), name, None)
        for name in (
            "task_key",
            "summary_type",
            "read_collection",
            "model_version",
            "source_tables",
            "source_reference_views",
            "source_reference_scopes",
            "source_reference_query",
        )
    ):
        raise ValueError("synthesis agent metadata differs from its registered class")
    validate_task_capabilities(agent.task_key)
    input_errors = validate_task_inputs(
        agent.task_key, {"location_id": location_id, "store": persist_draft}
    )
    if input_errors:
        raise ValueError("; ".join(input_errors))
    source_tables = validate_source_tables(
        agent.source_tables, label="Invalid agent draft"
    )
    if len(set(source_tables)) != len(source_tables):
        raise ValueError("Invalid agent draft: source_tables must be unique")
    model_version = agent.model_version
    if (
        not isinstance(model_version, str)
        or not model_version.strip()
        or len(model_version) > 100
    ):
        raise ValueError("Invalid agent draft: model_version must contain 1 to 100 characters")
    assert_agent_action_allowed("read", agent.read_collection, {"location_id": location_id})
    if persist_draft:
        assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})

    if persist_draft:
        read_existing = existing_reader or get_worker_ai_summary_draft
        prior = read_existing(location_id, agent.summary_type, request_id)
        if prior is not None:
            original_summary = prior.get("worker_result")
            if not isinstance(original_summary, dict):
                original_summary = {"location_id": location_id, "synthesis": prior["content"]}
            return {
                "summary": original_summary,
                "ai_summary_id": prior["summary_id"],
                "request_id": request_id,
                "replayed": True,
            }

    source_credential = get_worker_credential("agent_summary_source")
    open_source_connection = connection_factory or (
        lambda: get_worker_db("agent_summary_source")
    )
    connection = open_source_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        set_agent_summary_source_tenant_context(
            connection,
            credential=source_credential,
            location_id=location_id,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_agent_summary_source_reader")
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
        summary = agent.synthesize(connection, location_id)
        source_references = agent.collect_source_references(connection, location_id)
        output_errors = validate_output(agent.task_key, {"summary": summary})
        if output_errors:
            raise ValueError("; ".join(output_errors))
        synthesis = summary.get("synthesis") if isinstance(summary, dict) else None
        if not isinstance(synthesis, str) or not synthesis.strip():
            raise ValueError("Agent draft summary.synthesis must be non-empty text")
        if len(synthesis) > 20_000:
            raise ValueError("Agent draft content must be at most 20000 characters")
        if isinstance(summary, dict) and summary.get("location_id") not in (None, location_id):
            raise ValueError("Agent draft output location does not match its signed scope")
        payload = {
            "content": synthesis,
            "source_tables": source_tables,
            "model_version": model_version,
            "source_references": source_references,
            "worker_result": summary,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if not persist_draft:
        return {"summary": summary}

    write_draft = draft_writer or create_worker_ai_summary_draft
    saved = write_draft(location_id, agent.summary_type, request_id, payload)
    return {
        "summary": summary,
        "ai_summary_id": saved["summary_id"],
        "request_id": request_id,
        "replayed": bool(saved.get("replayed")),
    }


def run_worker_summary(
    location_id: str,
    summary_type: str,
    request_id: str | None,
    *,
    persist_draft: bool = True,
    connection_factory=None,
    summary_builder=None,
    existing_reader=None,
    draft_writer=None,
) -> dict[str, Any]:
    """Generate through the dedicated deterministic source reader.

    Source data is read in a repeatable-read, read-only transaction after a
    database-signed location context selects the deterministic source reader
    role and its filtered views. When ``persist_draft`` is true, the request
    lookup happens before generation and draft creation plus provenance
    attachment use the separate signed worker connection in
    :mod:`worker_draft`.
    """
    if persist_draft:
        try:
            location_id = str(UUID(str(location_id)))
            request_id = str(UUID(str(request_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("location_id and request_id must be UUIDs") from exc
    else:
        try:
            location_id = str(UUID(str(location_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("location_id must be a UUID") from exc
        if request_id is not None:
            raise ValueError("request_id is only valid when persisting an AI-summary draft")
    generate = summary_builder or build_summary
    if (
        not isinstance(summary_type, str)
        or summary_type not in DETERMINISTIC_SUMMARY_TYPES
    ):
        raise ValueError("summary_type is not a registered deterministic worker summary")
    from services.agents.safety import assert_agent_action_allowed
    from services.agents.tasks import validate_task_capabilities, validate_task_inputs

    validate_task_capabilities("ai_summary_synthesis")
    input_errors = validate_task_inputs(
        "ai_summary_synthesis",
        {"location_id": location_id, "summary_type": summary_type, "store": persist_draft},
    )
    if input_errors:
        raise ValueError("; ".join(input_errors))
    assert_agent_action_allowed("read", "ai_summary", {"location_id": location_id})
    if persist_draft:
        assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
        read_existing = existing_reader or get_worker_ai_summary_draft
        prior = read_existing(location_id, summary_type, request_id)
        if prior is not None:
            return prior

    open_source_connection = connection_factory or (
        lambda: get_worker_db("agent_summary_deterministic_source")
    )
    source_credential = get_worker_credential("agent_summary_deterministic_source")
    connection = open_source_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        set_agent_summary_source_tenant_context(
            connection,
            credential=source_credential,
            location_id=location_id,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SET LOCAL ROLE kokonut_agent_summary_deterministic_reader"
            )
            cursor.execute("SET LOCAL search_path = kokonut_agent_source, public")
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
        summary = generate(connection, location_id, summary_type)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if not persist_draft:
        return {"summary": summary}

    # Match the legacy deterministic summary model label while the worker
    # adapter supplies signed identity, idempotency, and source references.
    payload = {
        **summary,
        "model_version": summary.get("model_version", "rules-v1"),
        "worker_result": summary,
    }
    write_draft = draft_writer or create_worker_ai_summary_draft
    return write_draft(location_id, summary_type, request_id, payload)


def run_worker_ebf_evidence_gap(scorecard_id: str, location_id: str) -> dict[str, Any]:
    """Read EBF evidence gaps through its signed location-scoped source view."""
    from services.agents.safety import assert_agent_action_allowed
    from services.agents.tasks import (
        validate_output,
        validate_task_capabilities,
        validate_task_inputs,
    )

    try:
        scorecard_id = str(UUID(str(scorecard_id)))
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("scorecard_id and location_id must be UUIDs") from exc
    validate_task_capabilities("ebf_evidence_gap")
    input_errors = validate_task_inputs(
        "ebf_evidence_gap",
        {"scorecard_id": scorecard_id, "location_id": location_id},
    )
    if input_errors:
        raise ValueError("; ".join(input_errors))
    assert_agent_action_allowed(
        "read", "ebf_scorecard", {"location_id": location_id}
    )

    credential = get_worker_credential("agent_summary_source")
    connection = get_worker_db("agent_summary_source")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        set_agent_source_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource="ebf_scorecard",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_agent_summary_source_reader")
            cursor.execute("SET LOCAL search_path = kokonut_agent_source, public")
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
        from services.agents.ebf_evidence_gap_agent import analyze_evidence_gaps

        result = analyze_evidence_gaps(connection, scorecard_id, location_id)
        output_errors = validate_output("ebf_evidence_gap", result)
        if output_errors:
            raise ValueError("; ".join(output_errors))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return result


def run_worker_cids_export(location_id: str) -> dict[str, Any]:
    """Create the existing CIDS output through a signed location reader."""
    from services.agents.safety import assert_agent_action_allowed
    from services.agents.tasks import (
        validate_output,
        validate_task_capabilities,
        validate_task_inputs,
    )

    validate_task_capabilities("cids_export")
    input_errors = validate_task_inputs("cids_export", {"location_id": location_id})
    if input_errors:
        raise ValueError("; ".join(input_errors))
    try:
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("location_id must be a UUID") from exc
    assert_agent_action_allowed("read", "cids_export", {"location_id": location_id})

    credential = get_worker_credential("agent_summary_source")
    connection = get_worker_db("agent_summary_source")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        set_agent_source_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource="cids_export",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_agent_summary_source_reader")
            cursor.execute("SET LOCAL search_path = kokonut_agent_source, public")
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
        from services.registry.cids_export import export_location

        document = export_location(
            connection, location_id, source_schema="kokonut_agent_source"
        )
        output = {
            "document": document,
            "graph_count": len(document.get("@graph", [])),
            "alignment_tier": document.get("kokonut:alignmentTier"),
            "cids_version": document.get("kokonut:cidsVersion"),
        }
        output_errors = validate_output("cids_export", output)
        if output_errors:
            raise ValueError("; ".join(output_errors))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate one location-scoped agent draft using the signed worker identity"
    )
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument(
        "--task-key", choices=tuple(sorted(_SYNTHESIS_AGENT_MODULES)),
        help="Registered shared synthesis task to run",
    )
    parser.add_argument(
        "--summary-type", choices=_SUMMARY_TYPES, help="Built-in deterministic summary generator"
    )
    parser.add_argument(
        "--request-id", required=True, help="Stable UUID reused when retrying this operation"
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Require a registered synthesis task and prohibit deterministic summary reads",
    )
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Require a built-in summary type and prohibit shared synthesis tasks",
    )
    args = parser.parse_args()
    if args.source_only and not args.task_key:
        parser.error("--source-only requires --task-key")
    if args.deterministic_only and not args.summary_type:
        parser.error("--deterministic-only requires --summary-type")
    if args.deterministic_only and args.task_key:
        parser.error("--deterministic-only cannot be combined with --task-key")
    if args.source_only and args.deterministic_only:
        parser.error("--source-only and --deterministic-only cannot be combined")
    if args.task_key and args.summary_type:
        parser.error("choose either --task-key or --summary-type")
    if args.task_key:
        agent = resolve_synthesis_agent(args.task_key)
        result = run_worker_synthesis(agent, args.location_id, args.request_id)
    else:
        result = run_worker_summary(
            args.location_id, args.summary_type or "combined", args.request_id
        )
    print(
        json.dumps(
            {
                "summary_id": result.get("ai_summary_id", result.get("summary_id")),
                "resulting_status": result.get("resulting_status", "draft"),
                "request_id": result.get("request_id", args.request_id),
                "replayed": bool(result.get("replayed")),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
