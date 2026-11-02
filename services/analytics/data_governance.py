#!/usr/bin/env python3
"""
Data Governance & Interoperability

Consent management, access auditing, data portability, sharing agreements,
retention policies, and governance metrics for FAIR compliance.

Usage:
    python -m services.analytics.data_governance record-consent --farmer-id F001 --data-category soil --scope collection --status granted
    python -m services.analytics.data_governance withdraw-consent --consent-id UUID --reason "no longer needed"
    python -m services.analytics.data_governance consent-status --farmer-id F001
    python -m services.analytics.data_governance check-consent --farmer-id F001 --data-category soil --scope collection
    python -m services.analytics.data_governance log-access --accessor-id A001 --data-category soil --resource-type soil_sample --access-type read --purpose "field review"
    python -m services.analytics.data_governance access-audit --farmer-id F001
    python -m services.analytics.data_governance request-portability --farmer-id F001 --format csv --scope all
    python -m services.analytics.data_governance fulfill-portability --request-id UUID --file-path /tmp/export.csv
    python -m services.analytics.data_governance portability-requests --farmer-id F001
    python -m services.analytics.data_governance create-agreement --provider-id F001 --consumer-id ORG001 --data-categories soil,yield --purpose "research collaboration"
    python -m services.analytics.data_governance sharing-agreements --farmer-id F001
    python -m services.analytics.data_governance set-retention --data-category soil --entity-type soil_sample --actor OPERATOR --reason "Draft for review"
    python -m services.analytics.data_governance approve-retention --policy-id UUID --approved-by OPERATOR --reason "Approved schedule"
    python -m services.analytics.data_governance retire-retention --policy-id UUID --actor OPERATOR --reason "Schedule replaced"
    python -m services.analytics.data_governance governance-summary --location-id UUID
"""

import json
import re
import uuid
from datetime import date, datetime

from ..common.logging import get_logger

logger = get_logger("analytics.data_governance")


# These records have consent, lifecycle, provenance, or private-media semantics
# that the generic ``deleted_at`` retention sweep cannot preserve. Their
# disposition must use a reviewed, domain-specific workflow.
_REVIEWED_DISPOSITION_ENTITIES = frozenset({
    "farm_activity",
    "farm_activity_workflow_event",
    "mobile_collection_review_event",
    "mobile_device",
    "mobile_form_version",
    "mobile_media_upload",
    "mobile_participant_link",
    "offline_collection",
    "stakeholder_consent",
})

_ARCHIVE_REQUIRED_RETENTION_ENTITIES = {
    "notification_outbox": (
        "notification outbox requires an archive workflow that preserves its "
        "event/channel/destination idempotency tombstone"
    ),
    "notification_outbox_attempt": (
        "notification attempts require an archive workflow coordinated with "
        "their outbox parent and legal holds"
    ),
    "notification_outbox_operator_audit": (
        "notification operator audit requires an archive workflow coordinated "
        "with its outbox parent and legal holds"
    ),
}


def _requires_reviewed_disposition(entity_type: str | None) -> bool:
    return (
        isinstance(entity_type, str)
        and entity_type.strip().lower() in _REVIEWED_DISPOSITION_ENTITIES
    )


def _normalize_retention_scope_code(value: str | None, field_name: str) -> str | None:
    """Normalize an owner-defined retention scope code without assigning meaning."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,99}", normalized):
        raise ValueError(
            f"{field_name} must be a 1-100 character code using letters, numbers, '.', '_', ':', or '-'"
        )
    return normalized


def _retention_scope_filters(
    *,
    available_columns: set[str],
    location_id: str | None,
    jurisdiction_code: str | None,
    purpose_code: str | None,
) -> tuple[tuple[str, ...], tuple[object, ...], str | None]:
    """Build exact-column filters for configured scopes; never infer a scope.

    Jurisdiction and purpose are owner-defined codes. They are enforceable by
    the generic sweeper only when the target row itself exposes the matching
    code column; location ownership is likewise matched through a direct
    ``location_id`` column. Domain-specific joins need a separate reviewed
    adapter rather than a guessed relationship.
    """
    filters: list[str] = []
    parameters: list[object] = []
    for column, value, scope_name in (
        ("location_id", location_id, "location"),
        ("jurisdiction_code", jurisdiction_code, "jurisdiction"),
        ("purpose_code", purpose_code, "purpose"),
    ):
        if value is None:
            continue
        if column not in available_columns:
            return (
                (),
                (),
                f"configured {scope_name} scope requires the target table's {column} column",
            )
        # Column names come only from this fixed mapping, never policy input.
        filters.append(f'"{column}" = %s')
        parameters.append(value)
    return tuple(filters), tuple(parameters), None


def _normalize_retention_audit_text(
    value: str, field_name: str, *, max_length: int | None = None,
) -> str:
    """Validate operator-supplied retention audit text before opening a cursor."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    if max_length is not None and len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


# ============================================================
# Consent Management
# ============================================================

def record_consent(
    conn,
    farmer_id: str,
    data_category: str,
    scope: str,
    status: str = "granted",
    method: str = "digital_form",
    location_id: str = None,
    expires_at: datetime = None,
    evidence_ref: str = None,
    legal_basis: str = None,
    consent_version: str = "1.0",
    ip_address: str = None,
    user_agent: str = None,
    metadata: dict = None,
) -> dict:
    """Record a consent grant or withdrawal event."""
    cur = conn.cursor()
    consent_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO farmer_consent
                (id, farmer_id, location_id, data_category, consent_scope,
                 status, consent_method, evidence_ref, expires_at,
                 consent_version, legal_basis, ip_address, user_agent, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (
                consent_id, farmer_id, location_id, data_category, scope,
                status, method, evidence_ref, expires_at,
                consent_version, legal_basis, ip_address, user_agent,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "consent_id": consent_id,
            "farmer_id": farmer_id,
            "data_category": data_category,
            "consent_scope": scope,
            "status": status,
            "consent_method": method,
            "created_at": row[1].isoformat() if row else None,
        }
    finally:
        cur.close()


def withdraw_consent(
    conn,
    consent_id: str,
    reason: str = None,
    actor_id: str = None,
) -> dict:
    """Withdraw an existing consent grant."""
    if not actor_id:
        return {"error": "actor authorization is required", "consent_id": consent_id}
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE farmer_consent
            SET status = 'withdrawn',
                withdrawn_at = NOW(),
                withdrawal_reason = %s,
                updated_at = NOW()
            WHERE id = %s
              AND status != 'withdrawn'
              AND (%s IS NULL OR farmer_id = %s)
            RETURNING id, farmer_id, data_category, consent_scope, withdrawn_at
            """,
            (reason, consent_id, actor_id, actor_id),
        )
        row = cur.fetchone()
        conn.commit()

        if not row:
            return {"error": "consent not found or already withdrawn", "consent_id": consent_id}

        return {
            "consent_id": str(row[0]),
            "farmer_id": row[1],
            "data_category": row[2],
            "consent_scope": row[3],
            "status": "withdrawn",
            "withdrawn_at": row[4].isoformat() if row[4] else None,
            "withdrawal_reason": reason,
        }
    finally:
        cur.close()


def get_consent_status(conn, farmer_id: str) -> dict:
    """Get current consent status per data category for a farmer."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT DISTINCT ON (data_category, consent_scope)
                id, data_category, consent_scope, status, granted_at,
                withdrawn_at, expires_at, consent_method, consent_version,
                CASE
                    WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 'expired'
                    ELSE status
                END AS effective_status,
                CASE
                    WHEN expires_at IS NOT NULL THEN
                        EXTRACT(DAY FROM (expires_at - NOW()))::INTEGER
                    ELSE NULL
                END AS days_until_expiry
            FROM farmer_consent
            WHERE farmer_id = %s
            ORDER BY data_category, consent_scope, created_at DESC
            """,
            (farmer_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        by_category = {}
        for r in rows:
            cat = r["data_category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "consent_id": str(r["id"]),
                "scope": r["consent_scope"],
                "status": r["status"],
                "effective_status": r["effective_status"],
                "days_until_expiry": r["days_until_expiry"],
                "granted_at": r["granted_at"].isoformat() if r["granted_at"] else None,
                "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                "method": r["consent_method"],
                "version": r["consent_version"],
            })

        return {
            "farmer_id": farmer_id,
            "categories": by_category,
            "total_active_consents": len(rows),
        }
    finally:
        cur.close()


def check_consent(
    conn,
    farmer_id: str,
    data_category: str,
    scope: str,
) -> dict:
    """Check if a specific consent exists for a farmer, category, and scope."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, status, granted_at, expires_at, consent_method,
                CASE
                    WHEN granted_at > NOW() THEN 'pending'
                    WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 'expired'
                    ELSE status
                END AS effective_status
            FROM farmer_consent
            WHERE farmer_id = %s AND data_category = %s AND consent_scope = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (farmer_id, data_category, scope),
        )
        row = cur.fetchone()

        if not row:
            return {
                "farmer_id": farmer_id,
                "data_category": data_category,
                "scope": scope,
                "consent_exists": False,
                "consented": False,
            }

        consented = row[5] == "granted"

        return {
            "farmer_id": farmer_id,
            "data_category": data_category,
            "scope": scope,
            "consent_exists": True,
            "consented": consented,
            "consent_id": str(row[0]),
            "status": row[1],
            "effective_status": row[5],
            "granted_at": row[2].isoformat() if row[2] else None,
            "expires_at": row[3].isoformat() if row[3] else None,
        }
    finally:
        cur.close()


# ============================================================
# Access Auditing
# ============================================================

def log_access(
    conn,
    accessor_id: str,
    data_category: str,
    resource_type: str,
    access_type: str,
    purpose: str = None,
    resource_id: str = None,
    location_id: str = None,
    accessor_role: str = None,
    accessor_type: str = "user",
    access_method: str = None,
    consent_id: str = None,
    status: str = "success",
    denial_reason: str = None,
    records_affected: int = 0,
    ip_address: str = None,
    user_agent: str = None,
    request_id: str = None,
    session_id: str = None,
    metadata: dict = None,
) -> dict:
    """Log a data access event."""
    cur = conn.cursor()
    log_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO data_access_log
                (id, accessor_id, accessor_role, accessor_type,
                 resource_type, resource_id, location_id, data_category,
                 access_type, access_method, purpose, consent_id,
                 status, denial_reason, records_affected,
                 ip_address, user_agent, request_id, session_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, accessed_at
            """,
            (
                log_id, accessor_id, accessor_role, accessor_type,
                resource_type, resource_id, location_id, data_category,
                access_type, access_method, purpose, consent_id,
                status, denial_reason, records_affected,
                ip_address, user_agent, request_id, session_id,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "access_log_id": log_id,
            "accessor_id": accessor_id,
            "resource_type": resource_type,
            "access_type": access_type,
            "status": status,
            "accessed_at": row[1].isoformat() if row else None,
        }
    finally:
        cur.close()


def get_access_audit(conn, farmer_id: str, days: int = 30) -> dict:
    """Get data access audit trail for a farmer."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT dal.id, dal.accessor_id, dal.accessor_role, dal.accessor_type,
                   dal.resource_type, dal.resource_id, dal.data_category,
                   dal.access_type, dal.access_method, dal.purpose,
                   dal.status, dal.denial_reason, dal.records_affected,
                   dal.accessed_at, l.name AS location_name
            FROM data_access_log dal
            LEFT JOIN location l ON l.id = dal.location_id
            WHERE dal.location_id IN (
                SELECT id FROM location WHERE farmer_id = %s
            )
            AND dal.accessed_at >= NOW() - make_interval(days => %s)
            ORDER BY dal.accessed_at DESC
            LIMIT 500
            """,
            (farmer_id, days),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        events = []
        for r in rows:
            events.append({
                "access_log_id": str(r["id"]),
                "accessor_id": r["accessor_id"],
                "accessor_role": r["accessor_role"],
                "accessor_type": r["accessor_type"],
                "resource_type": r["resource_type"],
                "resource_id": str(r["resource_id"]) if r["resource_id"] else None,
                "data_category": r["data_category"],
                "access_type": r["access_type"],
                "access_method": r["access_method"],
                "purpose": r["purpose"],
                "status": r["status"],
                "denial_reason": r["denial_reason"],
                "records_affected": r["records_affected"],
                "accessed_at": r["accessed_at"].isoformat() if r["accessed_at"] else None,
                "location_name": r["location_name"],
            })

        summary = {
            "total_events": len(events),
            "by_access_type": {},
            "by_status": {},
            "denied_count": 0,
        }
        for e in events:
            at = e["access_type"]
            summary["by_access_type"][at] = summary["by_access_type"].get(at, 0) + 1
            st = e["status"]
            summary["by_status"][st] = summary["by_status"].get(st, 0) + 1
            if e["status"] == "denied":
                summary["denied_count"] += 1

        return {
            "farmer_id": farmer_id,
            "days": days,
            "events": events,
            "summary": summary,
        }
    finally:
        cur.close()


# ============================================================
# Data Portability
# ============================================================

def request_portability(
    conn,
    farmer_id: str,
    format_type: str = "json",
    scope: str = "all",
    data_categories: list = None,
    location_id: str = None,
    requested_by: str = None,
    include_metadata: bool = True,
    date_range_start: date = None,
    date_range_end: date = None,
    metadata: dict = None,
    authorization_ref: str = None,
) -> dict:
    """Request data export (FAIR portability)."""
    requester = requested_by or farmer_id
    if requester != farmer_id and not authorization_ref:
        return {"error": "authorization required for portability request", "farmer_id": farmer_id}
    cur = conn.cursor()
    request_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO data_portability_request
                (id, farmer_id, location_id, requested_by,
                  data_categories, format, include_metadata,
                  date_range_start, date_range_end, scope, authorization_ref, metadata)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, requested_at
            """,
            (
                request_id, farmer_id, location_id,
                requester,
                data_categories or [], format_type, include_metadata,
                date_range_start, date_range_end, scope,
                authorization_ref,
                json.dumps({**(metadata or {}), "authorization_ref": authorization_ref}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "request_id": request_id,
            "farmer_id": farmer_id,
            "format": format_type,
            "scope": scope,
            "data_categories": data_categories or [],
            "status": "pending",
            "requested_at": row[1].isoformat() if row else None,
        }
    finally:
        cur.close()


def fulfill_portability(
    conn,
    request_id: str,
    file_path: str = None,
    output_hash: str = None,
    output_size_bytes: int = None,
    record_count: int = 0,
    owner_id: str = None,
    fulfilled_by: str = None,
    authorization_ref: str = None,
) -> dict:
    """Mark a portability request as fulfilled.

    Authorization: fulfilled_by must be either the data owner or a system
    actor that has a verified authorization_ref.  Self-fulfillment
    (fulfilled_by == owner_id) is always allowed.
    """
    if not owner_id or not fulfilled_by or not authorization_ref:
        return {"error": "owner, fulfiller, and authorization reference are required", "request_id": request_id}

    cur = conn.cursor()

    try:
        # Authorization check: fulfiller must be the owner or have a
        # verified authorization record.
        if fulfilled_by != owner_id:
            cur.execute(
                """
                SELECT id FROM data_portability_request
                WHERE id = %s AND farmer_id = %s
                  AND authorization_ref = %s
                  AND status IN ('pending', 'processing')
                """,
                (request_id, owner_id, authorization_ref),
            )
            if not cur.fetchone():
                logger.warning(
                    "Unauthorized portability fulfillment attempt: fulfiller=%s owner=%s ref=%s",
                    fulfilled_by, owner_id, authorization_ref,
                )
                conn.commit()
                return {
                    "error": "Fulfiller is not authorized: must be the data owner or hold a verified authorization reference",
                    "request_id": request_id,
                }

            # Log the authorized third-party fulfillment
            cur.execute(
                """
                INSERT INTO data_access_log
                    (accessor_id, data_category, resource_type, resource_id,
                     access_type, purpose, accessor_type, consent_id, status)
                VALUES (%s, 'portability_export', 'data_portability_request', %s,
                        'export', 'portability_fulfillment', 'system', NULL, 'success')
                """,
                (fulfilled_by, request_id),
            )

        cur.execute(
            """
            UPDATE data_portability_request
             SET status = 'ready',
                processed_at = NOW(),
                ready_at = NOW(),
                output_url = %s,
                output_hash = %s,
                output_size_bytes = %s,
                 record_count = %s,
                 fulfilled_by = %s,
                 fulfillment_authorization_ref = %s,
                 updated_at = NOW()
             WHERE id = %s AND farmer_id = %s AND status IN ('pending', 'processing')
             RETURNING id, farmer_id, format, ready_at
            """,
            (file_path, output_hash, output_size_bytes, record_count, fulfilled_by,
             authorization_ref, request_id, owner_id),
        )
        row = cur.fetchone()
        conn.commit()

        if not row:
            return {"error": "request not found or not in processable state", "request_id": request_id}

        return {
            "request_id": str(row[0]),
            "farmer_id": row[1],
            "format": row[2],
            "status": "ready",
            "ready_at": row[3].isoformat() if row[3] else None,
            "output_url": file_path,
            "record_count": record_count,
        }
    finally:
        cur.close()


def get_portability_requests(conn, farmer_id: str, actor_id: str = None) -> dict:
    """List portability requests for a farmer."""
    if not actor_id or actor_id != farmer_id:
        return {"error": "only the data owner may list portability requests", "farmer_id": farmer_id}
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, data_categories, format, scope, status,
                   requested_at, processed_at, ready_at, downloaded_at,
                   expires_at, output_url, record_count, output_size_bytes,
                   fair_principles
            FROM data_portability_request
            WHERE farmer_id = %s
            ORDER BY requested_at DESC
            """,
            (farmer_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        requests = []
        for r in rows:
            requests.append({
                "request_id": str(r["id"]),
                "data_categories": r["data_categories"],
                "format": r["format"],
                "scope": r["scope"],
                "status": r["status"],
                "requested_at": r["requested_at"].isoformat() if r["requested_at"] else None,
                "processed_at": r["processed_at"].isoformat() if r["processed_at"] else None,
                "ready_at": r["ready_at"].isoformat() if r["ready_at"] else None,
                "downloaded_at": r["downloaded_at"].isoformat() if r["downloaded_at"] else None,
                "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                "output_url": r["output_url"],
                "record_count": r["record_count"],
                "output_size_bytes": r["output_size_bytes"],
                "fair_principles": r["fair_principles"],
            })

        return {
            "farmer_id": farmer_id,
            "requests": requests,
            "total": len(requests),
        }
    finally:
        cur.close()


# ============================================================
# Data Sharing Agreements
# ============================================================

def create_sharing_agreement(
    conn,
    provider_id: str,
    consumer_id: str,
    data_categories: list,
    purpose: str,
    provider_type: str = "farmer",
    consumer_type: str = "organization",
    legal_basis: str = None,
    exclusivity: bool = False,
    commercial_use: bool = False,
    anonymization_required: bool = True,
    retention_days: int = None,
    geographic_scope: str = None,
    effective_date: date = None,
    expiry_date: date = None,
    metadata: dict = None,
) -> dict:
    """Create a data sharing agreement."""
    cur = conn.cursor()
    agreement_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO data_sharing_agreement
                (id, provider_id, provider_type, consumer_id, consumer_type,
                 data_categories, purpose, legal_basis,
                 exclusivity, commercial_use, anonymization_required,
                 retention_days, geographic_scope,
                 status, effective_date, expiry_date, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (
                agreement_id, provider_id, provider_type, consumer_id, consumer_type,
                data_categories, purpose, legal_basis,
                exclusivity, commercial_use, anonymization_required,
                retention_days, geographic_scope,
                effective_date, expiry_date,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "agreement_id": agreement_id,
            "provider_id": provider_id,
            "consumer_id": consumer_id,
            "data_categories": data_categories,
            "purpose": purpose,
            "status": "draft",
            "created_at": row[1].isoformat() if row else None,
        }
    finally:
        cur.close()


def get_sharing_agreements(conn, farmer_id: str) -> dict:
    """List active data sharing agreements for a farmer."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, provider_id, consumer_id, data_categories, purpose,
                   status, effective_date, expiry_date,
                   anonymization_required, commercial_use, created_at
            FROM data_sharing_agreement
            WHERE (provider_id = %s OR consumer_id = %s)
              AND status NOT IN ('terminated', 'violated')
            ORDER BY created_at DESC
            """,
            (farmer_id, farmer_id),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        agreements = []
        for r in rows:
            agreements.append({
                "agreement_id": str(r["id"]),
                "provider_id": r["provider_id"],
                "consumer_id": r["consumer_id"],
                "data_categories": r["data_categories"],
                "purpose": r["purpose"],
                "status": r["status"],
                "effective_date": r["effective_date"].isoformat() if r["effective_date"] else None,
                "expiry_date": r["expiry_date"].isoformat() if r["expiry_date"] else None,
                "anonymization_required": r["anonymization_required"],
                "commercial_use": r["commercial_use"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            })

        return {
            "farmer_id": farmer_id,
            "agreements": agreements,
            "total": len(agreements),
        }
    finally:
        cur.close()


# ============================================================
# Retention Policies
# ============================================================

def set_retention_policy(
    conn,
    data_category: str,
    retention_days: int = None,
    action: str = "soft_delete",
    entity_type: str = None,
    location_id: str = None,
    auto_enforce: bool = False,
    policy_owner: str = None,
    metadata: dict = None,
    actor: str = None,
    reason: str = None,
    jurisdiction_code: str = None,
    purpose_code: str = None,
) -> dict:
    """Create an inert draft retention policy, optionally with a proposed window."""
    if not isinstance(data_category, str) or not data_category.strip():
        raise ValueError("data_category is required")
    actor = _normalize_retention_audit_text(actor, "actor", max_length=200)
    reason = _normalize_retention_audit_text(reason, "reason")
    if auto_enforce:
        raise ValueError("new policies must be approved before auto_enforce can be enabled")
    if retention_days is not None and (
        isinstance(retention_days, bool)
        or not isinstance(retention_days, int)
        or retention_days <= 0
    ):
        raise ValueError("retention_days must be a positive integer")
    if action not in {"soft_delete", "hard_delete", "anonymize", "archive", "none"}:
        raise ValueError("unsupported retention action")
    if _requires_reviewed_disposition(entity_type):
        raise ValueError(
            "this entity requires a dedicated reviewed disposition workflow"
        )
    jurisdiction_code = _normalize_retention_scope_code(
        jurisdiction_code, "jurisdiction_code",
    )
    purpose_code = _normalize_retention_scope_code(purpose_code, "purpose_code")
    cur = conn.cursor()
    policy_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO data_retention_policy
                (id, data_category, entity_type, location_id,
                 jurisdiction_code, purpose_code,
                 retention_days, deletion_method, auto_enforce,
                 policy_owner, status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, 'draft', %s::jsonb)
            ON CONFLICT DO NOTHING
            RETURNING id, created_at
            """,
            (
                policy_id, data_category, entity_type, location_id,
                jurisdiction_code, purpose_code,
                retention_days, action, policy_owner,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        if row is None:
            conn.commit()
            return {"created": False, "policy_id": policy_id}
        cur.execute(
            """
            INSERT INTO data_retention_policy_event
                (policy_id, action, actor, reason, policy_snapshot)
            VALUES (%s, 'draft_created', %s, %s, %s::jsonb)
            """,
            (
                policy_id,
                actor,
                reason,
                json.dumps({
                    "data_category": data_category.strip(),
                    "entity_type": entity_type,
                    "location_id": location_id,
                    "jurisdiction_code": jurisdiction_code,
                    "purpose_code": purpose_code,
                    "policy_owner": policy_owner,
                    "retention_days": retention_days,
                    "deletion_method": action,
                    "auto_enforce": False,
                    "status": "draft",
                }),
            ),
        )
        conn.commit()

        return {
            "policy_id": policy_id,
            "data_category": data_category,
            "retention_days": retention_days,
            "deletion_method": action,
            "jurisdiction_code": jurisdiction_code,
            "purpose_code": purpose_code,
            "auto_enforce": False,
            "status": "draft",
            "created_at": row[1].isoformat() if row else None,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def list_retention_policies(
    conn,
    *,
    status: str | None = None,
    data_category: str | None = None,
    jurisdiction_code: str | None = None,
    purpose_code: str | None = None,
    location_id: str | None = None,
    limit: int = 100,
) -> dict:
    """Return a bounded policy inventory without exposing free-text metadata."""
    if status is not None and (
        not isinstance(status, str)
        or status not in {"draft", "active", "inactive"}
    ):
        raise ValueError("status must be draft, active, or inactive")
    if data_category is not None:
        if not isinstance(data_category, str) or not data_category.strip():
            raise ValueError("data_category must be a non-empty string")
        data_category = data_category.strip()
    jurisdiction_code = _normalize_retention_scope_code(
        jurisdiction_code, "jurisdiction_code",
    )
    purpose_code = _normalize_retention_scope_code(purpose_code, "purpose_code")
    if location_id is not None:
        try:
            location_id = str(uuid.UUID(str(location_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("location_id must be a UUID") from exc
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be an integer between 1 and 500")

    filters = []
    params = []
    for column, value in (
        ("status", status),
        ("data_category", data_category),
        ("jurisdiction_code", jurisdiction_code),
        ("purpose_code", purpose_code),
        ("location_id", location_id),
    ):
        if value is not None:
            filters.append(f"{column} = %s")
            params.append(value)
    where = " AND ".join(filters) if filters else "TRUE"
    params.append(limit)

    columns = (
        "id", "data_category", "entity_type", "location_id",
        "jurisdiction_code", "purpose_code", "retention_days",
        "deletion_method", "auto_enforce", "status", "enforcement_status",
        "policy_owner", "approved_by", "approval_date", "created_at",
        "updated_at", "last_enforced_at",
    )
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT {", ".join(columns)}
            FROM data_retention_policy
            WHERE {where}
            ORDER BY created_at DESC, id
            LIMIT %s
            """,
            tuple(params),
        )
        policies = []
        for row in cur.fetchall():
            policy = dict(zip(columns, row))
            for key, value in policy.items():
                if isinstance(value, (date, datetime, uuid.UUID)):
                    policy[key] = str(value) if isinstance(value, uuid.UUID) else value.isoformat()
            policies.append(policy)
        return {"policies": policies, "total": len(policies), "limit": limit}
    finally:
        cur.close()


def list_retention_legal_holds(
    conn,
    *,
    active_only: bool = True,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
) -> dict:
    """Return a bounded legal-hold inventory without exposing hold reasons."""
    if not isinstance(active_only, bool):
        raise ValueError("active_only must be a boolean")
    if entity_type is not None and (
        not isinstance(entity_type, str)
        or not re.fullmatch(r"[a-z_]+", entity_type)
    ):
        raise ValueError("entity_type must be a lowercase table name")
    if entity_id is not None:
        try:
            entity_id = str(uuid.UUID(str(entity_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("entity_id must be a UUID") from exc
    if entity_id is not None and entity_type is None:
        raise ValueError("entity_type is required when entity_id is supplied")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be an integer between 1 and 500")

    filters = []
    params = []
    if active_only:
        filters.append("released_at IS NULL")
    if entity_type is not None:
        filters.append("entity_type = %s")
        params.append(entity_type)
    if entity_id is not None:
        filters.append("entity_id = %s")
        params.append(entity_id)
    where = " AND ".join(filters) if filters else "TRUE"
    params.append(limit)

    columns = (
        "id", "entity_type", "entity_id", "placed_by", "placed_at",
        "released_by", "released_at",
    )
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT {", ".join(columns)}
            FROM data_retention_legal_hold
            WHERE {where}
            ORDER BY placed_at DESC, id
            LIMIT %s
            """,
            tuple(params),
        )
        holds = []
        for row in cur.fetchall():
            hold = dict(zip(columns, row))
            for key, value in hold.items():
                if isinstance(value, (date, datetime, uuid.UUID)):
                    hold[key] = str(value) if isinstance(value, uuid.UUID) else value.isoformat()
            holds.append(hold)
        return {"holds": holds, "total": len(holds), "limit": limit}
    finally:
        cur.close()


def approve_retention_policy(
    conn,
    policy_id: str,
    approved_by: str,
    auto_enforce: bool = False,
    reason: str = None,
) -> dict:
    """Approve a fully specified draft; enforcement still needs its feature gate."""
    approved_by = _normalize_retention_audit_text(
        approved_by, "approved_by", max_length=200,
    )
    reason = _normalize_retention_audit_text(reason, "reason")
    if not isinstance(auto_enforce, bool):
        raise ValueError("auto_enforce must be a boolean")
    try:
        normalized_policy_id = str(uuid.UUID(str(policy_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("policy_id must be a UUID") from exc

    cur = conn.cursor()
    try:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('kokonut.retention.legal_hold'))")
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('data_retention_policy_approval'))")
        cur.execute(
            """
            UPDATE data_retention_policy
            SET status = 'active', approved_by = %s, approval_date = CURRENT_DATE,
                auto_enforce = %s, updated_at = NOW()
            WHERE id = %s
              AND status = 'draft'
              AND retention_days IS NOT NULL
              AND retention_days > 0
              AND entity_type IS NOT NULL
              AND policy_owner IS NOT NULL
              AND length(btrim(policy_owner)) > 0
              AND deletion_method <> 'none'
              AND (
                  NOT %s
                  OR (jurisdiction_code IS NULL AND purpose_code IS NULL)
              )
              AND NOT EXISTS (
                  SELECT 1 FROM data_retention_policy active
                  WHERE active.id <> data_retention_policy.id
                    AND active.data_category = data_retention_policy.data_category
                    AND active.entity_type IS NOT DISTINCT FROM data_retention_policy.entity_type
                    AND (
                        active.jurisdiction_code IS NULL
                        OR data_retention_policy.jurisdiction_code IS NULL
                        OR active.jurisdiction_code = data_retention_policy.jurisdiction_code
                    )
                    AND (
                        active.purpose_code IS NULL
                        OR data_retention_policy.purpose_code IS NULL
                        OR active.purpose_code = data_retention_policy.purpose_code
                    )
                    AND (
                        active.location_id IS NULL
                        OR data_retention_policy.location_id IS NULL
                        OR active.location_id = data_retention_policy.location_id
                    )
                    AND active.status = 'active'
              )
            RETURNING id, data_category, entity_type, location_id,
                      jurisdiction_code, purpose_code, retention_days,
                      deletion_method, auto_enforce, approved_by, approval_date,
                      policy_owner
            """,
            (approved_by, auto_enforce, auto_enforce, normalized_policy_id),
        )
        row = cur.fetchone()
        if row is not None:
            cur.execute(
                """
                INSERT INTO data_retention_policy_event
                    (policy_id, action, actor, reason, policy_snapshot)
                VALUES (%s, 'approved', %s, %s, %s::jsonb)
                """,
                (
                    str(row[0]),
                    approved_by,
                    reason,
                    json.dumps({
                        "data_category": row[1],
                        "entity_type": row[2],
                        "location_id": str(row[3]) if row[3] else None,
                        "jurisdiction_code": row[4],
                        "purpose_code": row[5],
                        "retention_days": row[6],
                        "deletion_method": row[7],
                        "auto_enforce": row[8],
                        "approved_by": row[9],
                        "approval_date": row[10].isoformat() if row[10] else None,
                        "policy_owner": row[11],
                        "status": "active",
                    }),
                ),
            )
        conn.commit()
        if row is None:
            return {
                "approved": False,
                "policy_id": normalized_policy_id,
                "reason": (
                    "draft is incomplete, scoped auto-enforcement has no resolver, "
                    "or the policy overlaps an active policy"
                ),
            }
        return {
            "approved": True,
            "policy_id": str(row[0]),
            "data_category": row[1],
            "entity_type": row[2],
            "location_id": str(row[3]) if row[3] else None,
            "jurisdiction_code": row[4],
            "purpose_code": row[5],
            "retention_days": row[6],
            "deletion_method": row[7],
            "auto_enforce": row[8],
            "approved_by": row[9],
            "approval_date": row[10].isoformat() if row[10] else None,
            "policy_owner": row[11],
            "jurisdiction_purpose_scope_resolved": row[4] is None and row[5] is None,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def retire_retention_policy(
    conn,
    policy_id: str,
    actor: str,
    reason: str,
) -> dict:
    """Disable an active policy with an append-only operator record."""
    actor = _normalize_retention_audit_text(actor, "actor", max_length=200)
    reason = _normalize_retention_audit_text(reason, "reason")
    try:
        normalized_policy_id = str(uuid.UUID(str(policy_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("policy_id must be a UUID") from exc

    cur = conn.cursor()
    try:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('kokonut.retention.legal_hold'))")
        cur.execute(
            """
            UPDATE data_retention_policy
            SET status = 'inactive', auto_enforce = FALSE,
                override_reason = %s, updated_at = NOW()
            WHERE id = %s AND status = 'active'
            RETURNING id, data_category, entity_type, location_id,
                      jurisdiction_code, purpose_code, retention_days,
                      deletion_method, approved_by, approval_date, policy_owner
            """,
            (reason, normalized_policy_id),
        )
        row = cur.fetchone()
        if row is None:
            conn.commit()
            return {"retired": False, "policy_id": normalized_policy_id}
        cur.execute(
            """
            INSERT INTO data_retention_policy_event
                (policy_id, action, actor, reason, policy_snapshot)
            VALUES (%s, 'retired', %s, %s, %s::jsonb)
            """,
            (
                str(row[0]),
                actor,
                reason,
                json.dumps({
                    "data_category": row[1],
                    "entity_type": row[2],
                    "location_id": str(row[3]) if row[3] else None,
                    "jurisdiction_code": row[4],
                    "purpose_code": row[5],
                    "retention_days": row[6],
                    "deletion_method": row[7],
                    "approved_by": row[8],
                    "approval_date": row[9].isoformat() if row[9] else None,
                    "policy_owner": row[10],
                    "status": "inactive",
                    "auto_enforce": False,
                }),
            ),
        )
        conn.commit()
        return {"retired": True, "policy_id": str(row[0])}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def place_retention_legal_hold(
    conn,
    entity_type: str,
    entity_id: str,
    actor: str,
    reason: str,
) -> dict:
    """Place an audited hold on a UUID-backed entity."""
    if not isinstance(entity_type, str) or not re.fullmatch(r"[a-z_]+", entity_type):
        raise ValueError("entity_type must be a lowercase table name")
    actor = _normalize_retention_audit_text(actor, "actor", max_length=200)
    reason = _normalize_retention_audit_text(reason, "reason")
    try:
        normalized_entity_id = str(uuid.UUID(str(entity_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("entity_id must be a UUID") from exc

    cur = conn.cursor()
    hold_id = str(uuid.uuid4())
    try:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('kokonut.retention.legal_hold'))")
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE n.nspname = 'public' AND c.relname = %s
                  AND c.relkind IN ('r', 'p')
                  AND a.attname = 'id' AND a.attnum > 0 AND NOT a.attisdropped
                  AND a.atttypid = 'uuid'::regtype
            )
            """,
            (entity_type,),
        )
        if not cur.fetchone()[0]:
            raise ValueError("entity_type is not a public table")
        quoted_entity = '"' + entity_type.replace('"', '""') + '"'
        cur.execute(
            f"SELECT id FROM {quoted_entity} WHERE id = %s FOR SHARE",
            (normalized_entity_id,),
        )
        if cur.fetchone() is None:
            raise ValueError("entity does not exist")
        cur.execute(
            """
            INSERT INTO data_retention_legal_hold
                (id, entity_type, entity_id, reason, placed_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, placed_at
            """,
            (hold_id, entity_type, normalized_entity_id, reason, actor),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "hold_id": str(row[0]),
            "entity_type": entity_type,
            "entity_id": normalized_entity_id,
            "placed_by": actor,
            "placed_at": row[1].isoformat() if row and row[1] else None,
            "status": "active",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def release_retention_legal_hold(
    conn,
    hold_id: str,
    actor: str,
    reason: str,
) -> dict:
    """Release an active hold once, retaining its immutable action history."""
    actor = _normalize_retention_audit_text(actor, "actor", max_length=200)
    reason = _normalize_retention_audit_text(reason, "reason")
    try:
        normalized_hold_id = str(uuid.UUID(str(hold_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("hold_id must be a UUID") from exc

    cur = conn.cursor()
    try:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('kokonut.retention.legal_hold'))")
        cur.execute(
            """
            UPDATE data_retention_legal_hold
            SET released_by = %s, released_at = NOW(), release_reason = %s
            WHERE id = %s AND released_at IS NULL
            RETURNING id, entity_type, entity_id, released_at
            """,
            (actor, reason, normalized_hold_id),
        )
        row = cur.fetchone()
        conn.commit()
        if row is None:
            return {"released": False, "hold_id": normalized_hold_id}
        return {
            "released": True,
            "hold_id": str(row[0]),
            "entity_type": row[1],
            "entity_id": str(row[2]),
            "released_at": row[3].isoformat() if row[3] else None,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def enforce_retention_policies(conn, actor: str, dry_run: bool = False) -> dict:
    """Execute a governed retention sweep for configured entity tables.

    ``entity_type`` is deliberately treated as a table identifier only after
    checking it against PostgreSQL metadata. Policies without a target table,
    legal holds, paused policies, and ``none`` actions are recorded as skipped.
    """
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("actor is required")
    normalized_actor = actor.strip()
    if len(normalized_actor) > 200:
        raise ValueError("actor must be at most 200 characters")
    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be a boolean")

    if not dry_run:
        from .retention import require_data_retention_enforcement

        require_data_retention_enforcement()

    cur = conn.cursor()
    results = []
    try:
        if not dry_run:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('kokonut.retention.legal_hold'))")
        cur.execute("""
            SELECT id, data_category, entity_type, location_id,
                   jurisdiction_code, purpose_code, retention_days,
                   deletion_method, legal_hold, auto_enforce, enforcement_status,
                   approved_by, approval_date, policy_owner
            FROM data_retention_policy
            WHERE status = 'active'
            ORDER BY priority DESC, created_at
        """)
        policies = cur.fetchall()
        for policy_id, category, entity_type, location_id, jurisdiction_code, purpose_code, days, method, legal_hold, auto_enforce, enforcement_status, approved_by, approval_date, policy_owner in policies:
            status, candidates, affected, error = None, 0, 0, None
            if _requires_reviewed_disposition(entity_type):
                status = "skipped"
                error = "protected entity requires a dedicated reviewed disposition workflow"
            elif entity_type in _ARCHIVE_REQUIRED_RETENTION_ENTITIES:
                status = "skipped"
                error = _ARCHIVE_REQUIRED_RETENTION_ENTITIES[entity_type]
            elif entity_type == "platform_event":
                status = "skipped"
                error = "platform_event requires the hold-aware event cleanup workflow"
            elif legal_hold:
                status = "skipped"
                error = "retention policy is on legal hold"
            if status is None and entity_type:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM data_retention_policy overlap
                    WHERE overlap.id <> %s
                      AND overlap.data_category = %s
                      AND overlap.entity_type = %s
                      AND overlap.status = 'active'
                      AND (
                          overlap.jurisdiction_code IS NULL
                          OR %s IS NULL
                          OR overlap.jurisdiction_code = %s
                      )
                      AND (
                          overlap.purpose_code IS NULL
                          OR %s IS NULL
                          OR overlap.purpose_code = %s
                      )
                      AND (
                          overlap.location_id IS NULL
                          OR %s IS NULL
                          OR overlap.location_id = %s
                      )
                    """,
                    (
                        policy_id, category, entity_type,
                        jurisdiction_code, jurisdiction_code,
                        purpose_code, purpose_code,
                        location_id, location_id,
                    ),
                )
                if cur.fetchone()[0] > 0:
                    status = "skipped"
                    error = "overlapping active retention policies are ambiguous"
            if status is None and (
                (not auto_enforce and not dry_run)
                or enforcement_status != "active"
                or legal_hold
                or method == "none"
                or not approved_by
                or not str(approved_by).strip()
                or not approval_date
                or not policy_owner
                or not str(policy_owner).strip()
                or isinstance(days, bool)
                or not isinstance(days, int)
                or days <= 0
            ):
                status = "skipped"
                if (
                    not approved_by
                    or not str(approved_by).strip()
                    or not approval_date
                    or not policy_owner
                    or not str(policy_owner).strip()
                    or days is None
                    or days <= 0
                ):
                    error = "policy requires an approved positive retention window"
            elif status is None and not entity_type:
                status, error = "error", "policy has no entity_type"
            if status is None:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public' AND c.relname = %s AND c.relkind IN ('r', 'p')
                    )
                """, (entity_type,))
                if not cur.fetchone()[0]:
                    status, error = "error", "configured entity table does not exist"
                else:
                    # Only tables with the standard governance columns are executable.
                    cur.execute("""
                        SELECT COUNT(*) FILTER (WHERE column_name = 'created_at'),
                               COUNT(*) FILTER (WHERE column_name = 'id' AND data_type = 'uuid'),
                               COUNT(*) FILTER (WHERE column_name = 'location_id'),
                               COUNT(*) FILTER (WHERE column_name = 'jurisdiction_code'),
                               COUNT(*) FILTER (WHERE column_name = 'purpose_code')
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s
                    """, (entity_type,))
                    column_counts = cur.fetchone()
                    has_created_at = column_counts[0] == 1
                    has_id = column_counts[1] == 1
                    if not has_created_at or not has_id:
                        status, error = "error", "entity table lacks created_at or a UUID id required for legal-hold checks"
                    else:
                        available_columns = {"created_at", "id"}
                        available_columns.update(
                            column
                            for index, column in enumerate(
                                ("location_id", "jurisdiction_code", "purpose_code"),
                                start=2,
                            )
                            if column_counts[index] == 1
                        )
                        scope_filters, scope_parameters, scope_error = _retention_scope_filters(
                            available_columns=available_columns,
                            location_id=str(location_id) if location_id else None,
                            jurisdiction_code=jurisdiction_code,
                            purpose_code=purpose_code,
                        )
                        if scope_error:
                            status, error = "skipped", scope_error
                        # entity_type is interpolated as a SQL identifier; allow only
                        # snake_case table names to prevent identifier injection.
                        if not scope_error and not re.match(r"^[a-z_]+$", entity_type or ""):
                            status, error = "error", "invalid entity_type"
                        elif not scope_error:
                            quoted = '"' + entity_type.replace('"', '""') + '"'
                            where = "created_at < NOW() - make_interval(days => %s)"
                            params = [days]
                            where += " AND NOT EXISTS (SELECT 1 FROM data_retention_legal_hold hold WHERE hold.entity_type = %s AND hold.entity_id = {entity}.id AND hold.released_at IS NULL)".format(entity=quoted)
                            params.append(entity_type)
                            if scope_filters:
                                where += " AND " + " AND ".join(scope_filters)
                                params.extend(scope_parameters)
                            cur.execute(f"SELECT COUNT(*) FROM {quoted} WHERE {where}", params)
                            candidates = cur.fetchone()[0]
                            if not dry_run and method == "soft_delete":
                                cur.execute("""
                                    SELECT EXISTS (SELECT 1 FROM information_schema.columns
                                    WHERE table_schema = 'public' AND table_name = %s AND column_name = 'deleted_at')
                                """, (entity_type,))
                                if cur.fetchone()[0]:
                                    cur.execute(f"UPDATE {quoted} SET deleted_at = NOW() WHERE {where} AND deleted_at IS NULL", params)
                                    affected = cur.rowcount
                                    status = "completed"
                                else:
                                    status, error = "error", "soft_delete requires deleted_at"
                            else:
                                status = "dry_run" if dry_run else "error"
                                if not dry_run:
                                    error = f"unsupported executable deletion method: {method}"
            cur.execute("""
                INSERT INTO data_retention_enforcement_log
                    (policy_id, actor, dry_run, status, candidates, affected, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (policy_id, normalized_actor, dry_run, status, candidates, affected, error))
            if status == "completed" and not dry_run:
                cur.execute(
                    "UPDATE data_retention_policy "
                    "SET last_enforced_at = NOW(), updated_at = NOW() WHERE id = %s",
                    (policy_id,),
                )
            results.append({"policy_id": str(policy_id), "status": status, "candidates": candidates, "affected": affected, "error": error})
        conn.commit()
        return {"actor": normalized_actor, "dry_run": dry_run, "policies": results, "total": len(results)}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


# ============================================================
# Governance Summary
# ============================================================

def get_governance_summary(conn, location_id: str) -> dict:
    """Aggregated governance metrics for a location."""
    cur = conn.cursor()

    try:
        # Consent summary
        cur.execute(
            """
            SELECT data_category,
                   COUNT(*) AS total_consents,
                   COUNT(*) FILTER (WHERE status = 'granted') AS granted,
                   COUNT(*) FILTER (WHERE status = 'withdrawn') AS withdrawn,
                   COUNT(*) FILTER (WHERE expires_at IS NOT NULL AND expires_at < NOW()) AS expired
            FROM farmer_consent
            WHERE location_id = %s
            GROUP BY data_category
            ORDER BY data_category
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        consent_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        consent_by_category = {}
        total_granted = 0
        total_withdrawn = 0
        for r in consent_rows:
            consent_by_category[r["data_category"]] = {
                "total": r["total_consents"],
                "granted": r["granted"],
                "withdrawn": r["withdrawn"],
                "expired": r["expired"],
            }
            total_granted += r["granted"]
            total_withdrawn += r["withdrawn"]

        # Access events summary
        cur.execute(
            """
            SELECT COUNT(*) AS total_accesses,
                   COUNT(*) FILTER (WHERE status = 'denied') AS denied,
                   COUNT(*) FILTER (WHERE access_type = 'read') AS reads,
                   COUNT(*) FILTER (WHERE access_type = 'write') AS writes,
                   COUNT(*) FILTER (WHERE access_type = 'export') AS exports,
                   COUNT(*) FILTER (WHERE access_type = 'share') AS shares
            FROM data_access_log
            WHERE location_id = %s
              AND accessed_at >= NOW() - INTERVAL '30 days'
            """,
            (location_id,),
        )
        access_row = cur.fetchone()
        access_summary = {
            "total_events_30d": int(access_row[0]) if access_row[0] else 0,
            "denied_30d": int(access_row[1]) if access_row[1] else 0,
            "reads_30d": int(access_row[2]) if access_row[2] else 0,
            "writes_30d": int(access_row[3]) if access_row[3] else 0,
            "exports_30d": int(access_row[4]) if access_row[4] else 0,
            "shares_30d": int(access_row[5]) if access_row[5] else 0,
        }

        # Active sharing agreements
        cur.execute(
            """
            SELECT COUNT(*) AS active_agreements
            FROM data_sharing_agreement
            WHERE (provider_id IN (SELECT farmer_id FROM farmer_consent WHERE location_id = %s)
                   OR consumer_id IN (SELECT farmer_id FROM farmer_consent WHERE location_id = %s))
              AND status = 'active'
            """,
            (location_id, location_id),
        )
        agreement_row = cur.fetchone()
        active_agreements = int(agreement_row[0]) if agreement_row[0] else 0

        # Pending portability requests
        cur.execute(
            """
            SELECT COUNT(*) AS pending_requests
            FROM data_portability_request
            WHERE location_id = %s AND status IN ('pending', 'processing')
            """,
            (location_id,),
        )
        port_row = cur.fetchone()
        pending_portability = int(port_row[0]) if port_row[0] else 0

        # Retention policies
        cur.execute(
            """
            SELECT COUNT(*) AS policies,
                   COUNT(*) FILTER (WHERE auto_enforce = TRUE) AS auto_enforce
            FROM data_retention_policy
            WHERE (location_id = %s OR location_id IS NULL)
              AND status = 'active'
            """,
            (location_id,),
        )
        ret_row = cur.fetchone()
        retention_summary = {
            "active_policies": int(ret_row[0]) if ret_row[0] else 0,
            "auto_enforce_count": int(ret_row[1]) if ret_row[1] else 0,
        }

        cur.close()

        consent_rate = (
            round(total_granted / (total_granted + total_withdrawn) * 100, 1)
            if (total_granted + total_withdrawn) > 0
            else 0
        )

        return {
            "location_id": location_id,
            "consent": {
                "by_category": consent_by_category,
                "total_granted": total_granted,
                "total_withdrawn": total_withdrawn,
                "consent_rate_pct": consent_rate,
            },
            "access_audit": access_summary,
            "sharing_agreements": {
                "active": active_agreements,
            },
            "portability": {
                "pending_requests": pending_portability,
            },
            "retention": retention_summary,
        }
    finally:
        cur.close()
