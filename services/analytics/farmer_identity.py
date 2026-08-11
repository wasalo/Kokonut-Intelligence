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
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any

from services.common.commands import CommandLine
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


# ============================================================
# CLI
# ============================================================

cli = CommandLine("farmer_identity", "Farmer identity & access management")


def _cmd_create_profile(db, a):
    dob = date.fromisoformat(a.dob) if a.dob else None
    return create_profile(
        db, a.first_name,
        last_name=a.last_name,
        date_of_birth=dob,
        gender=a.gender,
        phone=a.phone,
        email=a.email,
        national_id_type=a.national_id_type,
        national_id_number=a.national_id_number,
        national_id_country=a.national_id_country,
        location_id=a.location_id,
        village=a.village,
        district=a.district,
        province=a.province,
        country=a.country,
        postal_code=a.postal_code,
        farm_size_ha=a.farm_size,
        primary_crops=a.crops,
        farming_type=a.farming_type,
        years_farming=a.years_farming,
    )


def _cmd_update_profile(db, a):
    updates = {}
    for field in ("first_name", "last_name", "gender", "phone", "email",
                  "national_id_type", "national_id_number", "national_id_country",
                  "village", "district", "province", "country", "postal_code",
                  "farming_type", "status"):
        val = getattr(a, field.replace("-", "_"), None)
        if val is not None:
            updates[field] = val
    if a.dob:
        updates["date_of_birth"] = date.fromisoformat(a.dob)
    if a.farm_size is not None:
        updates["farm_size_ha"] = a.farm_size
    if a.crops is not None:
        updates["primary_crops"] = a.crops
    if a.years_farming is not None:
        updates["years_farming"] = a.years_farming
    return update_profile(db, a.farmer_id, updates)


def _cmd_add_credential(db, a):
    issued = date.fromisoformat(a.issued_date) if a.issued_date else None
    expiry = date.fromisoformat(a.expiry_date) if a.expiry_date else None
    return add_credential(
        db, a.farmer_id, a.credential_type, a.credential_name,
        issuing_authority=a.issuing_authority,
        credential_number=a.credential_number,
        credential_url=a.credential_url,
        issued_date=issued,
        expiry_date=expiry,
    )


def _cmd_create_kyc(db, a):
    return create_kyc(
        db, a.farmer_id, a.verification_method,
        document_type=a.document_type,
        document_url=a.document_url,
        document_hash=a.document_hash,
        provider=a.provider,
        did_identifier=a.did_identifier,
        credential_jwt=a.credential_jwt,
    )


def _cmd_verify_kyc(db, a):
    return verify_kyc(
        db, a.kyc_id, a.status,
        verified_by=a.verified_by,
        notes=a.notes,
        confidence_score=a.confidence,
    )


def _cmd_assign_role(db, a):
    expires = datetime.fromisoformat(a.expires_at) if a.expires_at else None
    return assign_role(
        db, a.farmer_id, a.role,
        scope=a.scope,
        location_id=a.location_id,
        permissions=a.permissions,
        expires_at=expires,
        assigned_by=a.assigned_by,
    )


def _cmd_record_consent(db, a):
    return record_data_sharing_consent(
        db, a.farmer_id, a.data_type, a.recipient_type,
        recipient_id=a.recipient_id,
        recipient_name=a.recipient_name,
        purpose=a.purpose,
        legal_basis=a.legal_basis,
        retention_days=a.retention_days,
        is_reciprocal=a.reciprocal,
        consent_given=not a.no_consent,
        data_scope=a.data_scope,
    )


def _cmd_register_device(db, a):
    return register_device(
        db, a.farmer_id, a.device_id, a.device_type,
        location_id=a.location_id,
        device_name=a.device_name,
        os_type=a.os_type,
        os_version=a.os_version,
        app_version=a.app_version,
        has_camera=a.camera,
        has_gps=a.gps,
        has_offline=not a.no_offline,
        storage_mb=a.storage_mb,
    )


cli.subcommand("create-profile", "Create farmer profile") \
    .add("--first-name", required=True) \
    .add("--last-name") \
    .add("--dob", help="Date of birth YYYY-MM-DD") \
    .add("--gender") \
    .add("--phone") \
    .add("--email") \
    .add("--national-id-type") \
    .add("--national-id-number") \
    .add("--national-id-country") \
    .add("--location-id") \
    .add("--village") \
    .add("--district") \
    .add("--province") \
    .add("--country") \
    .add("--postal-code") \
    .add("--farm-size", type=float, help="Farm size in hectares") \
    .add("--crops", nargs="+", help="Primary crops") \
    .add("--farming-type") \
    .add("--years-farming", type=int) \
    .add("--json", action="store_true") \
    .run(_cmd_create_profile)

cli.subcommand("update-profile", "Update farmer profile") \
    .add("--farmer-id", required=True) \
    .add("--first-name") \
    .add("--last-name") \
    .add("--dob", help="Date of birth YYYY-MM-DD") \
    .add("--gender") \
    .add("--phone") \
    .add("--email") \
    .add("--national-id-type") \
    .add("--national-id-number") \
    .add("--national-id-country") \
    .add("--village") \
    .add("--district") \
    .add("--province") \
    .add("--country") \
    .add("--postal-code") \
    .add("--farm-size", type=float) \
    .add("--crops", nargs="+") \
    .add("--farming-type") \
    .add("--years-farming", type=int) \
    .add("--status") \
    .add("--json", action="store_true") \
    .run(_cmd_update_profile)

cli.subcommand("get-profile", "Get farmer profile") \
    .add("--farmer-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_profile(db, a.farmer_id))

cli.subcommand("list-farmers", "List farmers") \
    .add("--location-id") \
    .add("--status", default="active") \
    .add("--limit", type=int, default=100) \
    .add("--offset", type=int, default=0) \
    .add("--json", action="store_true") \
    .run(lambda db, a: list_farmers(db, a.location_id, a.status, a.limit, a.offset))

cli.subcommand("add-credential", "Add credential") \
    .add("--farmer-id", required=True) \
    .add("--type", required=True, dest="credential_type") \
    .add("--name", required=True, dest="credential_name") \
    .add("--issuing-authority") \
    .add("--number", dest="credential_number") \
    .add("--url", dest="credential_url") \
    .add("--issued-date", help="Issued date YYYY-MM-DD") \
    .add("--expiry-date", help="Expiry date YYYY-MM-DD") \
    .add("--json", action="store_true") \
    .run(_cmd_add_credential)

cli.subcommand("verify-credential", "Verify credential") \
    .add("--credential-id", required=True) \
    .add("--verified-by") \
    .add("--json", action="store_true") \
    .run(lambda db, a: verify_credential(db, a.credential_id, a.verified_by))

cli.subcommand("get-credentials", "Get credentials") \
    .add("--farmer-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_credentials(db, a.farmer_id))

cli.subcommand("create-kyc", "Create KYC record") \
    .add("--farmer-id", required=True) \
    .add("--method", required=True, dest="verification_method") \
    .add("--document-type") \
    .add("--document-url") \
    .add("--document-hash") \
    .add("--provider") \
    .add("--did-identifier") \
    .add("--credential-jwt") \
    .add("--json", action="store_true") \
    .run(_cmd_create_kyc)

cli.subcommand("verify-kyc", "Verify KYC") \
    .add("--kyc-id", required=True) \
    .add("--status", required=True, choices=["approved", "rejected"]) \
    .add("--verified-by") \
    .add("--notes") \
    .add("--confidence", type=float) \
    .add("--json", action="store_true") \
    .run(_cmd_verify_kyc)

cli.subcommand("assign-role", "Assign role") \
    .add("--farmer-id", required=True) \
    .add("--role", required=True) \
    .add("--scope", default="location") \
    .add("--location-id") \
    .add("--permissions", nargs="+") \
    .add("--expires-at", help="ISO datetime") \
    .add("--assigned-by") \
    .add("--json", action="store_true") \
    .run(_cmd_assign_role)

cli.subcommand("check-permission", "Check permission") \
    .add("--farmer-id", required=True) \
    .add("--resource", required=True) \
    .add("--action", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: check_permission(db, a.farmer_id, a.resource, a.action))

cli.subcommand("record-consent", "Record data sharing consent") \
    .add("--farmer-id", required=True) \
    .add("--data-type", required=True) \
    .add("--recipient-type", required=True) \
    .add("--recipient-id") \
    .add("--recipient-name") \
    .add("--purpose") \
    .add("--legal-basis", default="consent") \
    .add("--retention-days", type=int, default=365) \
    .add("--reciprocal", action="store_true") \
    .add("--no-consent", action="store_true") \
    .add("--data-scope") \
    .add("--json", action="store_true") \
    .run(_cmd_record_consent)

cli.subcommand("register-device", "Register device") \
    .add("--farmer-id", required=True) \
    .add("--device-id", required=True) \
    .add("--device-type", required=True) \
    .add("--location-id") \
    .add("--device-name") \
    .add("--os-type") \
    .add("--os-version") \
    .add("--app-version") \
    .add("--camera", action="store_true") \
    .add("--gps", action="store_true") \
    .add("--no-offline", action="store_true") \
    .add("--storage-mb", type=int) \
    .add("--json", action="store_true") \
    .run(_cmd_register_device)

cli.subcommand("access-matrix", "Get access matrix") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_access_matrix(db, a.location_id))

cli.subcommand("directory", "Get farmer directory") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_farmer_directory(db, a.location_id))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()
