"""Tenant-scoped, human-reviewed solution lifecycle actions."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class SolutionLifecycleActionInvalid(ValueError):
    """A solution lifecycle action identifier or payload is invalid."""


RETIREMENT_TYPES = frozenset({
    "unsafe",
    "ineffective",
    "too_costly",
    "superseded",
    "not_adopted",
    "context_invalidated",
    "evidence_withdrawn",
    "maintenance_failure",
    "governance_breach",
    "mission_complete",
})


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise SolutionLifecycleActionInvalid(f"Invalid {field} identifier") from exc


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def approve_location_solution_retirement(
    operator_id: str,
    location_id: str,
    retirement_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Approve a location-originated retirement with an idempotent review receipt."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    retirement_id = _normalize_uuid(retirement_id, "retirement")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.approve_location_solution_retirement(
                           %s::uuid, %s::uuid, %s::uuid
                       )""",
                (location_id, retirement_id, request_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution retirement approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def propose_location_solution_retirement(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    retirement_type: str,
    trigger_reason: str,
    evidence_refs: list,
    migration_plan: str,
    replacement_solution_id: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a location-originated retirement proposal with an idempotent receipt."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    if replacement_solution_id is not None:
        replacement_solution_id = _normalize_uuid(replacement_solution_id, "replacement solution")
    if not isinstance(retirement_type, str) or retirement_type not in RETIREMENT_TYPES:
        raise SolutionLifecycleActionInvalid("Invalid retirement type")
    if not isinstance(trigger_reason, str) or not trigger_reason.strip() or len(trigger_reason) > 2000:
        raise SolutionLifecycleActionInvalid("Retirement trigger reason is required and must be at most 2000 characters")
    if not isinstance(migration_plan, str) or not migration_plan.strip() or len(migration_plan) > 4000:
        raise SolutionLifecycleActionInvalid("Retirement migration plan is required and must be at most 4000 characters")
    if not isinstance(evidence_refs, list) or not evidence_refs or len(evidence_refs) > 100:
        raise SolutionLifecycleActionInvalid("Retirement evidence must be a nonempty list of at most 100 items")
    if retirement_type == "superseded" and replacement_solution_id is None:
        raise SolutionLifecycleActionInvalid("Superseded retirement requires a replacement solution")
    try:
        encoded_evidence = json.dumps(
            evidence_refs, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Retirement evidence must contain JSON values") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Retirement evidence exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_location_solution_retirement(
                           %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, %s::uuid
                       )""",
                (
                    location_id,
                    solution_id,
                    request_id,
                    retirement_type,
                    trigger_reason,
                    encoded_evidence,
                    migration_plan,
                    replacement_solution_id,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution retirement proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
