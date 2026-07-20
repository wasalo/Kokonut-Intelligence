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
    python -m services.analytics.data_governance set-retention --data-category soil --retention-days 2555 --action soft_delete
    python -m services.analytics.data_governance governance-summary --location-id UUID
"""

import argparse
import json
import re
import uuid
from datetime import datetime, date, timezone, timedelta

from ..common.logging import get_logger

logger = get_logger("analytics.data_governance")


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
                INSERT INTO access_audit_log
                    (accessor_id, data_category, resource_type, resource_id,
                     access_type, purpose, accessor_type, consent_id, status)
                VALUES (%s, 'portability_export', 'data_portability_request', %s,
                        'write', 'portability_fulfillment', 'system', NULL, 'allowed')
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
    retention_days: int,
    action: str = "soft_delete",
    entity_type: str = None,
    location_id: str = None,
    auto_enforce: bool = True,
    policy_owner: str = None,
    metadata: dict = None,
) -> dict:
    """Set a data retention policy for a category."""
    cur = conn.cursor()
    policy_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO data_retention_policy
                (id, data_category, entity_type, location_id,
                 retention_days, deletion_method, auto_enforce,
                 policy_owner, status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s::jsonb)
            ON CONFLICT DO NOTHING
            RETURNING id, created_at
            """,
            (
                policy_id, data_category, entity_type, location_id,
                retention_days, action, auto_enforce, policy_owner,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "policy_id": policy_id,
            "data_category": data_category,
            "retention_days": retention_days,
            "deletion_method": action,
            "auto_enforce": auto_enforce,
            "status": "active",
            "created_at": row[1].isoformat() if row else None,
        }
    finally:
        cur.close()


def enforce_retention_policies(conn, actor: str, dry_run: bool = False) -> dict:
    """Execute a governed retention sweep for configured entity tables.

    ``entity_type`` is deliberately treated as a table identifier only after
    checking it against PostgreSQL metadata. Policies without a target table,
    legal holds, paused policies, and ``none`` actions are recorded as skipped.
    """
    cur = conn.cursor()
    results = []
    try:
        cur.execute("""
            SELECT id, data_category, entity_type, location_id, retention_days,
                   deletion_method, legal_hold, auto_enforce, enforcement_status
            FROM data_retention_policy
            WHERE status = 'active'
            ORDER BY priority DESC, created_at
        """)
        policies = cur.fetchall()
        for policy_id, category, entity_type, location_id, days, method, legal_hold, auto_enforce, enforcement_status in policies:
            status, candidates, affected, error = "skipped", 0, 0, None
            if not auto_enforce or enforcement_status != "active" or legal_hold or method == "none":
                status = "skipped"
            elif not entity_type:
                status, error = "error", "policy has no entity_type"
            else:
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
                        SELECT COUNT(*) FILTER (WHERE created_at < NOW() - make_interval(days => %s))
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s AND column_name = 'created_at'
                    """, (days, entity_type))
                    has_created_at = cur.fetchone()[0] == 1
                    if not has_created_at:
                        status, error = "error", "entity table lacks created_at"
                    else:
                        # entity_type is interpolated as a SQL identifier; allow only
                        # snake_case table names to prevent identifier injection.
                        if not re.match(r"^[a-z_]+$", entity_type or ""):
                            status, error = "error", "invalid entity_type"
                            continue
                        quoted = '"' + entity_type.replace('"', '""') + '"'
                        where = f"created_at < NOW() - make_interval(days => %s)"
                        params = [days]
                        if location_id:
                            where += " AND location_id = %s"
                            params.append(location_id)
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
            """, (policy_id, actor, dry_run, status, candidates, affected, error))
            cur.execute("UPDATE data_retention_policy SET last_enforced_at = NOW(), updated_at = NOW() WHERE id = %s", (policy_id,))
            results.append({"policy_id": str(policy_id), "status": status, "candidates": candidates, "affected": affected, "error": error})
        conn.commit()
        return {"actor": actor, "dry_run": dry_run, "policies": results, "total": len(results)}
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


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Data governance & interoperability")
    sub = parser.add_subparsers(dest="command")

    # record-consent
    rc = sub.add_parser("record-consent", help="Record consent grant/withdrawal")
    rc.add_argument("--farmer-id", required=True)
    rc.add_argument("--data-category", required=True)
    rc.add_argument("--scope", required=True)
    rc.add_argument("--status", default="granted", choices=["granted", "withdrawn", "pending"])
    rc.add_argument("--method", default="digital_form")
    rc.add_argument("--location-id")
    rc.add_argument("--expires-at", help="Expiry datetime ISO format")
    rc.add_argument("--evidence-ref")
    rc.add_argument("--legal-basis")
    rc.add_argument("--json", action="store_true")

    # withdraw-consent
    wc = sub.add_parser("withdraw-consent", help="Withdraw consent")
    wc.add_argument("--consent-id", required=True)
    wc.add_argument("--reason")
    wc.add_argument("--actor-id", required=True)
    wc.add_argument("--json", action="store_true")

    # consent-status
    cs = sub.add_parser("consent-status", help="Get consent status per category")
    cs.add_argument("--farmer-id", required=True)
    cs.add_argument("--json", action="store_true")

    # check-consent
    cc = sub.add_parser("check-consent", help="Check specific consent")
    cc.add_argument("--farmer-id", required=True)
    cc.add_argument("--data-category", required=True)
    cc.add_argument("--scope", required=True)
    cc.add_argument("--json", action="store_true")

    # log-access
    la = sub.add_parser("log-access", help="Log data access event")
    la.add_argument("--accessor-id", required=True)
    la.add_argument("--data-category", required=True)
    la.add_argument("--resource-type", required=True)
    la.add_argument("--access-type", required=True,
                    choices=["read", "write", "export", "share", "delete", "list", "aggregate", "download"])
    la.add_argument("--purpose")
    la.add_argument("--resource-id")
    la.add_argument("--location-id")
    la.add_argument("--accessor-role")
    la.add_argument("--accessor-type", default="user")
    la.add_argument("--access-method")
    la.add_argument("--consent-id")
    la.add_argument("--status", default="success", choices=["success", "denied", "partial", "error"])
    la.add_argument("--denial-reason")
    la.add_argument("--records-affected", type=int, default=0)
    la.add_argument("--json", action="store_true")

    # access-audit
    aa = sub.add_parser("access-audit", help="Get access audit trail")
    aa.add_argument("--farmer-id", required=True)
    aa.add_argument("--days", type=int, default=30)
    aa.add_argument("--json", action="store_true")

    # request-portability
    rp = sub.add_parser("request-portability", help="Request data export")
    rp.add_argument("--farmer-id", required=True)
    rp.add_argument("--format", dest="format_type", default="json",
                    choices=["json", "csv", "geojson", "xml", "rdf_turtle", "jsonld", "parquet", "excel"])
    rp.add_argument("--scope", default="all", choices=["all", "location", "category", "filtered"])
    rp.add_argument("--data-categories", help="Comma-separated categories")
    rp.add_argument("--location-id")
    rp.add_argument("--requested-by")
    rp.add_argument("--authorization-ref")
    rp.add_argument("--include-metadata", action="store_true", default=True)
    rp.add_argument("--json", action="store_true")

    # fulfill-portability
    fp = sub.add_parser("fulfill-portability", help="Mark portability request as fulfilled")
    fp.add_argument("--request-id", required=True)
    fp.add_argument("--file-path")
    fp.add_argument("--output-hash")
    fp.add_argument("--output-size", type=int)
    fp.add_argument("--record-count", type=int, default=0)
    fp.add_argument("--owner-id", required=True)
    fp.add_argument("--fulfilled-by", required=True)
    fp.add_argument("--authorization-ref", required=True)
    fp.add_argument("--json", action="store_true")

    # portability-requests
    pr = sub.add_parser("portability-requests", help="List portability requests")
    pr.add_argument("--farmer-id", required=True)
    pr.add_argument("--actor-id", required=True)
    pr.add_argument("--json", action="store_true")

    # create-agreement
    ca = sub.add_parser("create-agreement", help="Create data sharing agreement")
    ca.add_argument("--provider-id", required=True)
    ca.add_argument("--consumer-id", required=True)
    ca.add_argument("--data-categories", required=True, help="Comma-separated categories")
    ca.add_argument("--purpose", required=True)
    ca.add_argument("--provider-type", default="farmer")
    ca.add_argument("--consumer-type", default="organization")
    ca.add_argument("--legal-basis")
    ca.add_argument("--commercial-use", action="store_true")
    ca.add_argument("--retention-days", type=int)
    ca.add_argument("--json", action="store_true")

    # sharing-agreements
    sa = sub.add_parser("sharing-agreements", help="List sharing agreements")
    sa.add_argument("--farmer-id", required=True)
    sa.add_argument("--json", action="store_true")

    # set-retention
    sr = sub.add_parser("set-retention", help="Set retention policy")
    sr.add_argument("--data-category", required=True)
    sr.add_argument("--retention-days", type=int, required=True)
    sr.add_argument("--action", default="soft_delete",
                    choices=["soft_delete", "hard_delete", "anonymize", "archive", "none"])
    sr.add_argument("--entity-type")
    sr.add_argument("--location-id")
    sr.add_argument("--policy-owner")
    sr.add_argument("--json", action="store_true")

    es = sub.add_parser("enforce-retention", help="Run governed retention sweep")
    es.add_argument("--actor", required=True)
    es.add_argument("--dry-run", action="store_true")
    es.add_argument("--json", action="store_true")

    # governance-summary
    gs = sub.add_parser("governance-summary", help="Aggregated governance metrics")
    gs.add_argument("--location-id", required=True)
    gs.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if args.command is None:
        parser.print_help()
        return

    db = get_db()

    try:
        if args.command == "record-consent":
            exp = datetime.fromisoformat(args.expires_at) if args.expires_at else None
            result = record_consent(
                db, args.farmer_id, args.data_category, args.scope,
                status=args.status, method=args.method,
                location_id=args.location_id, expires_at=exp,
                evidence_ref=args.evidence_ref, legal_basis=args.legal_basis,
            )
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "withdraw-consent":
            result = withdraw_consent(db, args.consent_id, reason=args.reason, actor_id=args.actor_id)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "consent-status":
            result = get_consent_status(db, args.farmer_id)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "check-consent":
            result = check_consent(db, args.farmer_id, args.data_category, args.scope)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "log-access":
            result = log_access(
                db, args.accessor_id, args.data_category, args.resource_type,
                args.access_type, purpose=args.purpose,
                resource_id=args.resource_id, location_id=args.location_id,
                accessor_role=args.accessor_role, accessor_type=args.accessor_type,
                access_method=args.access_method, consent_id=args.consent_id,
                status=args.status, denial_reason=args.denial_reason,
                records_affected=args.records_affected,
            )
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "access-audit":
            result = get_access_audit(db, args.farmer_id, days=args.days)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "request-portability":
            cats = args.data_categories.split(",") if args.data_categories else None
            result = request_portability(
                db, args.farmer_id, format_type=args.format_type,
                scope=args.scope, data_categories=cats,
                location_id=args.location_id,
                requested_by=args.requested_by,
                authorization_ref=args.authorization_ref,
                include_metadata=args.include_metadata,
            )
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "fulfill-portability":
            result = fulfill_portability(
                db, args.request_id, file_path=args.file_path,
                output_hash=args.output_hash,
                output_size_bytes=args.output_size,
                record_count=args.record_count,
                owner_id=args.owner_id,
                fulfilled_by=args.fulfilled_by,
                authorization_ref=args.authorization_ref,
            )
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "portability-requests":
            result = get_portability_requests(db, args.farmer_id, actor_id=args.actor_id)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "create-agreement":
            cats = args.data_categories.split(",")
            result = create_sharing_agreement(
                db, args.provider_id, args.consumer_id, cats, args.purpose,
                provider_type=args.provider_type, consumer_type=args.consumer_type,
                legal_basis=args.legal_basis, commercial_use=args.commercial_use,
                retention_days=args.retention_days,
            )
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "sharing-agreements":
            result = get_sharing_agreements(db, args.farmer_id)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "set-retention":
            result = set_retention_policy(
                db, args.data_category, args.retention_days,
                action=args.action, entity_type=args.entity_type,
                location_id=args.location_id, policy_owner=args.policy_owner,
            )
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "governance-summary":
            result = get_governance_summary(db, args.location_id)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "enforce-retention":
            result = enforce_retention_policies(db, args.actor, dry_run=args.dry_run)
            print(json.dumps(result, indent=2, default=str))

    finally:
        db.close()


if __name__ == "__main__":
    main()
