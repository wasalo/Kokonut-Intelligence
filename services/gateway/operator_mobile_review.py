"""Location-scoped Field Collector review queries and append-only reviewer events."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class MobileCollectionPayloadTooLarge(ValueError):
    """Raised when a collection exceeds the browser review response bound."""


class MobileReviewEventInvalid(ValueError):
    """Raised when a reviewer note is incomplete or outside the allowed contract."""


_REVIEW_DECISIONS = {
    "reviewed",
    "needs_follow_up",
    "ineligibility_acknowledged",
}


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_ids(operator_id: str, location_id: str) -> tuple[str, str]:
    try:
        return str(UUID(operator_id)), str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc


def _read_rows(
    conn,
    sql: str,
    params: tuple,
    *,
    tenant_scope: tuple[str, str, str, str] | None = None,
    required_tenant_scopes: tuple[tuple[str, str], ...] = (),
) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL lock_timeout = '2s'")
        if tenant_scope is not None:
            operator_id, location_id, resource, action = tenant_scope
            context_options = {}
            if required_tenant_scopes:
                context_options["required_scopes"] = required_tenant_scopes
            set_operator_tenant_context(
                conn,
                operator_id=operator_id,
                location_id=location_id,
                resource=resource,
                action=action,
                **context_options,
            )
        cur.execute(sql, params)
        columns = [description.name for description in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _isoformat(row: dict, fields: tuple[str, ...]) -> dict:
    for field in fields:
        if row.get(field) is not None:
            row[field] = row[field].isoformat()
    for field in (
        "id",
        "form_revision_id",
        "collection_id",
        "location_id",
        "actor_operator_id",
    ):
        if row.get(field) is not None:
            row[field] = str(row[field])
    return row


def list_mobile_collections(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    connection_factory: Callable | None = None,
) -> list[dict]:
    """List synced rows needing review, without participant or payload data."""
    operator_id, location_id = _normalize_ids(operator_id, location_id)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    conn = (connection_factory or _connection_factory())()
    try:
        rows = _read_rows(
            conn,
            """SELECT oc.id, oc.location_id, oc.form_id, oc.form_version,
                          oc.collection_type, oc.collected_at, oc.synced_at,
                          oc.form_validation_status, oc.consent_validation_status,
                          oc.form_review_required, revision.id AS form_revision_id,
                          revision.name AS form_name, revision.status AS form_revision_status,
                          eligibility.eligible_for_use, eligibility.eligibility_reason,
                          CASE WHEN oc.form_review_required
                               THEN 'pending_review'
                               ELSE 'blocked_by_eligibility' END AS review_state
                     FROM offline_collection AS oc
                     JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = oc.id
                     LEFT JOIN mobile_form_version AS revision
                       ON revision.id = oc.form_revision_id
                    WHERE oc.location_id = %s::uuid
                      AND oc.sync_status = 'synced'
                      AND (oc.form_review_required OR NOT eligibility.eligible_for_use)
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'mobile_collection_review'
                             AND grant_row.action = 'read'
                             AND grant_row.location_id = oc.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                    ORDER BY oc.collected_at DESC, oc.id DESC
                    LIMIT %s""",
            (location_id, operator_id, limit),
            tenant_scope=(operator_id, location_id, "mobile_collection_review", "read"),
        )
        return [_isoformat(row, ("collected_at", "synced_at")) for row in rows]
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_mobile_collection(
    operator_id: str,
    collection_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Read one bounded payload with a distinct detail grant and audit action."""
    try:
        operator_id = str(UUID(operator_id))
        collection_id = str(UUID(collection_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator, collection, or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        rows = _read_rows(
            conn,
            """SELECT oc.id, oc.location_id, oc.form_id, oc.form_version,
                          oc.collection_type, oc.collected_at, oc.synced_at,
                          oc.form_validation_status, oc.consent_validation_status,
                          oc.form_review_required, revision.id AS form_revision_id,
                          revision.name AS form_name, revision.status AS form_revision_status,
                          revision.consent_policy_status,
                          eligibility.eligible_for_use, eligibility.eligibility_reason,
                          CASE WHEN oc.form_review_required
                               THEN 'pending_review'
                               ELSE 'blocked_by_eligibility' END AS review_state,
                          CASE WHEN jsonb_typeof(oc.photo_refs) = 'array'
                               THEN jsonb_array_length(oc.photo_refs) ELSE 0 END AS photo_count,
                          CASE WHEN octet_length(oc.payload::text) <= 524288
                               THEN oc.payload ELSE NULL END AS payload,
                          octet_length(oc.payload::text) AS payload_size
                     FROM offline_collection AS oc
                     JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = oc.id
                     LEFT JOIN mobile_form_version AS revision
                       ON revision.id = oc.form_revision_id
                    WHERE oc.id = %s::uuid
                      AND oc.location_id = %s::uuid
                      AND oc.sync_status = 'synced'
                      AND (oc.form_review_required OR NOT eligibility.eligible_for_use)
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'mobile_collection_review'
                             AND grant_row.action = 'read_detail'
                             AND grant_row.location_id = oc.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                    LIMIT 1""",
            (collection_id, location_id, operator_id),
            tenant_scope=(operator_id, location_id, "mobile_collection_review", "read_detail"),
        )
        if not rows:
            return None
        row = rows[0]
        if row["payload"] is None and row["payload_size"] > 524288:
            raise MobileCollectionPayloadTooLarge(
                "Collection exceeds the 512 KiB console read limit"
            )
        row.pop("payload_size", None)
        row = _isoformat(row, ("collected_at", "synced_at"))
        with conn.cursor() as cur:
            cur.execute(
                """SELECT event.id, event.actor_operator_id, event.decision,
                          event.reason, event.evidence, event.created_at
                     FROM mobile_collection_review_event AS event
                    WHERE event.collection_id = %s::uuid
                      AND event.location_id = %s::uuid
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'mobile_collection_review'
                             AND grant_row.action = 'read_detail'
                             AND grant_row.location_id = event.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                    ORDER BY event.created_at DESC, event.id DESC
                    LIMIT 20""",
                (collection_id, location_id, operator_id),
            )
            columns = [description.name for description in cur.description]
            events = [dict(zip(columns, values)) for values in cur.fetchall()]
        row["review_events"] = [
            _isoformat(event, ("created_at",)) for event in events
        ]
        return row
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_mobile_collection_disposition_inventory(
    operator_id: str,
    collection_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Return a read-only, content-free inventory for an ineligible collection.

    This is a known-lineage summary, not proof that all exports or backups have
    been reconciled. A separate retention grant is required; no data is changed.
    """
    try:
        operator_id = str(UUID(operator_id))
        collection_id = str(UUID(collection_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator, collection, or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        rows = _read_rows(
            conn,
            """SELECT oc.id AS collection_id,
                          oc.location_id,
                          eligibility.eligible_for_use,
                          eligibility.eligibility_reason,
                          'known_direct_lineage_only' AS inventory_scope,
                          jsonb_build_object(
                              'sync_status', oc.sync_status,
                              'form_id', oc.form_id,
                              'form_version', oc.form_version,
                              'has_participant_link', oc.participant_link_id IS NOT NULL,
                              'has_collection_consent_reference',
                                  oc.consent_event_id_at_collection IS NOT NULL,
                              'has_sync_consent_reference',
                                  oc.consent_event_id_at_sync IS NOT NULL,
                              'payload_bytes', octet_length(oc.payload::text),
                              'payload_field_count', CASE
                                  WHEN jsonb_typeof(oc.payload) = 'object'
                                  THEN jsonb_object_length(oc.payload) ELSE 0 END,
                              'photo_reference_count', CASE
                                  WHEN jsonb_typeof(oc.photo_refs) = 'array'
                                  THEN jsonb_array_length(oc.photo_refs) ELSE 0 END,
                              'has_coordinates', oc.latitude IS NOT NULL OR oc.longitude IS NOT NULL
                          ) AS collection,
                          (
                              SELECT jsonb_build_object(
                                  'object_count', COALESCE(SUM(media.status_count), 0),
                                  'total_bytes', COALESCE(SUM(media.size_bytes), 0),
                                  'by_status', COALESCE(
                                      jsonb_object_agg(media.status, media.status_count), '{}'::jsonb
                                  )
                              )
                                FROM (
                                    SELECT upload.status, COUNT(*) AS status_count,
                                           SUM(upload.size_bytes) AS size_bytes
                                      FROM mobile_media_upload AS upload
                                     WHERE (upload.attached_collection_id = oc.id
                                        OR (upload.attached_collection_id IS NULL
                                            AND upload.device_id = oc.device_id
                                            AND upload.collection_client_id = oc.client_id))
                                       AND upload.location_id = oc.location_id
                                     GROUP BY upload.status
                                ) AS media
                          ) AS private_media,
                          (
                              SELECT jsonb_build_object(
                                  'total', COALESCE(SUM(activity.status_count), 0),
                                  'by_status', COALESCE(
                                      jsonb_object_agg(activity.status, activity.status_count), '{}'::jsonb
                                  )
                              )
                                FROM (
                                    SELECT farm.status::text AS status, COUNT(*) AS status_count
                                      FROM farm_activity AS farm
                                     WHERE farm.source_system = 'field_collector'
                                       AND farm.source_id = oc.id::text
                                       AND farm.location_id = oc.location_id
                                     GROUP BY farm.status
                                ) AS activity
                          ) AS canonical_activity,
                          (
                              SELECT COUNT(*)
                                FROM farm_activity_workflow_event AS event
                               WHERE event.source_collection_id = oc.id
                                 AND event.location_id = oc.location_id
                          ) AS workflow_event_count,
                          (
                              SELECT COUNT(*)
                                FROM mobile_collection_review_event AS event
                               WHERE event.collection_id = oc.id
                                 AND event.location_id = oc.location_id
                          ) AS review_event_count
                     FROM offline_collection AS oc
                     JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = oc.id
                    WHERE oc.id = %s::uuid
                      AND oc.location_id = %s::uuid
                      AND oc.sync_status = 'synced'
                      AND (oc.form_review_required OR NOT eligibility.eligible_for_use)
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = %s::uuid
                             AND grant_row.resource = 'mobile_collection_retention'
                             AND grant_row.action = 'inventory'
                             AND grant_row.location_id = oc.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS review_grant
                           WHERE review_grant.operator_id = %s::uuid
                             AND review_grant.resource = 'mobile_collection_review'
                             AND review_grant.action = 'read'
                             AND review_grant.location_id = oc.location_id
                             AND operator_scope_grant_allows(
                                 review_grant.operator_id, review_grant.resource,
                                 review_grant.action, review_grant.location_id
                             )
                             AND review_grant.revoked_at IS NULL
                      )
                    LIMIT 1""",
            (collection_id, location_id, operator_id, operator_id),
            tenant_scope=(
                operator_id,
                location_id,
                "mobile_collection_retention",
                "inventory",
            ),
            required_tenant_scopes=(("mobile_collection_review", "read"),),
        )
        if not rows:
            return None
        return _isoformat(rows[0], ())
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def _validate_review_event(value: object) -> tuple[str, str, list[dict[str, str]]]:
    if not isinstance(value, dict) or set(value) != {"decision", "reason", "evidence"}:
        raise MobileReviewEventInvalid("event must contain decision, reason, and evidence only")
    decision = value["decision"]
    if not isinstance(decision, str) or decision not in _REVIEW_DECISIONS:
        raise MobileReviewEventInvalid("decision is unsupported")
    reason = value["reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise MobileReviewEventInvalid("reason must be a non-empty string up to 2000 characters")
    reason = reason.strip()
    evidence = value["evidence"]
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 20:
        raise MobileReviewEventInvalid("evidence must contain between 1 and 20 entries")
    normalized = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"source", "basis"}:
            raise MobileReviewEventInvalid("each evidence item must contain source and basis only")
        source, basis = item["source"], item["basis"]
        if not isinstance(source, str) or not source.strip() or len(source) > 1000:
            raise MobileReviewEventInvalid("evidence source must be non-empty and at most 1000 characters")
        if not isinstance(basis, str) or not basis.strip() or len(basis) > 2000:
            raise MobileReviewEventInvalid("evidence basis must be non-empty and at most 2000 characters")
        normalized.append({"source": source.strip(), "basis": basis.strip()})
    return decision, reason, normalized


def record_mobile_review_event(
    operator_id: str,
    collection_id: str,
    location_id: str,
    body: object,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Append a reviewer note without changing collection or eligibility state."""
    try:
        operator_id = str(UUID(operator_id))
        collection_id = str(UUID(collection_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise MobileReviewEventInvalid("Invalid operator, collection, or location identifier") from exc
    decision, reason, evidence = _validate_review_event(body)
    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            set_operator_tenant_context(
                conn,
                operator_id=operator_id,
                location_id=location_id,
                resource="mobile_collection_review",
                action="review",
                required_scopes=(("mobile_collection_review", "read_detail"),),
            )
            cur.execute(
                """INSERT INTO mobile_collection_review_event (
                          collection_id, location_id, actor_operator_id,
                          decision, reason, evidence
                   )
                   SELECT oc.id, oc.location_id, identity.id,
                          %s, %s, %s::jsonb
                     FROM offline_collection AS oc
                     JOIN v_mobile_collection_use_eligibility AS eligibility
                       ON eligibility.collection_id = oc.id
                     JOIN operator_identity AS identity
                       ON identity.id = %s::uuid AND identity.enabled = TRUE
                    WHERE oc.id = %s::uuid
                      AND oc.location_id = %s::uuid
                      AND oc.sync_status = 'synced'
                      AND (oc.form_review_required OR NOT eligibility.eligible_for_use)
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS grant_row
                           WHERE grant_row.operator_id = identity.id
                             AND grant_row.resource = 'mobile_collection_review'
                             AND grant_row.action = 'review'
                             AND grant_row.location_id = oc.location_id
                             AND operator_scope_grant_allows(
                                 grant_row.operator_id, grant_row.resource,
                                 grant_row.action, grant_row.location_id
                             )
                             AND grant_row.revoked_at IS NULL
                      )
                      AND EXISTS (
                          SELECT 1 FROM operator_scope_grant AS detail_grant
                           WHERE detail_grant.operator_id = identity.id
                             AND detail_grant.resource = 'mobile_collection_review'
                             AND detail_grant.action = 'read_detail'
                             AND detail_grant.location_id = oc.location_id
                             AND operator_scope_grant_allows(
                                 detail_grant.operator_id, detail_grant.resource,
                                 detail_grant.action, detail_grant.location_id
                             )
                             AND detail_grant.revoked_at IS NULL
                      )
                   RETURNING id, collection_id, location_id, actor_operator_id,
                             decision, reason, evidence, created_at""",
                (
                    decision,
                    reason,
                    json.dumps(evidence),
                    operator_id,
                    collection_id,
                    location_id,
                ),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return None
            columns = [description.name for description in cur.description]
            result = dict(zip(columns, row))
        conn.commit()
        return _isoformat(result, ("created_at",))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
