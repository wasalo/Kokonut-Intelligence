"""Location-scoped Field Collector farm activity intake and draft promotion."""

from __future__ import annotations

import hashlib
import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.mobile.form_validation import (
    FormPayloadInvalid,
    FormSchemaUnavailable,
    validate_form_payload,
)


class FarmActivityPayloadTooLarge(ValueError):
    """Raised when a private intake payload exceeds the review response cap."""


class FarmActivityIntakeInvalid(ValueError):
    """Raised when a farm activity intake acknowledgement is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_ids(operator_id: str, location_id: str) -> tuple[str, str]:
    try:
        return str(UUID(operator_id)), str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc


def _normalize_collection_ids(
    operator_id: str, collection_id: str, location_id: str
) -> tuple[str, str, str]:
    try:
        return str(UUID(operator_id)), str(UUID(collection_id)), str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator, collection, or location identifier") from exc


def _read_rows(conn, sql: str, params: tuple) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL lock_timeout = '2s'")
        cur.execute(sql, params)
        columns = [description.name for description in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def list_farm_activity_intake(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    connection_factory: Callable | None = None,
) -> list[dict]:
    """List eligible, unpromoted farm activity captures without free text."""
    operator_id, location_id = _normalize_ids(operator_id, location_id)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    conn = (connection_factory or _connection_factory())()
    try:
        rows = _read_rows(
            conn,
            """SELECT oc.id, oc.location_id, oc.form_id, oc.form_version,
                          oc.collected_at, oc.synced_at,
                          oc.payload->>'activity_type' AS activity_type,
                          oc.payload->>'activity_date' AS activity_date,
                          eligibility.eligible_for_use
                     FROM offline_collection AS oc
                     JOIN mobile_form_version AS revision
                       ON revision.id = oc.form_revision_id
                     JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = oc.id
                    WHERE oc.location_id = %s::uuid
                      AND oc.form_id = 'farm_activity_v1'
                      AND oc.form_version = '1.2.0'
                      AND oc.collection_type = 'farm_activity'
                      AND oc.sync_status = 'synced'
                      AND oc.form_validation_status = 'active'
                      AND oc.form_review_required = FALSE
                      AND oc.consent_validation_status = 'not_required'
                      AND revision.status = 'active'
                      AND revision.consent_policy_status = 'not_required'
                      AND eligibility.eligible_for_use = TRUE
                      AND NOT EXISTS (
                          SELECT 1 FROM farm_activity AS activity
                           WHERE activity.source_system = 'field_collector'
                             AND activity.source_id = oc.id::text
                      )
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'farm_activity'
                             AND grant_row.action = 'read'
                             AND grant_row.location_id = oc.location_id
                             AND grant_row.revoked_at IS NULL
                      )
                    ORDER BY oc.collected_at DESC, oc.id DESC
                    LIMIT %s""",
            (location_id, operator_id, limit),
        )
        return [
            {
                **row,
                "id": str(row["id"]),
                "location_id": str(row["location_id"]),
                "collected_at": row["collected_at"].isoformat() if row["collected_at"] else None,
                "synced_at": row["synced_at"].isoformat() if row["synced_at"] else None,
            }
            for row in rows
        ]
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_farm_activity_intake(
    operator_id: str,
    collection_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Read one eligible intake payload under separate detail grants."""
    operator_id, collection_id, location_id = _normalize_collection_ids(
        operator_id, collection_id, location_id
    )
    conn = (connection_factory or _connection_factory())()
    try:
        rows = _read_rows(
            conn,
            """SELECT oc.id, oc.location_id, oc.form_id, oc.form_version,
                          oc.collection_type, oc.collected_at, oc.synced_at,
                          CASE WHEN octet_length(oc.payload::text) <= 524288
                               THEN oc.payload ELSE NULL::jsonb END AS payload,
                          octet_length(oc.payload::text) AS payload_size,
                          CASE WHEN jsonb_typeof(oc.photo_refs) = 'array'
                               THEN jsonb_array_length(oc.photo_refs) ELSE 0 END AS photo_count,
                          eligibility.eligible_for_use
                     FROM offline_collection AS oc
                     JOIN mobile_form_version AS revision
                       ON revision.id = oc.form_revision_id
                     JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = oc.id
                    WHERE oc.id = %s::uuid
                      AND oc.location_id = %s::uuid
                      AND oc.form_id = 'farm_activity_v1'
                      AND oc.form_version = '1.2.0'
                      AND oc.collection_type = 'farm_activity'
                      AND oc.sync_status = 'synced'
                      AND oc.form_validation_status = 'active'
                      AND oc.form_review_required = FALSE
                      AND oc.consent_validation_status = 'not_required'
                      AND revision.status = 'active'
                      AND revision.consent_policy_status = 'not_required'
                      AND eligibility.eligible_for_use = TRUE
                      AND NOT EXISTS (
                          SELECT 1 FROM farm_activity AS activity
                           WHERE activity.source_system = 'field_collector'
                             AND activity.source_id = oc.id::text
                      )
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'farm_activity'
                             AND grant_row.action = 'read_detail'
                             AND grant_row.location_id = oc.location_id
                             AND grant_row.revoked_at IS NULL
                      )
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS detail_grant
                           WHERE detail_grant.operator_id = %s::uuid
                             AND detail_grant.resource = 'mobile_collection_review'
                             AND detail_grant.action = 'read_detail'
                             AND detail_grant.location_id = oc.location_id
                             AND detail_grant.revoked_at IS NULL
                      )
                    LIMIT 1""",
            (collection_id, location_id, operator_id, operator_id),
        )
        if not rows:
            return None
        row = rows[0]
        if row["payload_size"] > 524_288:
            raise FarmActivityPayloadTooLarge("Farm activity intake exceeds the 512 KiB review limit")
        row.pop("payload_size", None)
        row["payload"] = _json_object(row["payload"])
        for field in ("id", "location_id"):
            row[field] = str(row[field])
        for field in ("collected_at", "synced_at"):
            row[field] = row[field].isoformat() if row[field] else None
        return row
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def create_farm_activity_draft(
    operator_id: str,
    collection_id: str,
    location_id: str,
    *,
    content_reviewed: bool,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Promote an eligible v1.2.0 capture to one canonical draft atomically.

    The caller must explicitly attest that the private text has been reviewed.
    Location is taken from the synced collection, never from its payload.
    """
    operator_id, collection_id, location_id = _normalize_collection_ids(
        operator_id, collection_id, location_id
    )
    if content_reviewed is not True:
        raise FarmActivityIntakeInvalid("Explicit content review is required before draft promotion")

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            cur.execute(
                "SELECT set_config('kokonut.actor_id', %s, true), "
                "set_config('kokonut.actor_type', 'operator', true)",
                (operator_id,),
            )
            cur.execute(
                """SELECT oc.id::text, oc.location_id::text, oc.form_id,
                          oc.form_version, oc.collection_type, oc.sync_status,
                          oc.form_validation_status, oc.consent_validation_status,
                          oc.form_review_required, oc.payload, revision.form_schema,
                          revision.status, revision.consent_policy_status,
                          oc.participant_link_id::text
                     FROM offline_collection AS oc
                     JOIN mobile_form_version AS revision
                       ON revision.id = oc.form_revision_id
                     JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = oc.id
                    WHERE oc.id = %s::uuid
                      AND oc.location_id = %s::uuid
                      AND oc.form_id = 'farm_activity_v1'
                      AND oc.form_version = '1.2.0'
                      AND oc.collection_type = 'farm_activity'
                      AND oc.sync_status = 'synced'
                      AND oc.form_validation_status = 'active'
                      AND oc.form_review_required = FALSE
                      AND oc.consent_validation_status = 'not_required'
                      AND revision.status = 'active'
                      AND revision.consent_policy_status = 'not_required'
                      AND eligibility.eligible_for_use = TRUE
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS create_grant
                           WHERE create_grant.operator_id = %s::uuid
                             AND create_grant.resource = 'farm_activity'
                             AND create_grant.action = 'create_draft'
                             AND create_grant.location_id = oc.location_id
                             AND create_grant.revoked_at IS NULL
                      )
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS detail_grant
                           WHERE detail_grant.operator_id = %s::uuid
                             AND detail_grant.resource = 'mobile_collection_review'
                             AND detail_grant.action = 'read_detail'
                             AND detail_grant.location_id = oc.location_id
                             AND detail_grant.revoked_at IS NULL
                      )
                    FOR UPDATE OF oc, revision""",
                (collection_id, location_id, operator_id, operator_id),
            )
            intake = cur.fetchone()
            if intake is None:
                conn.rollback()
                return None

            # Hold the participant-link row while creating a canonical draft.
            # A concurrent revocation must win before promotion or wait until
            # this transaction commits; checking the eligibility view alone
            # would leave a small read-to-write race.
            participant_link_id = intake[13]
            if participant_link_id is not None:
                cur.execute(
                    """SELECT id FROM mobile_participant_link
                        WHERE id = %s::uuid AND revoked_at IS NULL
                        FOR SHARE""",
                    (participant_link_id,),
                )
                if cur.fetchone() is None:
                    conn.rollback()
                    return None

            # Recheck and lock both grants for the duration of this write, so
            # a concurrent operator-grant revocation cannot race promotion.
            for resource, action in (
                ("farm_activity", "create_draft"),
                ("mobile_collection_review", "read_detail"),
            ):
                cur.execute(
                    """SELECT id FROM operator_scope_grant
                        WHERE operator_id = %s::uuid
                          AND resource = %s
                          AND action = %s
                          AND location_id = %s::uuid
                          AND revoked_at IS NULL
                        FOR SHARE""",
                    (operator_id, resource, action, intake[1]),
                )
                if cur.fetchone() is None:
                    conn.rollback()
                    return None

            payload = _json_object(intake[9])
            schema = _json_object(intake[10])
            try:
                validate_form_payload(schema, payload)
            except (FormPayloadInvalid, FormSchemaUnavailable) as exc:
                raise FarmActivityIntakeInvalid(
                    "The stored farm activity no longer matches its immutable form revision"
                ) from exc

            serialized_payload = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            payload_digest = hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()
            cur.execute(
                "SELECT set_config('kokonut.workflow_action', 'draft_created', true), "
                "set_config('kokonut.content_reviewed', 'true', true), "
                "set_config('kokonut.payload_sha256', %s, true)",
                (payload_digest,),
            )
            source_raw = {
                "form_id": "farm_activity_v1",
                "form_version": "1.2.0",
                "offline_collection_id": collection_id,
                "payload_sha256": payload_digest,
            }
            cur.execute(
                """INSERT INTO farm_activity (
                       location_id, activity_type, activity_date, description,
                       labor_hours, notes, status, schema_version, source_system,
                       source_id, source_raw
                   ) VALUES (
                       %s::uuid, %s, %s::date, %s, %s, %s, 'draft', '1.2.0',
                       'field_collector', %s, %s::jsonb
                   )
                   ON CONFLICT (source_system, source_id)
                       WHERE source_system = 'field_collector' AND source_id IS NOT NULL
                   DO NOTHING
                   RETURNING id::text, location_id::text, activity_type,
                             activity_date, status, source_system, source_id""",
                (
                    intake[1],
                    payload["activity_type"],
                    payload["activity_date"],
                    payload.get("description"),
                    payload.get("labor_hours"),
                    payload.get("notes"),
                    collection_id,
                    json.dumps(source_raw, sort_keys=True),
                ),
            )
            activity = cur.fetchone()
            created = activity is not None
            if not created:
                cur.execute(
                    """SELECT id::text, location_id::text, activity_type,
                              activity_date, status, source_system, source_id,
                              source_raw->>'payload_sha256'
                         FROM farm_activity
                        WHERE source_system = 'field_collector'
                          AND source_id = %s
                        FOR UPDATE""",
                    (collection_id,),
                )
                activity = cur.fetchone()
                if activity is None or activity[1] != intake[1] or activity[7] != payload_digest:
                    raise RuntimeError("Farm activity source identity conflicts with existing data")
                conn.commit()
                return {
                    "id": str(activity[0]),
                    "location_id": str(activity[1]),
                    "activity_type": activity[2],
                    "activity_date": activity[3].isoformat() if hasattr(activity[3], "isoformat") else str(activity[3]),
                    "status": activity[4],
                    "source_system": activity[5],
                    "source_id": activity[6],
                    "created": False,
                }

            cur.execute(
                """INSERT INTO farm_activity_workflow_event (
                       farm_activity_id, location_id, source_collection_id,
                       actor_operator_id, action, from_status, to_status, metadata
                   ) VALUES (
                       %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                       'draft_created', NULL, 'draft', %s::jsonb
                   )""",
                (
                    activity[0],
                    activity[1],
                    collection_id,
                    operator_id,
                    json.dumps({"content_reviewed": True, "payload_sha256": payload_digest}),
                ),
            )
        conn.commit()
        return {
            "id": str(activity[0]),
            "location_id": str(activity[1]),
            "activity_type": activity[2],
            "activity_date": activity[3].isoformat() if hasattr(activity[3], "isoformat") else str(activity[3]),
            "status": activity[4],
            "source_system": activity[5],
            "source_id": activity[6],
            "created": created,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
