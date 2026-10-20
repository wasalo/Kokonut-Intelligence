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
LEARNING_TYPES = frozenset({
    "validated_assumption",
    "invalidated_assumption",
    "implementation",
    "adoption",
    "safety",
    "economic",
    "equity",
    "context_transfer",
})
LEARNING_CONFIDENCE = frozenset({"high", "moderate", "low", "insufficient_evidence"})
LEARNING_TRANSFERABILITY = frozenset({"high", "medium", "low", "unknown"})


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


def record_location_solution_gate_evaluation(
    operator_id: str,
    location_id: str,
    gate_id: str,
    request_id: str,
    passed: bool,
    observed: dict,
    evidence: list,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Append an attributed evaluation for an exact location-origin gate."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "gate")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(passed, bool):
        raise SolutionLifecycleActionInvalid("Gate evaluation result must be true or false")
    if not isinstance(observed, dict):
        raise SolutionLifecycleActionInvalid("Gate observed values must be a JSON object")
    if not isinstance(evidence, list) or not evidence or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid("Gate evidence must be a nonempty list of at most 100 items")
    try:
        encoded_observed = json.dumps(
            observed, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Gate evaluation values must contain JSON data") from exc
    if len(encoded_observed.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Gate observed values exceed the 64 KiB limit")
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Gate evidence exceeds the 64 KiB limit")

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
                """SELECT * FROM kokonut_security.record_location_solution_gate_evaluation(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean, %s::jsonb, %s::jsonb
                       )""",
                (
                    location_id,
                    gate_id,
                    request_id,
                    passed,
                    encoded_observed,
                    encoded_evidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution gate evaluation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_location_solution_gate(
    operator_id: str,
    location_id: str,
    gate_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Approve a passing location-origin gate by a distinct active reviewer."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "gate")
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
                """SELECT * FROM kokonut_security.approve_location_solution_gate(
                           %s::uuid, %s::uuid, %s::uuid
                       )""",
                (location_id, gate_id, request_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution gate approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def transition_location_solution_gate(
    operator_id: str,
    location_id: str,
    gate_id: str,
    request_id: str,
    rationale: str,
    evidence: list,
    rollback_plan: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Advance a location-origin solution through an approved passing gate."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "gate")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(rationale, str) or not 10 <= len(rationale.strip()) <= 4000:
        raise SolutionLifecycleActionInvalid(
            "Transition rationale must contain between 10 and 4000 characters"
        )
    if not isinstance(evidence, list) or not evidence or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid(
            "Transition evidence must be a nonempty list of at most 100 items"
        )
    if rollback_plan is not None and (
        not isinstance(rollback_plan, str) or len(rollback_plan) > 4000
    ):
        raise SolutionLifecycleActionInvalid(
            "Transition rollback plan must be at most 4000 characters"
        )
    try:
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid(
            "Transition evidence must contain JSON values"
        ) from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Transition evidence exceeds the 64 KiB limit")

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
            action="transition",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.transition_location_solution_gate(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::jsonb, %s::text
                       )""",
                (
                    location_id,
                    gate_id,
                    request_id,
                    rationale.strip(),
                    encoded_evidence,
                    rollback_plan,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution gate transition returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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


def propose_location_solution_learning(
    operator_id: str,
    location_id: str,
    replication_id: str,
    request_id: str,
    lesson_type: str,
    finding: str,
    recommended_action: str,
    evidence: list,
    *,
    confidence: str = "moderate",
    transferability: str = "unknown",
    affected_assumptions: list | None = None,
    affected_metrics: list | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an attributed learning proposal from a reviewed location replication."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    replication_id = _normalize_uuid(replication_id, "replication")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(lesson_type, str) or lesson_type not in LEARNING_TYPES:
        raise SolutionLifecycleActionInvalid("Invalid learning lesson type")
    if not isinstance(confidence, str) or confidence not in LEARNING_CONFIDENCE:
        raise SolutionLifecycleActionInvalid("Invalid learning confidence")
    if not isinstance(transferability, str) or transferability not in LEARNING_TRANSFERABILITY:
        raise SolutionLifecycleActionInvalid("Invalid learning transferability")
    for value, name in ((finding, "finding"), (recommended_action, "recommended action")):
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise SolutionLifecycleActionInvalid(
                f"Learning {name} is required and must be at most 4000 characters"
            )

    def encode_array(value: list | None, name: str, *, required: bool = False) -> str:
        if value is None and not required:
            value = []
        if not isinstance(value, list) or (required and not value) or len(value) > 100:
            qualifier = "a nonempty list" if required else "a list"
            raise SolutionLifecycleActionInvalid(
                f"Learning {name} must be {qualifier} of at most 100 items"
            )
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise SolutionLifecycleActionInvalid(f"Learning {name} must contain JSON values") from exc
        if len(encoded.encode("utf-8")) > 65536:
            raise SolutionLifecycleActionInvalid(f"Learning {name} exceeds the 64 KiB limit")
        return encoded

    encoded_assumptions = encode_array(affected_assumptions, "affected assumptions")
    encoded_metrics = encode_array(affected_metrics, "affected metrics")
    encoded_evidence = encode_array(evidence, "evidence", required=True)

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
                """SELECT * FROM kokonut_security.propose_location_solution_learning(
                           %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s,
                           %s::jsonb, %s::jsonb, %s, %s::jsonb
                       )""",
                (
                    location_id,
                    replication_id,
                    request_id,
                    lesson_type,
                    finding,
                    confidence,
                    transferability,
                    encoded_assumptions,
                    encoded_metrics,
                    recommended_action,
                    encoded_evidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution learning proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
