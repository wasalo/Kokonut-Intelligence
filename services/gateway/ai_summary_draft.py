"""Authenticated, location-scoped AI summary draft generation."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.agents.ai_summary import build_summary
from services.agents.safety import assert_agent_action_allowed
from services.common.tenant_context import set_operator_tenant_context


class AiSummaryDraftInvalid(ValueError):
    """An AI-summary draft request has invalid scope or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=5)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AiSummaryDraftInvalid(f"Invalid {field} identifier") from exc


def create_operator_ai_summary_draft(
    operator_id: str,
    location_id: str,
    *,
    summary_type: str,
    request_id: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Generate and store one idempotent draft under signed operator scope."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(summary_type, str) or summary_type not in {
        "operations",
        "financial",
        "environmental",
        "combined",
    }:
        raise AiSummaryDraftInvalid("Summary type is not supported")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            # Keep generated aggregates and the subsequent source-ID manifest
            # on one PostgreSQL snapshot so concurrent writes cannot make the
            # recorded references describe a different input set.
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="ai_summary",
            action="draft",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.get_location_ai_summary_draft_request(
                           %s::uuid, %s::text, %s::uuid
                       )""",
                (location_id, summary_type, request_id),
            )
            existing = cursor.fetchone()
        if existing is not None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT kokonut_security.get_location_ai_summary_source_references(
                               %s::uuid, %s::uuid, 'draft'
                           )""",
                    (location_id, str(existing[0])),
                )
                source_references = cursor.fetchone()
            connection.commit()
            return {
                "summary_id": str(existing[0]),
                "location_id": location_id,
                "summary_type": summary_type,
                "content": existing[1],
                "source_tables": existing[2] or [],
                "source_references": source_references[0] if source_references else {},
                "model_version": existing[3],
                "created_at": existing[4],
                "resulting_status": existing[5],
                "replayed": True,
            }

        summary = build_summary(connection, location_id, summary_type)
        assert_agent_action_allowed(
            "create",
            "ai_summary",
            {"status": "draft", "created_by": operator_id, "location_id": location_id},
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_ai_summary_draft(
                           %s::uuid, %s::text, %s::text, %s::text[], %s::uuid
                       )""",
                (
                    location_id,
                    summary_type,
                    summary["content"],
                    summary["source_tables"],
                    request_id,
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("AI summary draft function returned no result")
        if row[6]:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT kokonut_security.get_location_ai_summary_source_references(
                               %s::uuid, %s::uuid, 'draft'
                           )""",
                    (location_id, str(row[0])),
                )
                source_references = cursor.fetchone()
            source_references = source_references[0] if source_references else {}
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT kokonut_security.set_location_ai_summary_source_references(
                               %s::uuid, %s::uuid, %s::uuid, %s::jsonb
                           )""",
                    (
                        location_id,
                        str(row[0]),
                        request_id,
                        json.dumps(summary.get("source_references", {}), sort_keys=True),
                    ),
                )
                attached = cursor.fetchone()
            if attached is None:
                raise RuntimeError("AI summary source-reference function returned no result")
            source_references = attached[0] or {}
        connection.commit()
        return {
            "summary_id": str(row[0]),
            "location_id": location_id,
            "summary_type": summary_type,
            "content": row[1],
            "source_tables": row[2] or [],
            "source_references": source_references,
            "model_version": row[3],
            "created_at": row[4],
            "resulting_status": row[5],
            "replayed": bool(row[6]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
