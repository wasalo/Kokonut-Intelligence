"""Human-only governed transitions for Field Collector farm activity drafts."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID


class FarmActivityTransitionInvalid(ValueError):
    """Raised when a requested human decision is malformed."""


class FarmActivityTransitionConflict(RuntimeError):
    """Raised when the current lifecycle state cannot accept a decision."""


class FarmActivityDraftEditInvalid(ValueError):
    """Raised when a draft edit is malformed or does not match its form revision."""


class FarmActivityDraftEditConflict(RuntimeError):
    """Raised when a draft is no longer editable or its audit event is missing."""


_TRANSITIONS = {
    "submit": ("submit", "submitted", "submitted", {"draft"}, False),
    "verify": ("verify", "verified", "verified", {"submitted"}, False),
    "reject": ("reject", "rejected", "rejected", {"submitted", "verified"}, True),
    "request-rework": ("rework", "rework_requested", "draft", {"rejected"}, True),
    "publish": ("publish", "published", "published", {"verified"}, False),
    "close-exception": ("close_exception", "exception_closed", "rejected", {"rejected"}, True),
}


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_ids(operator_id: str, activity_id: str, location_id: str) -> tuple[str, str, str]:
    try:
        return str(UUID(operator_id)), str(UUID(activity_id)), str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator, farm activity, or location identifier") from exc


def _normalize_operator_location(operator_id: str, location_id: str) -> tuple[str, str]:
    try:
        return str(UUID(operator_id)), str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc


def _read_query(conn, sql: str, params: tuple) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL lock_timeout = '2s'")
        cur.execute(sql, params)
        columns = [description.name for description in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def list_farm_activities(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    connection_factory: Callable | None = None,
) -> list[dict]:
    """List the location's native Field Collector workflow records without free text."""
    operator_id, location_id = _normalize_operator_location(operator_id, location_id)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    conn = (connection_factory or _connection_factory())()
    try:
        rows = _read_query(
            conn,
            """SELECT activity.id, activity.location_id, activity.activity_type,
                          activity.activity_date, activity.status, activity.created_at,
                          activity.updated_at,
                          farm_activity_source_eligible_for_use(
                              activity.source_system, activity.source_id,
                              activity.source_raw, activity.location_id
                          ) AS eligible_for_use,
                          CASE
                              WHEN farm_activity_source_eligible_for_use(
                                  activity.source_system, activity.source_id,
                                  activity.source_raw, activity.location_id
                              ) THEN 'eligible'
                              ELSE COALESCE(
                                  NULLIF(eligibility.eligibility_reason, 'eligible'),
                                  'source_not_eligible'
                              )
                          END AS eligibility_reason,
                          EXISTS (
                              SELECT 1 FROM farm_activity_workflow_event AS event
                               WHERE event.farm_activity_id = activity.id
                                 AND event.action = 'exception_closed'
                          ) AS exception_closed
                     FROM farm_activity AS activity
                     LEFT JOIN offline_collection AS collection
                       ON collection.id = CASE
                           WHEN activity.source_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                           THEN activity.source_id::uuid
                           ELSE NULL::uuid
                       END
                      AND collection.location_id = activity.location_id
                     LEFT JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = collection.id
                    WHERE activity.location_id = %s::uuid
                      AND activity.source_system = 'field_collector'
                      AND activity.source_raw->>'form_id' = 'farm_activity_v1'
                      AND activity.source_raw->>'form_version' = '1.2.0'
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'farm_activity'
                             AND grant_row.action = 'read'
                             AND grant_row.location_id = activity.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                    ORDER BY activity.updated_at DESC, activity.id DESC
                    LIMIT %s""",
            (location_id, operator_id, limit),
        )
        for row in rows:
            row["id"] = str(row["id"])
            row["location_id"] = str(row["location_id"])
            row["activity_date"] = row["activity_date"].isoformat()
            for field in ("created_at", "updated_at"):
                row[field] = row[field].isoformat() if row[field] else None
        return rows
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_farm_activity(
    operator_id: str,
    activity_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Read bounded canonical content and its human decision history by location."""
    operator_id, activity_id, location_id = _normalize_ids(operator_id, activity_id, location_id)
    conn = (connection_factory or _connection_factory())()
    try:
        rows = _read_query(
            conn,
            """SELECT activity.id, activity.location_id, activity.activity_type,
                          activity.activity_date, activity.description,
                          activity.labor_hours, activity.notes, activity.status,
                          activity.created_at, activity.updated_at,
                          farm_activity_source_eligible_for_use(
                              activity.source_system, activity.source_id,
                              activity.source_raw, activity.location_id
                          ) AS eligible_for_use,
                          CASE
                              WHEN farm_activity_source_eligible_for_use(
                                  activity.source_system, activity.source_id,
                                  activity.source_raw, activity.location_id
                              ) THEN 'eligible'
                              ELSE COALESCE(
                                  NULLIF(eligibility.eligibility_reason, 'eligible'),
                                  'source_not_eligible'
                              )
                          END AS eligibility_reason,
                          (
                              SELECT COUNT(*) > 100
                                FROM farm_activity_workflow_event AS event
                               WHERE event.farm_activity_id = activity.id
                                 AND event.location_id = activity.location_id
                          ) AS workflow_events_truncated,
                          COALESCE((
                              SELECT jsonb_agg(jsonb_build_object(
                                  'action', bounded.action,
                                  'from_status', bounded.from_status,
                                  'to_status', bounded.to_status,
                                  'reason', bounded.reason,
                                  'actor_operator_id', bounded.actor_operator_id::text,
                                  'created_at', bounded.created_at
                              ) ORDER BY bounded.created_at, bounded.id)
                                FROM LATERAL (
                                    SELECT event.id, event.action, event.from_status,
                                           event.to_status, event.reason,
                                           event.actor_operator_id, event.created_at
                                      FROM farm_activity_workflow_event AS event
                                     WHERE event.farm_activity_id = activity.id
                                       AND event.location_id = activity.location_id
                                     ORDER BY event.created_at DESC, event.id DESC
                                     LIMIT 100
                                ) AS bounded
                          ), '[]'::jsonb) AS workflow_events
                     FROM farm_activity AS activity
                     LEFT JOIN offline_collection AS collection
                       ON collection.id = CASE
                           WHEN activity.source_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                           THEN activity.source_id::uuid
                           ELSE NULL::uuid
                       END
                      AND collection.location_id = activity.location_id
                     LEFT JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = collection.id
                    WHERE activity.id = %s::uuid
                      AND activity.location_id = %s::uuid
                      AND activity.source_system = 'field_collector'
                      AND activity.source_raw->>'form_id' = 'farm_activity_v1'
                      AND activity.source_raw->>'form_version' = '1.2.0'
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'farm_activity'
                             AND grant_row.action = 'read_detail'
                             AND grant_row.location_id = activity.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS detail_grant
                           WHERE detail_grant.operator_id = %s::uuid
                             AND detail_grant.resource = 'mobile_collection_review'
                             AND detail_grant.action = 'read_detail'
                             AND detail_grant.location_id = activity.location_id
                             AND operator_scope_grant_allows(
                                 detail_grant.operator_id, detail_grant.resource,
                                 detail_grant.action, detail_grant.location_id
                             )
                             AND detail_grant.revoked_at IS NULL
                      )
                    LIMIT 1""",
            (activity_id, location_id, operator_id, operator_id),
        )
        if not rows:
            return None
        row = rows[0]
        row["id"] = str(row["id"])
        row["location_id"] = str(row["location_id"])
        row["activity_date"] = row["activity_date"].isoformat()
        for field in ("created_at", "updated_at"):
            row[field] = row[field].isoformat() if row[field] else None
        row["workflow_events"] = [
            {
                **event,
                "created_at": event["created_at"].isoformat()
                if hasattr(event["created_at"], "isoformat")
                else event["created_at"],
            }
            for event in (row["workflow_events"] or [])
        ]
        return row
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def edit_farm_activity_draft(
    operator_id: str,
    activity_id: str,
    location_id: str,
    content_patch: dict,
    reason: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Edit a native draft against its immutable source schema and audit the change."""
    operator_id, activity_id, location_id = _normalize_ids(operator_id, activity_id, location_id)
    allowed_fields = {"activity_type", "activity_date", "description", "labor_hours", "notes"}
    if not isinstance(content_patch, dict) or not content_patch:
        raise FarmActivityDraftEditInvalid("Provide at least one farm activity field to edit")
    if set(content_patch) - allowed_fields:
        raise FarmActivityDraftEditInvalid("Draft edits accept only fields from the farm activity form")
    if not isinstance(reason, str) or not reason.strip():
        raise FarmActivityDraftEditInvalid("A correction reason is required")
    normalized_reason = reason.strip()
    if len(normalized_reason) > 2000:
        raise FarmActivityDraftEditInvalid("Correction reason exceeds 2000 characters")

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            cur.execute(
                "SELECT set_config('kokonut.actor_id', %s, true), "
                "set_config('kokonut.actor_type', 'operator', true), "
                "set_config('kokonut.workflow_action', 'draft_edited', true), "
                "set_config('kokonut.workflow_reason', %s, true)",
                (operator_id, normalized_reason),
            )
            cur.execute(
                """SELECT id::text, source_id, location_id::text, status::text,
                          source_system, source_raw->>'form_id',
                          source_raw->>'form_version', activity_type,
                          activity_date, description, labor_hours, notes,
                          farm_activity_source_eligible_for_use(
                              source_system, source_id, source_raw, location_id
                          ) AS eligible_for_use
                     FROM farm_activity
                    WHERE id = %s::uuid
                      AND location_id = %s::uuid
                      AND source_system = 'field_collector'
                      AND source_raw->>'form_id' = 'farm_activity_v1'
                      AND source_raw->>'form_version' = '1.2.0'
                    FOR UPDATE""",
                (activity_id, location_id),
            )
            activity = cur.fetchone()
            if activity is None:
                conn.rollback()
                return None
            if activity[3] != "draft":
                raise FarmActivityDraftEditConflict("Only a draft farm activity can be edited")
            if activity[12] is not True:
                raise FarmActivityDraftEditConflict(
                    "The source form, consent, or review state blocks further use pending human disposition"
                )

            cur.execute(
                """SELECT resource, action
                     FROM operator_scope_grant AS grant_row
                    WHERE grant_row.operator_id = %s::uuid
                      AND grant_row.location_id = %s::uuid
                      AND grant_row.revoked_at IS NULL
                      AND operator_scope_grant_allows(
                          grant_row.operator_id, grant_row.resource,
                          grant_row.action, grant_row.location_id
                      )
                      AND (
                          (resource = 'farm_activity' AND action IN ('edit_draft', 'read_detail'))
                          OR (resource = 'mobile_collection_review' AND action = 'read_detail')
                      )
                    FOR SHARE""",
                (operator_id, location_id),
            )
            grants = {(row[0], row[1]) for row in cur.fetchall()}
            required_grants = {
                ("farm_activity", "edit_draft"),
                ("farm_activity", "read_detail"),
                ("mobile_collection_review", "read_detail"),
            }
            if not required_grants.issubset(grants):
                conn.rollback()
                return None

            try:
                source_collection_id = str(UUID(str(activity[1])))
            except (TypeError, ValueError) as exc:
                raise FarmActivityDraftEditConflict("The draft source lineage is unavailable") from exc
            cur.execute(
                """SELECT revision.form_schema
                     FROM offline_collection AS collection
                     JOIN mobile_form_version AS revision
                       ON revision.id = collection.form_revision_id
                    WHERE collection.id = %s::uuid
                      AND collection.location_id = %s::uuid
                      AND collection.form_id = 'farm_activity_v1'
                      AND collection.form_version = '1.2.0'
                      AND revision.form_id = 'farm_activity_v1'
                      AND revision.version = '1.2.0'
                    FOR SHARE OF collection, revision""",
                (source_collection_id, location_id),
            )
            revision = cur.fetchone()
            if revision is None:
                raise FarmActivityDraftEditConflict("The immutable source form revision is unavailable")

            payload = {
                "activity_type": activity[7],
                "activity_date": activity[8].isoformat(),
            }
            for field, value in (
                ("description", activity[9]),
                ("labor_hours", activity[10]),
                ("notes", activity[11]),
            ):
                if value is not None:
                    payload[field] = float(value) if field == "labor_hours" else value
            for field, value in content_patch.items():
                if value is None:
                    if field in {"activity_type", "activity_date"}:
                        raise FarmActivityDraftEditInvalid(f"{field} cannot be cleared")
                    payload.pop(field, None)
                else:
                    payload[field] = value

            if "labor_hours" in payload:
                try:
                    labor_number = float(payload["labor_hours"])
                except (TypeError, ValueError, OverflowError) as exc:
                    raise FarmActivityDraftEditInvalid("Labor hours must be a finite number") from exc
                if not math.isfinite(labor_number):
                    raise FarmActivityDraftEditInvalid("Labor hours must be a finite number")
                payload["labor_hours"] = labor_number

            from services.mobile.form_validation import (
                FormPayloadInvalid,
                FormSchemaUnavailable,
                validate_form_payload,
            )

            try:
                validate_form_payload(revision[0], payload)
            except FormPayloadInvalid as exc:
                raise FarmActivityDraftEditInvalid(
                    "Draft content does not match its immutable farm activity form revision"
                ) from exc
            except FormSchemaUnavailable as exc:
                raise FarmActivityDraftEditConflict(
                    "The immutable source form schema cannot be evaluated"
                ) from exc

            try:
                activity_date = date.fromisoformat(payload["activity_date"])
                labor_hours = (
                    Decimal(str(payload["labor_hours"]))
                    if "labor_hours" in payload
                    else None
                )
            except (TypeError, ValueError, InvalidOperation) as exc:
                raise FarmActivityDraftEditInvalid("Draft date or labor value is invalid") from exc
            if labor_hours is not None:
                try:
                    representable_labor_hours = labor_hours.quantize(Decimal("0.01"))
                except InvalidOperation as exc:
                    raise FarmActivityDraftEditInvalid(
                        "Labor hours exceed the canonical field precision"
                    ) from exc
                if (
                    not labor_hours.is_finite()
                    or labor_hours < 0
                    or labor_hours > Decimal("999999.99")
                    or representable_labor_hours != labor_hours
                ):
                    raise FarmActivityDraftEditInvalid(
                        "Labor hours must fit the canonical field precision of two decimal places"
                    )

            updated_values = (
                payload["activity_type"],
                activity_date,
                payload.get("description"),
                labor_hours,
                payload.get("notes"),
            )
            current_values = (activity[7], activity[8], activity[9], activity[10], activity[11])
            if updated_values == current_values:
                raise FarmActivityDraftEditInvalid("The edit does not change any farm activity fields")

            cur.execute(
                """UPDATE farm_activity
                      SET activity_type = %s,
                          activity_date = %s,
                          description = %s,
                          labor_hours = %s,
                          notes = %s,
                          updated_at = NOW()
                    WHERE id = %s::uuid""",
                (*updated_values, activity_id),
            )
            cur.execute(
                """SELECT id::text, action, from_status, to_status, reason,
                          metadata->'changed_fields', created_at
                     FROM farm_activity_workflow_event
                    WHERE farm_activity_id = %s::uuid
                      AND location_id = %s::uuid
                      AND actor_operator_id = %s::uuid
                      AND action = 'draft_edited'
                      AND from_status = 'draft'
                      AND to_status = 'draft'
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1""",
                (activity_id, location_id, operator_id),
            )
            event = cur.fetchone()
            if event is None:
                raise FarmActivityDraftEditConflict("Farm activity edit evidence was not recorded")

        conn.commit()
        return {
            "event_id": str(event[0]),
            "activity_id": activity_id,
            "location_id": location_id,
            "action": event[1],
            "from_status": event[2],
            "to_status": event[3],
            "reason": event[4],
            "changed_fields": event[5],
            "created_at": event[6].isoformat() if hasattr(event[6], "isoformat") else str(event[6]),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def transition_farm_activity(
    operator_id: str,
    activity_id: str,
    location_id: str,
    action: str,
    reason: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Apply one authorized decision to a Field Collector activity.

    PostgreSQL guards the transition and writes its append-only workflow event
    in the same transaction. The route supplies the OIDC operator identity;
    device and participant identities are never substituted for it.
    """
    operator_id, activity_id, location_id = _normalize_ids(operator_id, activity_id, location_id)
    transition = _TRANSITIONS.get(action)
    if transition is None:
        raise FarmActivityTransitionInvalid("Unsupported farm activity transition")
    grant_action, event_action, to_status, allowed_from, reason_required = transition

    if reason is not None and not isinstance(reason, str):
        raise FarmActivityTransitionInvalid("Transition reason must be text")
    normalized_reason = reason.strip() if isinstance(reason, str) else ""
    if len(normalized_reason) > 2000:
        raise FarmActivityTransitionInvalid("Transition reason exceeds 2000 characters")
    if reason_required and not normalized_reason:
        raise FarmActivityTransitionInvalid("A reason is required for this transition")

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            cur.execute(
                "SELECT set_config('kokonut.actor_id', %s, true), "
                "set_config('kokonut.actor_type', 'operator', true), "
                "set_config('kokonut.workflow_action', %s, true), "
                "set_config('kokonut.workflow_reason', %s, true)",
                (operator_id, event_action, normalized_reason),
            )
            cur.execute(
                """SELECT id::text, location_id::text, status::text, source_system,
                          farm_activity_source_eligible_for_use(
                              source_system, source_id, source_raw, location_id
                          ) AS eligible_for_use
                     FROM farm_activity
                    WHERE id = %s::uuid
                      AND location_id = %s::uuid
                      AND source_system = 'field_collector'
                      AND source_raw->>'form_id' = 'farm_activity_v1'
                      AND source_raw->>'form_version' = '1.2.0'
                    FOR UPDATE""",
                (activity_id, location_id),
            )
            activity = cur.fetchone()
            if activity is None:
                conn.rollback()
                return None
            if activity[2] not in allowed_from:
                raise FarmActivityTransitionConflict("Farm activity is not in a state for this decision")
            if action in {"submit", "verify", "request-rework", "publish"} and activity[4] is not True:
                raise FarmActivityTransitionConflict(
                    "The source form, consent, or review state blocks further use pending human disposition"
                )

            cur.execute(
                """SELECT id FROM operator_scope_grant AS grant_row
                    WHERE grant_row.operator_id = %s::uuid
                      AND grant_row.resource = 'farm_activity'
                      AND grant_row.action = %s
                      AND grant_row.location_id = %s::uuid
                      AND grant_row.revoked_at IS NULL
                      AND operator_scope_grant_allows(
                          grant_row.operator_id, grant_row.resource,
                          grant_row.action, grant_row.location_id
                      )
                    FOR SHARE""",
                (operator_id, grant_action, location_id),
            )
            if cur.fetchone() is None:
                conn.rollback()
                return None

            cur.execute(
                "UPDATE farm_activity SET status = %s, updated_at = NOW() WHERE id = %s::uuid",
                (to_status, activity_id),
            )
            cur.execute(
                """SELECT id::text, action, from_status, to_status, reason, created_at
                     FROM farm_activity_workflow_event
                    WHERE farm_activity_id = %s::uuid
                      AND actor_operator_id = %s::uuid
                      AND action = %s
                      AND from_status IS NOT DISTINCT FROM %s
                      AND to_status = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1""",
                (activity_id, operator_id, event_action, activity[2], to_status),
            )
            event = cur.fetchone()
            if event is None:
                raise FarmActivityTransitionConflict("Farm activity transition evidence was not recorded")

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
