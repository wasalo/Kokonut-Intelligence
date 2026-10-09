#!/usr/bin/env python3
"""
Farmer Identity & Access Management

Provides farmer profile management, credential verification,
KYC workflows, role-based access control, data sharing consent,
and device registration.

Usage:
    python3 -m services.analytics.farmer_identity create-profile --first-name John --location-id UUID
    python3 -m services.analytics.farmer_identity update-profile --farmer-id UUID --last-name Doe
    python3 -m services.analytics.farmer_identity get-profile --farmer-id UUID
    python3 -m services.analytics.farmer_identity list-farmers --location-id UUID
    python3 -m services.analytics.farmer_identity add-credential --farmer-id UUID --type organic_cert --name "Organic Certificate"
    python3 -m services.analytics.farmer_identity verify-credential --credential-id UUID
    python3 -m services.analytics.farmer_identity get-credentials --farmer-id UUID
    python3 -m services.analytics.farmer_identity create-kyc --farmer-id UUID --method national_id
    python3 -m services.analytics.farmer_identity verify-kyc --kyc-id UUID --status approved --verified-by UUID
    python3 -m services.analytics.farmer_identity assign-role --farmer-id UUID --role farmer
    python3 -m services.analytics.farmer_identity check-permission --farmer-id UUID --resource farm --action read
    python3 -m services.analytics.farmer_identity record-consent --farmer-id UUID --data-type soil_data --recipient-type buyer
    python3 -m services.analytics.farmer_identity register-device --farmer-id UUID --device-id DEV001 --device-type phone
    python3 -m services.analytics.farmer_identity access-matrix --location-id UUID
    python3 -m services.analytics.farmer_identity directory --location-id UUID
"""

import json
import uuid
from datetime import date, datetime
from typing import List

from ..common.logging import get_logger

logger = get_logger("analytics.farmer_identity")


# ============================================================
# Farmer Profile Management
# ============================================================

def create_profile(
    conn,
    first_name: str,
    last_name: str = None,
    date_of_birth: date = None,
    gender: str = None,
    phone: str = None,
    email: str = None,
    national_id_type: str = None,
    national_id_number: str = None,
    national_id_country: str = None,
    location_id: str = None,
    village: str = None,
    district: str = None,
    province: str = None,
    country: str = None,
    postal_code: str = None,
    farm_size_ha: float = None,
    primary_crops: List[str] = None,
    farming_type: str = None,
    years_farming: int = None,
    metadata: dict = None,
) -> dict:
    """Create a new farmer profile."""
    cur = conn.cursor()
    farmer_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO farmer_profile (
                id, location_id, first_name, last_name, date_of_birth, gender,
                phone, email, national_id_type, national_id_number, national_id_country,
                village, district, province, country, postal_code,
                farm_size_ha, primary_crops, farming_type, years_farming,
                metadata, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s::jsonb, 'active'
            )
            RETURNING id, created_at
            """,
            (
                farmer_id, location_id, first_name, last_name, date_of_birth, gender,
                phone, email, national_id_type, national_id_number, national_id_country,
                village, district, province, country, postal_code,
                farm_size_ha, primary_crops or [], farming_type, years_farming,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Created farmer profile %s for %s %s", farmer_id, first_name, last_name or "")

        return {
            "farmer_id": farmer_id,
            "first_name": first_name,
            "last_name": last_name,
            "location_id": location_id,
            "status": "active",
            "created_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


def update_profile(
    conn,
    farmer_id: str,
    updates: dict,
) -> dict:
    """Update farmer profile fields."""
    cur = conn.cursor()

    allowed_fields = {
        "first_name", "last_name", "date_of_birth", "gender",
        "phone", "email", "national_id_type", "national_id_number", "national_id_country",
        "village", "district", "province", "country", "postal_code",
        "farm_size_ha", "primary_crops", "farming_type", "years_farming",
        "kyc_status", "status", "metadata",
    }

    filtered = {k: v for k, v in updates.items() if k in allowed_fields}
    if not filtered:
        cur.close()
        return {"error": "No valid fields to update"}

    set_parts = []
    params = []
    for k, v in filtered.items():
        if k == "metadata":
            set_parts.append(f"{k} = %s::jsonb")
            params.append(json.dumps(v))
        else:
            set_parts.append(f"{k} = %s")
            params.append(v)

    set_parts.append("updated_at = NOW()")
    params.append(farmer_id)

    try:
        cur.execute(
            f"""
            UPDATE farmer_profile
            SET {', '.join(set_parts)}
            WHERE id = %s
            RETURNING id, updated_at
            """,
            tuple(params),
        )
        row = cur.fetchone()
        conn.commit()

        if not row:
            return {"error": f"Farmer {farmer_id} not found"}

        logger.info("Updated farmer profile %s", farmer_id)

        return {
            "farmer_id": farmer_id,
            "updated_fields": list(filtered.keys()),
            "updated_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


def get_profile(conn, farmer_id: str) -> dict:
    """Get farmer profile by ID."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, location_id, first_name, last_name, date_of_birth, gender,
                   phone, phone_verified, email, email_verified,
                   village, district, province, country, postal_code,
                   farm_size_ha, primary_crops, farming_type, years_farming,
                   national_id_type, national_id_number, national_id_country,
                   kyc_status, kyc_verified_at, status, metadata,
                   created_at, updated_at
            FROM farmer_profile
            WHERE id = %s
            """,
            (farmer_id,),
        )
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        cur.close()

        if not row:
            return {"error": f"Farmer {farmer_id} not found"}

        data = dict(zip(cols, row))
        data["date_of_birth"] = data["date_of_birth"].isoformat() if data["date_of_birth"] else None
        data["kyc_verified_at"] = data["kyc_verified_at"].isoformat() if data["kyc_verified_at"] else None
        data["created_at"] = data["created_at"].isoformat() if data["created_at"] else None
        data["updated_at"] = data["updated_at"].isoformat() if data["updated_at"] else None

        return data
    finally:
        cur.close()


def list_farmers(
    conn,
    location_id: str = None,
    status: str = "active",
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """List farmers, optionally filtered by location and status."""
    cur = conn.cursor()

    where_parts = ["1=1"]
    params = []

    if location_id:
        where_parts.append("location_id = %s")
        params.append(location_id)
    if status:
        where_parts.append("status = %s")
        params.append(status)

    where_clause = " AND ".join(where_parts)

    try:
        cur.execute(
            f"""
            SELECT id, first_name, last_name, phone, email,
                   village, district, farm_size_ha, primary_crops,
                   farming_type, kyc_status, status, created_at
            FROM farmer_profile
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params) + (limit, offset),
        )
        cols = [d[0] for d in cur.description]
        farmers = [dict(zip(cols, row)) for row in cur.fetchall()]

        for f in farmers:
            f["created_at"] = f["created_at"].isoformat() if f["created_at"] else None

        cur.execute(
            f"SELECT COUNT(*) FROM farmer_profile WHERE {where_clause}",
            tuple(params),
        )
        total = cur.fetchone()[0]
        cur.close()

        return {
            "farmers": farmers,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        cur.close()


# ============================================================
# Credential Management
# ============================================================

def add_credential(
    conn,
    farmer_id: str,
    credential_type: str,
    credential_name: str,
    issuing_authority: str = None,
    credential_number: str = None,
    credential_url: str = None,
    issued_date: date = None,
    expiry_date: date = None,
    evidence_urls: List[str] = None,
    evidence_hashes: List[str] = None,
    metadata: dict = None,
) -> dict:
    """Add a credential to a farmer profile."""
    cur = conn.cursor()
    credential_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO farmer_credential (
                id, farmer_id, credential_type, credential_name,
                issuing_authority, credential_number, credential_url,
                issued_date, expiry_date,
                evidence_urls, evidence_hashes,
                metadata, status
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s::jsonb, 'active'
            )
            RETURNING id, created_at
            """,
            (
                credential_id, farmer_id, credential_type, credential_name,
                issuing_authority, credential_number, credential_url,
                issued_date, expiry_date,
                evidence_urls or [], evidence_hashes or [],
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Added credential %s (%s) for farmer %s", credential_id, credential_type, farmer_id)

        return {
            "credential_id": credential_id,
            "farmer_id": farmer_id,
            "credential_type": credential_type,
            "credential_name": credential_name,
            "status": "active",
            "created_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


def verify_credential(conn, credential_id: str, verified_by: str = None) -> dict:
    """Mark a credential as verified."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE farmer_credential
            SET is_verified = TRUE,
                verified_by = %s,
                verified_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, credential_type, credential_name, verified_at
            """,
            (verified_by, credential_id),
        )
        row = cur.fetchone()
        conn.commit()

        if not row:
            return {"error": f"Credential {credential_id} not found"}

        logger.info("Verified credential %s", credential_id)

        return {
            "credential_id": row[0],
            "credential_type": row[1],
            "credential_name": row[2],
            "is_verified": True,
            "verified_at": row[3].isoformat() if row[3] else None,
        }
    finally:
        cur.close()


def get_credentials(conn, farmer_id: str) -> dict:
    """Get all credentials for a farmer."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, credential_type, credential_name, issuing_authority,
                   credential_number, credential_url, issued_date, expiry_date,
                   is_verified, verified_by, verified_at,
                   evidence_urls, status, created_at
            FROM farmer_credential
            WHERE farmer_id = %s
            ORDER BY created_at DESC
            """,
            (farmer_id,),
        )
        cols = [d[0] for d in cur.description]
        creds = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()

        for c in creds:
            c["issued_date"] = c["issued_date"].isoformat() if c["issued_date"] else None
            c["expiry_date"] = c["expiry_date"].isoformat() if c["expiry_date"] else None
            c["verified_at"] = c["verified_at"].isoformat() if c["verified_at"] else None
            c["created_at"] = c["created_at"].isoformat() if c["created_at"] else None

        return {
            "farmer_id": farmer_id,
            "credentials": creds,
            "total": len(creds),
        }
    finally:
        cur.close()


# ============================================================
# KYC Verification
# ============================================================

def create_kyc(
    conn,
    farmer_id: str,
    verification_method: str,
    document_type: str = None,
    document_url: str = None,
    document_hash: str = None,
    provider: str = None,
    did_identifier: str = None,
    credential_jwt: str = None,
    metadata: dict = None,
) -> dict:
    """Create a KYC verification record."""
    cur = conn.cursor()
    kyc_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO kyc_verification (
                id, farmer_id, verification_method, provider,
                document_type, document_url, document_hash,
                did_identifier, credential_jwt,
                verification_status, metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                'pending', %s::jsonb
            )
            RETURNING id, created_at
            """,
            (
                kyc_id, farmer_id, verification_method, provider,
                document_type, document_url, document_hash,
                did_identifier, credential_jwt,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()

        cur.execute(
            "UPDATE farmer_profile SET kyc_status = 'pending', updated_at = NOW() WHERE id = %s",
            (farmer_id,),
        )
        conn.commit()

        logger.info("Created KYC record %s for farmer %s", kyc_id, farmer_id)

        return {
            "kyc_id": kyc_id,
            "farmer_id": farmer_id,
            "verification_method": verification_method,
            "verification_status": "pending",
            "created_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


def verify_kyc(
    conn,
    kyc_id: str,
    status: str,
    verified_by: str = None,
    notes: str = None,
    confidence_score: float = None,
) -> dict:
    """Approve or reject a KYC verification."""
    cur = conn.cursor()

    if status not in ("approved", "rejected"):
        cur.close()
        return {"error": "Status must be 'approved' or 'rejected'"}

    try:
        cur.execute(
            """
            UPDATE kyc_verification
            SET verification_status = %s,
                reviewed_by = %s,
                reviewed_at = NOW(),
                rejection_reason = %s,
                confidence_score = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, farmer_id, verification_method, verification_status, reviewed_at
            """,
            (status, verified_by, notes, confidence_score, kyc_id),
        )
        row = cur.fetchone()
        conn.commit()

        if not row:
            return {"error": f"KYC record {kyc_id} not found"}

        farmer_id = row[1]
        kyc_status = "verified" if status == "approved" else "rejected"
        verified_at = row[4] if status == "approved" else None

        cur2 = conn.cursor()
        cur2.execute(
            """
            UPDATE farmer_profile
            SET kyc_status = %s,
                kyc_verified_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (kyc_status, verified_at, farmer_id),
        )
        conn.commit()
        cur2.close()

        logger.info("KYC %s %s for farmer %s", kyc_id, status, farmer_id)

        return {
            "kyc_id": row[0],
            "farmer_id": farmer_id,
            "verification_method": row[2],
            "verification_status": row[3],
            "reviewed_at": row[4].isoformat() if row[4] else None,
        }
    finally:
        cur.close()


# ============================================================
# Role-Based Access Control
# ============================================================

def assign_role(
    conn,
    farmer_id: str,
    role: str,
    scope: str = "location",
    location_id: str = None,
    permissions: List[str] = None,
    expires_at: datetime = None,
    assigned_by: str = None,
    metadata: dict = None,
) -> dict:
    """Assign a role to a farmer."""
    cur = conn.cursor()
    assignment_id = str(uuid.uuid4())

    if permissions is None:
        cur.execute(
            "SELECT default_permissions FROM farmer_role WHERE name = %s",
            (role,),
        )
        row = cur.fetchone()
        permissions = row[0] if row else []

    try:
        cur.execute(
            """
            INSERT INTO role_assignment (
                id, farmer_id, location_id, role, scope, permissions,
                expires_at, assigned_by, metadata, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s::jsonb,
                %s, %s, %s::jsonb, 'active'
            )
            RETURNING id, assigned_at
            """,
            (
                assignment_id, farmer_id, location_id, role, scope,
                json.dumps(permissions), expires_at, assigned_by,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Assigned role %s to farmer %s (scope=%s)", role, farmer_id, scope)

        return {
            "assignment_id": assignment_id,
            "farmer_id": farmer_id,
            "role": role,
            "scope": scope,
            "permissions": permissions,
            "status": "active",
            "assigned_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


def check_permission(conn, farmer_id: str, resource: str, action: str) -> dict:
    """Check if a farmer has a specific permission."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT role, scope, permissions
            FROM role_assignment
            WHERE farmer_id = %s
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            """,
            (farmer_id,),
        )
        rows = cur.fetchall()
        cur.close()

        target = f"{resource}:{action}"
        wildcard_resource = f"*:{action}"
        wildcard_action = f"{resource}:*"
        wildcard_all = "*:*"

        for row in rows:
            perms = row[2] or []
            if target in perms or wildcard_resource in perms or wildcard_action in perms or wildcard_all in perms:
                return {
                    "farmer_id": farmer_id,
                    "resource": resource,
                    "action": action,
                    "allowed": True,
                    "role": row[0],
                    "scope": row[1],
                }

        return {
            "farmer_id": farmer_id,
            "resource": resource,
            "action": action,
            "allowed": False,
        }
    finally:
        cur.close()


# ============================================================
# Data Sharing Consent
# ============================================================

def record_data_sharing_consent(
    conn,
    farmer_id: str,
    data_type: str,
    recipient_type: str,
    recipient_id: str = None,
    recipient_name: str = None,
    purpose: str = None,
    legal_basis: str = "consent",
    retention_days: int = 365,
    is_reciprocal: bool = False,
    consent_given: bool = True,
    data_scope: str = None,
    metadata: dict = None,
) -> dict:
    """Record data sharing consent from a farmer."""
    cur = conn.cursor()
    consent_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO data_sharing_consent (
                id, farmer_id, data_type, data_scope,
                recipient_type, recipient_id, recipient_name,
                purpose, legal_basis, retention_days, is_reciprocal,
                consent_given, status, metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, 'active', %s::jsonb
            )
            RETURNING id, consent_date
            """,
            (
                consent_id, farmer_id, data_type, data_scope,
                recipient_type, recipient_id, recipient_name,
                purpose, legal_basis, retention_days, is_reciprocal,
                consent_given, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Recorded consent %s for farmer %s (data=%s, recipient=%s)", consent_id, farmer_id, data_type, recipient_type)

        return {
            "consent_id": consent_id,
            "farmer_id": farmer_id,
            "data_type": data_type,
            "recipient_type": recipient_type,
            "consent_given": consent_given,
            "status": "active",
            "consent_date": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# Device Registration
# ============================================================

def register_device(
    conn,
    farmer_id: str,
    device_id: str,
    device_type: str,
    location_id: str = None,
    device_name: str = None,
    os_type: str = None,
    os_version: str = None,
    app_version: str = None,
    has_camera: bool = False,
    has_gps: bool = False,
    has_offline: bool = True,
    storage_mb: int = None,
    device_token: str = None,
    push_provider: str = None,
    metadata: dict = None,
) -> dict:
    """Register a mobile device for a farmer."""
    cur = conn.cursor()
    registration_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO device_registration (
                id, farmer_id, location_id, device_id, device_name, device_type,
                os_type, os_version, app_version,
                has_camera, has_gps, has_offline, storage_mb,
                device_token, push_provider, metadata, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s::jsonb, 'active'
            )
            ON CONFLICT (device_id) DO UPDATE SET
                farmer_id = EXCLUDED.farmer_id,
                location_id = EXCLUDED.location_id,
                device_name = EXCLUDED.device_name,
                os_type = EXCLUDED.os_type,
                os_version = EXCLUDED.os_version,
                app_version = EXCLUDED.app_version,
                updated_at = NOW()
            RETURNING id, created_at
            """,
            (
                registration_id, farmer_id, location_id, device_id, device_name, device_type,
                os_type, os_version, app_version,
                has_camera, has_gps, has_offline, storage_mb,
                device_token, push_provider, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Registered device %s for farmer %s", device_id, farmer_id)

        return {
            "registration_id": row[0],
            "farmer_id": farmer_id,
            "device_id": device_id,
            "device_type": device_type,
            "status": "active",
            "created_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# Access Matrix & Directory
# ============================================================

def get_access_matrix(conn, location_id: str = None) -> dict:
    """Get role-based access matrix for a location."""
    cur = conn.cursor()

    try:
        if location_id:
            cur.execute(
                """
                SELECT farmer_id, farmer_name, role, scope, permissions,
                       status, assigned_at, expires_at, location_name,
                       kyc_status, effective_status
                FROM v_access_matrix
                WHERE location_id = %s
                ORDER BY farmer_name, role
                """,
                (location_id,),
            )
        else:
            cur.execute(
                """
                SELECT farmer_id, farmer_name, role, scope, permissions,
                       status, assigned_at, expires_at, location_name,
                       kyc_status, effective_status
                FROM v_access_matrix
                ORDER BY location_name, farmer_name, role
                """
            )

        cols = [d[0] for d in cur.description]
        entries = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()

        for e in entries:
            e["assigned_at"] = e["assigned_at"].isoformat() if e["assigned_at"] else None
            e["expires_at"] = e["expires_at"].isoformat() if e["expires_at"] else None

        return {
            "location_id": location_id,
            "entries": entries,
            "total": len(entries),
        }
    finally:
        cur.close()


def get_farmer_directory(conn, location_id: str = None) -> dict:
    """Get farmer directory with verification status."""
    cur = conn.cursor()

    try:
        if location_id:
            cur.execute(
                """
                SELECT farmer_id, first_name, last_name, phone, email,
                       village, district, province, country,
                       farm_size_ha, primary_crops, farming_type,
                       kyc_status, kyc_verified_at, location_name,
                       primary_role, role_scope,
                       active_credentials, active_consents, registered_devices,
                       status, created_at, updated_at
                FROM v_farmer_directory
                WHERE location_id = %s
                ORDER BY last_name, first_name
                """,
                (location_id,),
            )
        else:
            cur.execute(
                """
                SELECT farmer_id, first_name, last_name, phone, email,
                       village, district, province, country,
                       farm_size_ha, primary_crops, farming_type,
                       kyc_status, kyc_verified_at, location_name,
                       primary_role, role_scope,
                       active_credentials, active_consents, registered_devices,
                       status, created_at, updated_at
                FROM v_farmer_directory
                ORDER BY location_name, last_name, first_name
                """
            )

        cols = [d[0] for d in cur.description]
        farmers = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()

        for f in farmers:
            f["kyc_verified_at"] = f["kyc_verified_at"].isoformat() if f["kyc_verified_at"] else None
            f["created_at"] = f["created_at"].isoformat() if f["created_at"] else None
            f["updated_at"] = f["updated_at"].isoformat() if f["updated_at"] else None

        return {
            "location_id": location_id,
            "farmers": farmers,
            "total": len(farmers),
        }
    finally:
        cur.close()
