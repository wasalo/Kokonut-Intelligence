"""Tenant-scoped Gateway operations for non-Field-Collector farm activities."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_EDITABLE_FIELDS = (
    "plot_id",
    "crop_cycle_id",
    "activity_type",
    "activity_date",
    "description",
    "labor_hours",
    "labor_cost",
    "materials_used",
    "evidence_urls",
    "notes",
)
_TRANSITIONS = {
    "submit": ("submit", "submitted", "submitted", {"draft"}, False),
    "verify": ("verify", "verified", "verified", {"submitted"}, False),
    "reject": ("reject", "rejected", "rejected", {"submitted", "verified"}, True),
    "request-rework": ("rework", "rework_requested", "draft", {"rejected"}, True),
    "publish": ("publish", "published", "published", {"verified"}, False),
    "close-exception": ("close_exception", "exception_closed", "rejected", {"rejected"}, True),
}


class FarmActivityRecordInvalid(ValueError):
    """Raised when a Gateway farm-activity operation is malformed."""


class FarmActivityRecordConflict(RuntimeError):
    """Raised when the record state cannot accept the requested operation."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_ids(operator_id: str, location_id: str, activity_id: str | None = None):
    try:
        values = (str(UUID(operator_id)), str(UUID(location_id)))
        return values if activity_id is None else (*values, str(UUID(activity_id)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator, location, or farm activity identifier") from exc


def _normalize_content(content: dict, *, creating: bool) -> dict:
    if not isinstance(content, dict):
        raise FarmActivityRecordInvalid("Farm activity content must be an object")
    if not content and not creating:
        raise FarmActivityRecordInvalid("Provide at least one farm activity field to edit")
    unknown = set(content) - set(_EDITABLE_FIELDS)
    if unknown:
        raise FarmActivityRecordInvalid("Farm activity content contains a protected or unsupported field")
    if creating and not {"activity_type", "activity_date"}.issubset(content):
        raise FarmActivityRecordInvalid("New farm activities require activity_type and activity_date")

    normalized = {}
    for field, value in content.items():
        if field in {"plot_id", "crop_cycle_id"}:
            if value is None:
                normalized[field] = None
                continue
            try:
                normalized[field] = str(UUID(value))
            except (TypeError, ValueError) as exc:
                raise FarmActivityRecordInvalid(f"{field} must be a UUID or null") from exc
        elif field == "activity_type":
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
                raise FarmActivityRecordInvalid("activity_type must contain 1 to 100 characters")
            normalized[field] = value.strip()
        elif field == "activity_date":
            try:
                normalized[field] = date.fromisoformat(value) if isinstance(value, str) else None
            except ValueError as exc:
                raise FarmActivityRecordInvalid("activity_date must be an ISO date") from exc
            if normalized[field] is None:
                raise FarmActivityRecordInvalid("activity_date must be an ISO date")
        elif field in {"description", "notes"}:
            if value is not None and (not isinstance(value, str) or len(value) > 10000):
                raise FarmActivityRecordInvalid(f"{field} must be text of at most 10000 characters")
            normalized[field] = value
        elif field in {"labor_hours", "labor_cost"}:
            if value is None:
                normalized[field] = None
                continue
            try:
                amount = Decimal(str(value))
                representable = amount.quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError) as exc:
                raise FarmActivityRecordInvalid(f"{field} must be a finite decimal") from exc
            maximum = Decimal("999999.99") if field == "labor_hours" else Decimal("9999999999.99")
            if not amount.is_finite() or amount < 0 or amount > maximum or representable != amount:
                raise FarmActivityRecordInvalid(f"{field} must be non-negative with at most two decimal places")
            normalized[field] = amount
        elif field == "materials_used":
            if value is None:
                normalized[field] = []
                continue
            if not isinstance(value, (dict, list)):
                raise FarmActivityRecordInvalid("materials_used must be an object or array")
            try:
                encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
            except (TypeError, ValueError) as exc:
                raise FarmActivityRecordInvalid("materials_used must contain valid JSON values") from exc
            if len(encoded) > 65536:
                raise FarmActivityRecordInvalid("materials_used exceeds the 65536-character limit")
            normalized[field] = value
        elif field == "evidence_urls":
            if value is None:
                normalized[field] = []
            elif (
                not isinstance(value, list)
                or len(value) > 100
                or any(not isinstance(url, str) or not url or len(url) > 2048 for url in value)
            ):
                raise FarmActivityRecordInvalid("evidence_urls must be up to 100 bounded text values")
            else:
                normalized[field] = value
    return normalized


def _set_context(conn, operator_id: str, location_id: str, action: str, *, extra_scopes=()):
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL lock_timeout = '2s'")
    set_operator_tenant_context(
        conn,
        operator_id=operator_id,
        location_id=location_id,
        resource="farm_activity",
        action=action,
        required_scopes=tuple(extra_scopes),
    )


def _set_actor_action(conn, operator_id: str, action: str, reason: str = ""):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('kokonut.actor_id', %s, true), "
            "set_config('kokonut.actor_type', 'operator', true), "
            "set_config('kokonut.workflow_action', %s, true), "
            "set_config('kokonut.workflow_reason', %s, true)",
            (operator_id, action, reason),
        )


def _activity_result(row) -> dict:
    names = (
        "id", "location_id", "plot_id", "crop_cycle_id", "activity_type", "activity_date",
        "description", "labor_hours", "labor_cost", "materials_used", "evidence_urls",
        "notes", "status", "source_system", "created_at", "updated_at",
    )
    result = dict(zip(names, row))
    for field in ("id", "location_id", "plot_id", "crop_cycle_id"):
        if result[field] is not None:
            result[field] = str(result[field])
    if result["activity_date"] is not None:
        result["activity_date"] = result["activity_date"].isoformat()
    for field in ("created_at", "updated_at"):
        if result[field] is not None:
            result[field] = result[field].isoformat()
    return result


def _activity_summary_result(row) -> dict:
    names = (
        "id", "location_id", "plot_id", "crop_cycle_id", "activity_type",
        "activity_date", "status", "source_system", "created_at", "updated_at",
    )
    result = dict(zip(names, row))
    for field in ("id", "location_id", "plot_id", "crop_cycle_id"):
        if result[field] is not None:
            result[field] = str(result[field])
    if result["activity_date"] is not None:
        result["activity_date"] = result["activity_date"].isoformat()
    for field in ("created_at", "updated_at"):
        if result[field] is not None:
            result[field] = result[field].isoformat()
    return result


def list_farm_activity_records(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    published_only: bool = False,
    connection_factory: Callable | None = None,
) -> list[dict]:
    operator_id, location_id = _normalize_ids(operator_id, location_id)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    grant_action = "read_published" if published_only else "read"
    conn = (connection_factory or _connection_factory())()
    try:
        # The signed tenant-context setter takes row locks so a grant or owner
        # transfer cannot race this request. PostgreSQL rejects SELECT FOR
        # SHARE after a transaction is marked read-only, so keep data access
        # read-only after context setup and always roll the transaction back.
        _set_context(conn, operator_id, location_id, grant_action)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, location_id, plot_id, crop_cycle_id, activity_type,
                          activity_date, status, source_system, created_at, updated_at
                     FROM farm_activity
                    WHERE location_id = %s::uuid
                      AND source_system IS DISTINCT FROM 'field_collector'
                      AND (%s::boolean IS FALSE OR status IN ('verified', 'published'))
                    ORDER BY updated_at DESC NULLS LAST, id DESC
                    LIMIT %s""",
                (location_id, published_only, limit),
            )
            return [_activity_summary_result(row) for row in cur.fetchall()]
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_farm_activity_record(
    operator_id: str,
    activity_id: str,
    location_id: str,
    *,
    published_only: bool = False,
    connection_factory: Callable | None = None,
) -> dict | None:
    operator_id, location_id, activity_id = _normalize_ids(operator_id, location_id, activity_id)
    grant_action = "read_published_detail" if published_only else "read_detail"
    conn = (connection_factory or _connection_factory())()
    try:
        _set_context(conn, operator_id, location_id, grant_action)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT activity.id, activity.location_id, activity.plot_id,
                          activity.crop_cycle_id, activity.activity_type,
                          activity.activity_date, activity.description,
                          activity.labor_hours, activity.labor_cost,
                          activity.materials_used, activity.evidence_urls, activity.notes,
                          activity.status, activity.source_system,
                          activity.created_at, activity.updated_at,
                          COALESCE((
                              SELECT jsonb_agg(jsonb_build_object(
                                  'action', bounded.action,
                                  'from_status', bounded.from_status,
                                  'to_status', bounded.to_status,
                                  'reason', bounded.reason,
                                  'actor_operator_id', bounded.actor_operator_id::text,
                                  'changed_fields', bounded.metadata->'changed_fields',
                                  'created_at', bounded.created_at
                              ) ORDER BY bounded.created_at, bounded.id)
                                FROM LATERAL (
                                    SELECT event.id, event.action, event.from_status,
                                           event.to_status, event.reason,
                                           event.actor_operator_id, event.metadata,
                                           event.created_at
                                      FROM farm_activity_operator_event AS event
                                     WHERE event.farm_activity_id = activity.id
                                       AND event.location_id = activity.location_id
                                     ORDER BY event.created_at DESC, event.id DESC
                                     LIMIT 100
                                ) AS bounded
                          ), '[]'::jsonb) AS operator_events
                     FROM farm_activity AS activity
                    WHERE activity.id = %s::uuid
                      AND activity.location_id = %s::uuid
                      AND activity.source_system IS DISTINCT FROM 'field_collector'
                      AND (%s::boolean IS FALSE OR activity.status IN ('verified', 'published'))""",
                (activity_id, location_id, published_only),
            )
            row = cur.fetchone()
        if row is None:
            return None
        result = _activity_result(row[:16])
        result["operator_events"] = [
            {
                **event,
                "created_at": event["created_at"].isoformat()
                if hasattr(event["created_at"], "isoformat")
                else event["created_at"],
            }
            for event in (row[16] or [])
        ]
        return result
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def create_farm_activity_record(
    operator_id: str,
    location_id: str,
    content: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    operator_id, location_id = _normalize_ids(operator_id, location_id)
    values = _normalize_content(content, creating=True)
    values.setdefault("materials_used", [])
    values.setdefault("evidence_urls", [])
    columns = ("location_id", *_EDITABLE_FIELDS)
    params = [location_id]
    for field in _EDITABLE_FIELDS:
        value = values.get(field)
        params.append(json.dumps(value, separators=(",", ":")) if field == "materials_used" else value)

    conn = (connection_factory or _connection_factory())()
    try:
        _set_context(
            conn, operator_id, location_id, "create_draft",
            extra_scopes=(("farm_activity", "read_detail"),),
        )
        _set_actor_action(conn, operator_id, "draft_created")
        with conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO farm_activity (
                        {", ".join(columns)}, status, schema_version, source_system,
                        created_by, updated_by
                    ) VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s,
                        %s::numeric, %s::numeric, %s::jsonb, %s::text[], %s,
                        'draft', 'gateway_v1', 'kokonut_gateway', %s::uuid, %s::uuid
                    )
                    RETURNING id, location_id, plot_id, crop_cycle_id, activity_type,
                              activity_date, description, labor_hours, labor_cost,
                              materials_used, evidence_urls, notes, status, source_system,
                              created_at, updated_at""",
                (*params, operator_id, operator_id),
            )
            row = cur.fetchone()
            activity = _activity_result(row)
            cur.execute(
                """SELECT id::text FROM farm_activity_operator_event
                    WHERE farm_activity_id = %s::uuid AND actor_operator_id = %s::uuid
                      AND action = 'draft_created'
                    ORDER BY created_at DESC, id DESC LIMIT 1""",
                (activity["id"], operator_id),
            )
            event = cur.fetchone()
            if event is None:
                raise FarmActivityRecordConflict("Farm activity creation evidence was not recorded")
        conn.commit()
        activity["event_id"] = str(event[0])
        return activity
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def edit_farm_activity_record_draft(
    operator_id: str,
    activity_id: str,
    location_id: str,
    content_patch: dict,
    reason: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    operator_id, location_id, activity_id = _normalize_ids(operator_id, location_id, activity_id)
    values = _normalize_content(content_patch, creating=False)
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000:
        raise FarmActivityRecordInvalid("Draft edits require a correction reason of at most 2000 characters")
    normalized_reason = reason.strip()
    conn = (connection_factory or _connection_factory())()
    try:
        _set_context(
            conn, operator_id, location_id, "edit_draft",
            extra_scopes=(("farm_activity", "read_detail"),),
        )
        _set_actor_action(conn, operator_id, "draft_edited", normalized_reason)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM farm_activity
                    WHERE id = %s::uuid AND location_id = %s::uuid
                      AND status = 'draft'
                      AND source_system IS DISTINCT FROM 'field_collector'
                    FOR UPDATE""",
                (activity_id, location_id),
            )
            if cur.fetchone() is None:
                conn.rollback()
                return None
            assignments = []
            params = []
            for field in _EDITABLE_FIELDS:
                if field not in values:
                    continue
                value = values[field]
                if field == "materials_used":
                    value = json.dumps(value, separators=(",", ":"))
                    assignments.append(f"{field} = %s::jsonb")
                elif field == "evidence_urls":
                    assignments.append(f"{field} = %s::text[]")
                else:
                    assignments.append(f"{field} = %s")
                params.append(value)
            cur.execute(
                f"""UPDATE farm_activity SET {", ".join(assignments)}, updated_at = NOW()
                    WHERE id = %s::uuid AND location_id = %s::uuid
                    RETURNING id, location_id, plot_id, crop_cycle_id, activity_type,
                              activity_date, description, labor_hours, labor_cost,
                              materials_used, evidence_urls, notes, status, source_system,
                              created_at, updated_at""",
                (*params, activity_id, location_id),
            )
            activity = _activity_result(cur.fetchone())
            cur.execute(
                """SELECT id::text FROM farm_activity_operator_event
                    WHERE farm_activity_id = %s::uuid AND actor_operator_id = %s::uuid
                      AND action = 'draft_edited'
                    ORDER BY created_at DESC, id DESC LIMIT 1""",
                (activity_id, operator_id),
            )
            event = cur.fetchone()
            if event is None:
                raise FarmActivityRecordConflict("Farm activity draft edit evidence was not recorded")
        conn.commit()
        activity["event_id"] = str(event[0])
        return activity
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def transition_farm_activity_record(
    operator_id: str,
    activity_id: str,
    location_id: str,
    action: str,
    reason: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    operator_id, location_id, activity_id = _normalize_ids(operator_id, location_id, activity_id)
    transition = _TRANSITIONS.get(action)
    if transition is None:
        raise FarmActivityRecordInvalid("Unsupported farm activity transition")
    grant_action, event_action, to_status, allowed_from, reason_required = transition
    if reason is not None and not isinstance(reason, str):
        raise FarmActivityRecordInvalid("Transition reason must be text")
    normalized_reason = reason.strip() if isinstance(reason, str) else ""
    if len(normalized_reason) > 2000 or (reason_required and not normalized_reason):
        raise FarmActivityRecordInvalid("This transition requires a reason of at most 2000 characters")

    conn = (connection_factory or _connection_factory())()
    try:
        _set_context(conn, operator_id, location_id, grant_action)
        _set_actor_action(conn, operator_id, event_action, normalized_reason)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status::text FROM farm_activity
                    WHERE id = %s::uuid AND location_id = %s::uuid
                      AND source_system IS DISTINCT FROM 'field_collector'
                    FOR UPDATE""",
                (activity_id, location_id),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return None
            from_status = row[0]
            if from_status not in allowed_from:
                raise FarmActivityRecordConflict("Farm activity is not in a state for this decision")

            if action == "verify":
                cur.execute(
                    """UPDATE farm_activity SET status = %s, verified_by = %s::uuid,
                              verified_at = NOW(), updated_at = NOW()
                        WHERE id = %s::uuid AND location_id = %s::uuid""",
                    (to_status, operator_id, activity_id, location_id),
                )
            elif action == "reject":
                cur.execute(
                    """UPDATE farm_activity SET status = %s, rejection_reason = %s,
                              updated_at = NOW()
                        WHERE id = %s::uuid AND location_id = %s::uuid""",
                    (to_status, normalized_reason, activity_id, location_id),
                )
            else:
                cur.execute(
                    """UPDATE farm_activity SET status = %s, updated_at = NOW()
                        WHERE id = %s::uuid AND location_id = %s::uuid""",
                    (to_status, activity_id, location_id),
                )
            cur.execute(
                """SELECT id::text, action, from_status, to_status, reason, created_at
                     FROM farm_activity_operator_event
                    WHERE farm_activity_id = %s::uuid AND actor_operator_id = %s::uuid
                      AND action = %s
                    ORDER BY created_at DESC, id DESC LIMIT 1""",
                (activity_id, operator_id, event_action),
            )
            event = cur.fetchone()
            if event is None:
                raise FarmActivityRecordConflict("Farm activity transition evidence was not recorded")
        conn.commit()
        return {
            "event_id": str(event[0]),
            "activity_id": activity_id,
            "location_id": location_id,
            "action": event[1],
            "from_status": event[2],
            "to_status": event[3],
            "reason": event[4],
            "created_at": event[5].isoformat() if hasattr(event[5], "isoformat") else str(event[5]),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
