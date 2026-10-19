"""Location-scoped, read-only Kernel projections for threatcasting plans."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 100
_MAX_DETAIL_MILESTONES = 500


class ThreatcastingReadInvalid(ValueError):
    """A threatcasting identifier, page size, or cursor is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ThreatcastingReadInvalid(f"Invalid {field} identifier") from exc


def _page_size(value: str | int) -> int:
    if isinstance(value, str):
        if not value.isdecimal():
            raise ThreatcastingReadInvalid("limit must be an integer between 1 and 100")
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise ThreatcastingReadInvalid("limit must be an integer between 1 and 100")
    return value


def _normalize_cursor_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ThreatcastingReadInvalid("Invalid cursor timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ThreatcastingReadInvalid("Cursor timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def _open_readonly(factory: Callable):
    connection = factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
    except Exception:
        try:
            connection.rollback()
        finally:
            connection.close()
        raise
    return connection


def list_location_backcast_plans(
    operator_id: str,
    location_id: str,
    *,
    limit: str | int = 50,
    cursor_created_at: str | datetime | None = None,
    cursor_plan_id: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded plan summaries using a signed location grant."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_size(limit)
    before_created_at = _normalize_cursor_time(cursor_created_at)
    before_plan_id = (
        _normalize_uuid(cursor_plan_id, "cursor plan") if cursor_plan_id is not None else None
    )
    if (before_created_at is None) != (before_plan_id is None):
        raise ThreatcastingReadInvalid(
            "cursor_created_at and cursor_plan_id must be provided together"
        )

    connection = _open_readonly(connection_factory or _connection_factory())
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="threatcasting",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT plan.id, plan.plan_name, plan.future_state_description,
                          plan.current_gap_analysis, plan.created_at, plan.updated_at,
                          narrative.id AS narrative_id, narrative.narrative_type,
                          narrative.title AS narrative_title,
                          threat.id AS threat_id, threat.threat_name,
                          COUNT(milestone.id) AS milestone_count,
                          COUNT(milestone.id) FILTER (
                              WHERE milestone.milestone_status = 'completed'
                          ) AS completed_milestone_count,
                          COUNT(milestone.id) FILTER (
                              WHERE milestone.milestone_status = 'blocked'
                          ) AS blocked_milestone_count
                     FROM public.backcast_plan AS plan
                     JOIN public.threat_narrative AS narrative
                       ON narrative.id = plan.narrative_id
                     JOIN public.threat AS threat
                       ON threat.id = narrative.threat_id
                      AND threat.location_id = plan.location_id
                     LEFT JOIN public.threat_backcast_plan AS milestone
                       ON milestone.plan_id = plan.id
                    WHERE plan.location_id = %s::uuid
                      AND (%s::timestamptz IS NULL OR
                           (plan.created_at, plan.id) <
                           (%s::timestamptz, %s::uuid))
                    GROUP BY plan.id, narrative.id, threat.id
                    ORDER BY plan.created_at DESC, plan.id DESC
                    LIMIT %s""",
                (location_id, before_created_at, before_created_at, before_plan_id, page_size + 1),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]

        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = {
                "created_at": last["created_at"].isoformat(),
                "plan_id": str(last["id"]),
            }
        return {
            "location_id": location_id,
            "advisory_only": True,
            "items": items,
            "next_cursor": next_cursor,
        }
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_backcast_plan(
    operator_id: str,
    location_id: str,
    plan_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Read one plan and its evidence-bearing milestones in the granted location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    plan_id = _normalize_uuid(plan_id, "plan")
    connection = _open_readonly(connection_factory or _connection_factory())
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="threatcasting",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT plan.id, plan.location_id, plan.plan_name,
                          plan.future_state_description, plan.current_gap_analysis,
                          plan.created_at, plan.updated_at,
                          narrative.id AS narrative_id, narrative.narrative_type,
                          narrative.title AS narrative_title,
                          threat.id AS threat_id, threat.threat_name
                     FROM public.backcast_plan AS plan
                     JOIN public.threat_narrative AS narrative
                       ON narrative.id = plan.narrative_id
                     JOIN public.threat AS threat
                       ON threat.id = narrative.threat_id
                      AND threat.location_id = plan.location_id
                    WHERE plan.id = %s::uuid
                      AND plan.location_id = %s::uuid""",
                (plan_id, location_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            plan = _mapping(cursor, row)

            cursor.execute(
                """SELECT milestone.id, milestone.milestone_order,
                          milestone.milestone_description,
                          milestone.milestone_target_date,
                          milestone.milestone_status, milestone.dependencies,
                          milestone.responsible_party,
                          milestone.resource_requirements,
                          milestone.completion_evidence,
                          milestone.created_at, milestone.updated_at
                     FROM public.threat_backcast_plan AS milestone
                     JOIN public.backcast_plan AS plan
                       ON plan.id = milestone.plan_id
                      AND plan.location_id = %s::uuid
                    WHERE milestone.plan_id = %s::uuid
                    ORDER BY milestone.milestone_order, milestone.id
                    LIMIT %s""",
                (location_id, plan_id, _MAX_DETAIL_MILESTONES + 1),
            )
            milestone_rows = [_mapping(cursor, item) for item in cursor.fetchall()]
            if len(milestone_rows) > _MAX_DETAIL_MILESTONES:
                raise ThreatcastingReadInvalid(
                    "Plan exceeds the maximum readable milestone count"
                )
        plan["milestones"] = milestone_rows
        plan["advisory_only"] = True
        return plan
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
