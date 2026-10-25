"""Authenticated receipts for operator-requested registered synthesis tasks."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

TASK_SUMMARY_TYPES = {
    "ai_summary_synthesis": frozenset({"operations", "financial", "environmental", "combined"}),
    "organic_readiness_synthesis": frozenset({"organic_readiness"}),
    "ecological_modeling_synthesis": frozenset({"ecological_modeling"}),
    "holistic_wellbeing_synthesis": frozenset({"holistic_wellbeing"}),
    "feedback_synthesis": frozenset({"stakeholder_feedback"}),
    "commons_liberation_synthesis": frozenset({"commons_liberation"}),
    "gnh_alignment_synthesis": frozenset({"gnh_alignment"}),
    "regenerator_synthesis": frozenset({"regenerative_outcomes"}),
    "capital_efficiency_synthesis": frozenset({"capital_efficiency"}),
    "financial_resilience_synthesis": frozenset({"financial_resilience"}),
    "bio_factory_synthesis": frozenset({"bio_factory"}),
    "open_source_capitalist_synthesis": frozenset({"open_source_capitalist"}),
    "kokonut_commons_synthesis": frozenset({"kokonut_commons"}),
}


class AiSummaryTaskRequestInvalid(ValueError):
    """Raised when an operator task request has invalid fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=5)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AiSummaryTaskRequestInvalid(f"Invalid {field} identifier") from exc


def create_operator_ai_summary_task_request(
    operator_id: str,
    location_id: str,
    *,
    task_key: str,
    summary_type: str,
    request_id: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Mint an immutable, exact-location authorization receipt for one task."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(task_key, str) or task_key not in TASK_SUMMARY_TYPES:
        raise AiSummaryTaskRequestInvalid("Task is not in the registered synthesis catalogue")
    if not isinstance(summary_type, str) or summary_type not in TASK_SUMMARY_TYPES[task_key]:
        raise AiSummaryTaskRequestInvalid("Summary type is not allowed for the registered task")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '10s'")
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
                """SELECT * FROM kokonut_security.create_location_ai_summary_operator_task_request(
                           %s::uuid, %s::text, %s::text, %s::uuid
                       )""",
                (location_id, task_key, summary_type, request_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("AI-summary task request function returned no result")
        connection.commit()
        return {
            "request_id": str(row[0]),
            "location_id": str(row[1]),
            "task_key": row[2],
            "summary_type": row[3],
            "created_at": row[4],
            "replayed": bool(row[5]),
            "status": "authorized",
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
