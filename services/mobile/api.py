"""HTTP API for the offline-first Kokonut Field Collector."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from services.common.database import get_db
from services.common.tenant_context import (
    TenantContextDenied,
    set_gateway_tenant_context,
    set_mobile_device_tenant_context,
    set_operator_tenant_context,
)
from services.mobile.form_validation import FormPayloadInvalid, FormSchemaUnavailable, validate_form_payload

try:
    from fastapi import APIRouter, Header, HTTPException, Request  # type: ignore[reportAssignmentType]
    from fastapi.responses import FileResponse, JSONResponse
except ImportError:  # pragma: no cover - gateway requires FastAPI at runtime
    APIRouter = None
    def Header(default=None, **kwargs):
        return default

    class HTTPException(RuntimeError):
        def __init__(self, status_code=500, detail=None):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail or f"HTTP {status_code}")

    Request = None
    FileResponse = None
    JSONResponse = None


APP_PATH = Path(__file__).with_name("field-collector.html")
VAULT_SCRIPT_PATH = Path(__file__).with_name("field-collector-vault.js")
SERVICE_WORKER_PATH = Path(__file__).with_name("field-collector-service-worker.js")
router = APIRouter(prefix="/mobile", tags=["mobile"]) if APIRouter else None
logger = logging.getLogger(__name__)
DEVICE_REENROLLMENT_REQUIRED_DETAIL = (
    "Field Collector device must be re-enrolled by the current verified location owner"
)


class RegisterRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    enrollment_code: str = Field(min_length=32, max_length=128)
    device_name: str | None = Field(default=None, max_length=300)
    device_type: str = Field(default="phone", max_length=100)
    os: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=50)
    app_version: str | None = Field(default="1.0.0", max_length=50)


class EnrollmentCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    expires_in_minutes: int = Field(default=60, ge=1, le=1440)


class CollectionRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=200)
    collection_type: str = Field(min_length=1, max_length=100)
    form_id: str | None = Field(default=None, max_length=200)
    form_version: str | None = Field(default=None, max_length=50)
    participant_ref: str | None = Field(default=None, min_length=32, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    photo_refs: list[str] = Field(default_factory=list, max_length=5)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100000)
    collected_at: datetime | None = None


class SyncRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    collections: list[CollectionRequest] = Field(min_length=1, max_length=50)


class ParticipantLinkCreateRequest(BaseModel):
    party_id: UUID
    evidence: dict[str, Any] = Field(default_factory=dict)


class ParticipantLinkRevokeRequest(BaseModel):
    participant_ref: str = Field(min_length=32, max_length=128)


def _set_participant_operator_context(conn, request: Request, location_id: str, action: str) -> None:
    """Bind OIDC participant administration to its validated tenant grant."""
    session = getattr(request.state, "operator_session", None)
    operator = getattr(session, "operator", None)
    operator_id = getattr(operator, "operator_id", None)
    if operator_id is not None:
        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="mobile_participant",
            action=action,
        )


def _set_gateway_mobile_device_context(conn, request: Request, location_id: str, action: str):
    """Bind a Gateway-authenticated mobile-device mutation to its owner tenant."""
    authorization = getattr(request.state, "gateway_authorization", None)
    try:
        expected_location = str(UUID(str(location_id)))
        authorized_location = str(UUID(str(authorization.get("location_id"))))
    except (AttributeError, TypeError, ValueError):
        raise TenantContextDenied("verified Gateway route authorization is required") from None
    if (
        not isinstance(authorization, dict)
        or authorization.get("resource") != "mobile_device"
        or authorization.get("action") != action
        or authorized_location != expected_location
    ):
        raise TenantContextDenied("verified Gateway route authorization is required")
    try:
        return set_gateway_tenant_context(
            conn,
            gateway_caller=getattr(request.state, "caller", None),
            location_id=expected_location,
            resource="mobile_device",
            action=action,
        )
    except ValueError as exc:
        raise TenantContextDenied("verified Gateway identity is invalid") from exc


def _set_mobile_mutation_timeouts(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL lock_timeout = '2s'")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verified_location_tenant(cur, location_id: str) -> str:
    """Lock and return the current verified owner for one location."""
    cur.execute(
        """
        SELECT owner.organization_id::text
          FROM location AS loc
          JOIN location_tenant_owner_verification AS owner
            ON owner.location_id = loc.id
           AND owner.organization_id = loc.organization_id
           AND owner.revoked_at IS NULL
          JOIN organization AS tenant
            ON tenant.id = owner.organization_id
           AND tenant.status = 'active'
         WHERE loc.id = %s::uuid
           AND loc.status = 'active'
         FOR SHARE OF loc, owner, tenant
        """,
        (location_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=403,
            detail="A verified active owner is required for Field Collector enrollment",
        )
    return str(row[0])


def _device_reenrollment_error() -> HTTPException:
    return HTTPException(status_code=403, detail=DEVICE_REENROLLMENT_REQUIRED_DETAIL)


def _consent_decision_at(cur, *, party_id, policy: dict, location_id: str, at: datetime):
    """Return the latest exact policy decision effective by ``at``."""
    scope_id = location_id if policy["consent_scope_type"] == "location" else policy["consent_scope_id"]
    cur.execute(
        """
        SELECT id::text, event_type, expires_at
          FROM stakeholder_consent
         WHERE party_id = %s
           AND data_category = %s
           AND purpose = %s
           AND scope_type = %s
           AND scope_id IS NOT DISTINCT FROM %s::uuid
           AND recipient_party_id IS NOT DISTINCT FROM %s::uuid
           AND recipient_type = %s
           AND consent_version = %s
           AND effective_at <= %s
         ORDER BY effective_at DESC, created_at DESC, id DESC
         LIMIT 1
        """,
        (
            party_id,
            policy["consent_data_category"],
            policy["consent_purpose"],
            policy["consent_scope_type"],
            scope_id,
            policy["consent_recipient_party_id"],
            policy["consent_recipient_type"],
            policy["consent_version"],
            at,
        ),
    )
    return cur.fetchone()


def _validate_required_consent(cur, *, party_id, policy: dict, location_id: str, collected_at: datetime):
    """Require an exact grant at collection and a still-current grant at sync."""
    now = datetime.now(timezone.utc)
    at_collection = _consent_decision_at(
        cur, party_id=party_id, policy=policy, location_id=location_id, at=collected_at
    )
    current = _consent_decision_at(
        cur, party_id=party_id, policy=policy, location_id=location_id, at=now
    )
    if (
        not at_collection
        or at_collection[1] != "grant"
        or (at_collection[2] is not None and _normalise_datetime(at_collection[2]) <= collected_at)
    ):
        raise HTTPException(status_code=403, detail="No matching consent grant was effective when the record was collected")
    if at_collection[2] is not None and _normalise_datetime(at_collection[2]) <= now:
        raise HTTPException(status_code=403, detail="The collection-time consent grant expired before sync")
    if (
        not current
        or current[1] != "grant"
        or (current[2] is not None and _normalise_datetime(current[2]) <= now)
    ):
        raise HTTPException(status_code=403, detail="Matching consent is not active at sync time")

    scope_id = location_id if policy["consent_scope_type"] == "location" else policy["consent_scope_id"]
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM stakeholder_consent
             WHERE party_id = %s
               AND data_category = %s
               AND purpose = %s
               AND scope_type = %s
               AND scope_id IS NOT DISTINCT FROM %s::uuid
               AND recipient_party_id IS NOT DISTINCT FROM %s::uuid
               AND recipient_type = %s
               AND consent_version = %s
               AND event_type IN ('withdraw', 'deny', 'expire')
               AND effective_at > %s
               AND effective_at <= %s
        )
        """,
        (
            party_id,
            policy["consent_data_category"],
            policy["consent_purpose"],
            policy["consent_scope_type"],
            scope_id,
            policy["consent_recipient_party_id"],
            policy["consent_recipient_type"],
            policy["consent_version"],
            collected_at,
            now,
        ),
    )
    if cur.fetchone()[0]:
        raise HTTPException(status_code=403, detail="Consent was withdrawn or denied after collection")
    return at_collection[0], current[0], now


def _participant_link_for_ref(cur, participant_ref: str, location_id: str):
    cur.execute(
        """
        SELECT id::text, party_id::text, revoked_at
          FROM mobile_participant_link
         WHERE participant_ref_hash = %s AND location_id = %s::uuid
         FOR SHARE
        """,
        (_token_hash(participant_ref), location_id),
    )
    return cur.fetchone()


def _form_revision_for_sync(cur, item: CollectionRequest, location_id: str) -> dict:
    if not item.form_id or not item.form_version:
        raise HTTPException(status_code=422, detail="New collections require a known form ID and version")
    cur.execute(
        """
        SELECT id::text, form_id, version, collection_type, location_id::text,
               status, consent_policy_status, consent_data_category, consent_purpose,
               consent_scope_type, consent_scope_id::text, consent_recipient_type,
               consent_recipient_party_id::text, consent_version, created_at, form_schema
          FROM mobile_form_version
         WHERE form_id = %s AND version = %s
         FOR SHARE
        """,
        (item.form_id, item.form_version),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=422, detail="Unknown form revision")
    revision = {
        "id": row[0],
        "form_id": row[1],
        "version": row[2],
        "collection_type": row[3],
        "location_id": row[4],
        "status": row[5],
        "consent_policy_status": row[6],
        "consent_data_category": row[7],
        "consent_purpose": row[8],
        "consent_scope_type": row[9],
        "consent_scope_id": row[10],
        "consent_recipient_type": row[11],
        "consent_recipient_party_id": row[12],
        "consent_version": row[13],
        "created_at": _normalise_datetime(row[14]),
        "form_schema": row[15],
    }
    if revision["collection_type"] != item.collection_type:
        raise HTTPException(status_code=422, detail="Collection type does not match the form revision")
    if revision["location_id"] and revision["location_id"] != location_id:
        raise HTTPException(status_code=403, detail="Form revision is assigned to another location")
    return revision


def _validate_media_upload_policy(
    cur,
    *,
    collection_client_id: str,
    collection_type: str,
    form_id: str,
    form_version: str,
    participant_ref: str | None,
    location_id: str,
    collected_at: datetime,
) -> None:
    """Check form and required consent before accepting private image bytes."""
    item = CollectionRequest(
        client_id=collection_client_id,
        collection_type=collection_type,
        form_id=form_id,
        form_version=form_version,
        participant_ref=participant_ref,
        collected_at=collected_at,
    )
    revision = _form_revision_for_sync(cur, item, location_id)
    collected = _normalise_datetime(collected_at)
    if collected < revision["created_at"]:
        raise HTTPException(status_code=422, detail="Collection predates the referenced form revision")
    if revision["status"] not in {"active", "retired"}:
        raise HTTPException(status_code=409, detail="Form revision is no longer accepted")

    link = _participant_link_for_ref(cur, participant_ref, location_id) if participant_ref else None
    if participant_ref and not link:
        raise HTTPException(status_code=403, detail="Participant reference is not assigned to this location")
    if revision["consent_policy_status"] in {"unclassified", "not_required"} and participant_ref:
        raise HTTPException(status_code=422, detail="This form revision does not accept a participant reference")
    # A known retired revision is review-only, but it is still subject to the
    # consent policy that governed collection. Do not let staleness bypass a
    # required participant link or a withdrawal that happened before upload.
    if revision["consent_policy_status"] == "required":
        if not participant_ref:
            raise HTTPException(status_code=422, detail="This form revision requires a participant reference")
        if link[2] is not None:
            raise HTTPException(status_code=403, detail="Participant reference has been revoked")
        _validate_required_consent(
            cur,
            party_id=link[1],
            policy=revision,
            location_id=location_id,
            collected_at=collected,
        )


def _normalise_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _device_for_token(token: str | None) -> tuple[str, str | None, str | None]:
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Device token required")
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT device_id, user_id, location_id, owner_binding_current
              FROM kokonut_security.resolve_mobile_device_token(%s)
            """,
            (_token_hash(token),),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid device token")
    if not row[3]:
        raise _device_reenrollment_error()
    return row[0], row[1], row[2]


@router.get("/app")
async def mobile_app():
    """Serve the app from the gateway's API namespace."""
    return FileResponse(APP_PATH, media_type="text/html")


@router.get("/field-collector-vault.js")
async def mobile_vault_script():
    """Serve the local encryption helper used by the companion page."""
    return FileResponse(VAULT_SCRIPT_PATH, media_type="application/javascript")


@router.get("/field-collector-service-worker.js")
async def mobile_service_worker():
    """Serve the offline shell worker from the mobile API namespace."""
    return FileResponse(SERVICE_WORKER_PATH, media_type="application/javascript")


def get_media_store():
    """Return the explicitly configured private media storage adapter."""
    from services.mobile.media_storage import create_media_store

    return create_media_store()


@router.post("/media/uploads", status_code=201)
async def upload_private_media(
    request: Request,
    x_device_token: str | None = Header(default=None),
    x_collection_client_id: str = Header(default="", min_length=1, max_length=200),  # type: ignore[reportArgumentType]
    x_collection_type: str | None = Header(default=None, min_length=1, max_length=100),
    x_form_id: str | None = Header(default=None, min_length=1, max_length=200),
    x_form_version: str | None = Header(default=None, min_length=1, max_length=50),
    x_participant_ref: str | None = Header(default=None, min_length=32, max_length=128),
    x_collected_at: datetime | None = Header(default=None),
):
    """Store a size-limited JPEG under a random, device-scoped private key."""
    from services.mobile.media_storage import MAX_MEDIA_BYTES, MediaStorageNotConfigured

    device_id, user_id, location_id = _device_for_token(x_device_token)
    if not location_id:
        raise HTTPException(status_code=403, detail="Device is not assigned to a location")
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "image/jpeg":
        raise HTTPException(status_code=415, detail="Only JPEG images are accepted")
    policy_conn = get_db()
    policy_cur = None
    try:
        if not location_id:
            raise TenantContextDenied("device has no assigned location")
        set_mobile_device_tenant_context(
            policy_conn,
            device_id=device_id,
            location_id=location_id,
            device_token_hash=_token_hash(x_device_token),
        )
        policy_cur = policy_conn.cursor()
        _validate_media_upload_policy(
            policy_cur,
            collection_client_id=x_collection_client_id,
            collection_type=x_collection_type or "",
            form_id=x_form_id or "",
            form_version=x_form_version or "",
            participant_ref=x_participant_ref,
            location_id=location_id,
            collected_at=_normalise_datetime(x_collected_at),
        )
        policy_conn.commit()
    except HTTPException:
        policy_conn.rollback()
        raise
    except TenantContextDenied as exc:
        policy_conn.rollback()
        raise _device_reenrollment_error() from exc
    finally:
        if policy_cur is not None:
            policy_cur.close()
        policy_conn.close()
    body = await request.body()
    if len(body) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 2 MB upload limit")
    if len(body) < 3 or not body.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="Uploaded content is not a JPEG image")

    try:
        store = get_media_store()
    except MediaStorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Private media storage is not configured") from exc

    media_id = uuid4()
    device_scope = hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:20]
    object_key = f"private/field-collector/{location_id}/{device_scope}/{media_id.hex}.jpg"
    content_sha256 = hashlib.sha256(body).hexdigest()
    try:
        store.put_private(object_key, body, content_type)
    except Exception as exc:
        logger.error("Private media object write failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Private media storage is unavailable") from exc

    conn = None
    cur = None
    commit_started = False
    try:
        conn = get_db()
        set_mobile_device_tenant_context(
            conn,
            device_id=device_id,
            location_id=location_id,
            device_token_hash=_token_hash(x_device_token),
        )
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mobile_media_upload
                (media_id, device_id, user_id, collection_client_id, location_id, object_key,
                 content_type, size_bytes, content_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(media_id),
                device_id,
                user_id,
                x_collection_client_id,
                location_id,
                object_key,
                content_type,
                len(body),
                content_sha256,
            ),
        )
        commit_started = True
        conn.commit()
    except Exception as exc:
        rollback_succeeded = conn is None
        if conn is not None and not commit_started:
            try:
                conn.rollback()
                rollback_succeeded = True
            except Exception as rollback_exc:
                logger.error("Private media rollback failed (%s)", type(rollback_exc).__name__)
        if rollback_succeeded:
            try:
                store.delete_private(object_key)
            except Exception as cleanup_exc:
                logger.error("Private media cleanup failed (%s)", type(cleanup_exc).__name__)
        elif commit_started:
            logger.error("Private media cleanup deferred because commit outcome is uncertain")
        if isinstance(exc, TenantContextDenied):
            raise _device_reenrollment_error() from exc
        logger.error("Private media metadata write failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Could not register private media") from exc
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception as close_exc:
                logger.error("Private media cursor close failed (%s)", type(close_exc).__name__)
        if conn is not None:
            try:
                conn.close()
            except Exception as close_exc:
                logger.error("Private media connection close failed (%s)", type(close_exc).__name__)

    return {"media_id": str(media_id), "content_type": content_type, "size_bytes": len(body)}


@router.get("/forms")
async def list_forms(
    location_id: str | None = None,
    x_device_token: str | None = Header(default=None),
):
    """Return approved global forms or forms scoped to the authenticated device."""
    registered_device_id = None
    registered_location_id = None
    if x_device_token:
        registered_device_id, _, registered_location_id = _device_for_token(x_device_token)
        if location_id:
            try:
                requested_location_id = str(UUID(location_id))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid location identifier") from exc
            if requested_location_id != registered_location_id:
                raise HTTPException(status_code=403, detail="Location does not match device")
    elif location_id:
        raise HTTPException(status_code=401, detail="Device token required for location forms")

    conn = get_db()
    try:
        if x_device_token:
            if not registered_location_id:
                raise HTTPException(status_code=403, detail=DEVICE_REENROLLMENT_REQUIRED_DETAIL)
            set_mobile_device_tenant_context(
                conn,
                device_id=registered_device_id,
                location_id=registered_location_id,
                device_token_hash=_token_hash(x_device_token),
            )
        cur = conn.cursor()
        if x_device_token:
            cur.execute(
                """
                SELECT form_id, name, description, form_schema, ui_schema,
                       version, collection_type, min_app_version,
                       consent_policy_status, consent_data_category,
                       consent_purpose, consent_version, consent_recipient_type,
                       consent_recipient_name,
                       (consent_policy_status = 'required') AS participant_required
                FROM mobile_form_version
                WHERE status = 'active'
                  AND (location_id IS NULL OR location_id::text = %s)
                ORDER BY name
                """,
                (registered_location_id,),
            )
        else:
            cur.execute(
                """
                SELECT form_id, name, description, form_schema, ui_schema,
                       version, collection_type, min_app_version,
                       consent_policy_status, consent_data_category,
                       consent_purpose, consent_version, consent_recipient_type,
                       consent_recipient_name,
                       (consent_policy_status = 'required') AS participant_required
                FROM mobile_form_version
                WHERE status = 'active'
                  AND location_id IS NULL
                  AND is_public IS TRUE
                ORDER BY name
                """
            )
        columns = [item[0] for item in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
        conn.commit()
    except TenantContextDenied as exc:
        conn.rollback()
        raise _device_reenrollment_error() from exc
    finally:
        conn.close()
    return {"forms": rows}


@router.post("/locations/{location_id}/participants", status_code=201)
async def create_participant_link(
    location_id: UUID,
    request: Request,
    body: ParticipantLinkCreateRequest,
):
    """Create a reviewer-approved, location-scoped opaque participant reference."""
    if not body.evidence:
        raise HTTPException(status_code=422, detail="Reviewer evidence is required")
    evidence_bytes = json.dumps(body.evidence, separators=(",", ":")).encode("utf-8")
    if len(evidence_bytes) > 16_384:
        raise HTTPException(status_code=413, detail="Participant link evidence is too large")
    participant_ref = secrets.token_urlsafe(32)
    conn = get_db()
    try:
        cur = conn.cursor()
        _set_participant_operator_context(conn, request, str(location_id), "create")
        cur.execute("SELECT 1 FROM party WHERE id = %s", (str(body.party_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Participant party was not found")
        cur.execute(
            """
            INSERT INTO mobile_participant_link
                (participant_ref_hash, party_id, location_id, created_by, evidence)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id::text, created_at
            """,
            (
                _token_hash(participant_ref),
                str(body.party_id),
                str(location_id),
                request.state.caller,
                json.dumps(body.evidence),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    except HTTPException:
        conn.rollback()
        raise
    except TenantContextDenied as exc:
        conn.rollback()
        raise HTTPException(
            status_code=403,
            detail="Tenant-qualified operator access is required",
        ) from exc
    except Exception as exc:
        conn.rollback()
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="An active participant link already exists for this location") from exc
        logger.warning("Participant link creation failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Participant link could not be created") from exc
    finally:
        conn.close()
    return JSONResponse(
        status_code=201,
        content={
            "link_id": row[0],
            "location_id": str(location_id),
            "participant_ref": participant_ref,
            "created_at": row[1].isoformat() if hasattr(row[1], "isoformat") else row[1],
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post("/locations/{location_id}/participants/revoke")
async def revoke_participant_link(
    location_id: UUID,
    request: Request,
    body: ParticipantLinkRevokeRequest,
):
    """Revoke a participant reference without deleting its identity history."""
    conn = get_db()
    try:
        cur = conn.cursor()
        _set_participant_operator_context(conn, request, str(location_id), "revoke")
        cur.execute(
            """
            UPDATE mobile_participant_link
               SET revoked_by = %s, revoked_at = NOW()
             WHERE participant_ref_hash = %s
               AND location_id = %s
               AND revoked_at IS NULL
            RETURNING id::text, revoked_at
            """,
            (request.state.caller, _token_hash(body.participant_ref), str(location_id)),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Active participant link was not found")
        conn.commit()
        cur.close()
    except HTTPException:
        conn.rollback()
        raise
    except TenantContextDenied as exc:
        conn.rollback()
        raise HTTPException(
            status_code=403,
            detail="Tenant-qualified operator access is required",
        ) from exc
    finally:
        conn.close()
    return JSONResponse(
        content={
            "link_id": row[0],
            "location_id": str(location_id),
            "status": "revoked",
            "revoked_at": row[1].isoformat() if hasattr(row[1], "isoformat") else row[1],
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post("/locations/{location_id}/enrollments", status_code=201)
async def create_enrollment(
    location_id: UUID,
    request: Request,
    body: EnrollmentCreateRequest,
):
    """Issue a short-lived, single-use device enrollment code."""
    return await _create_enrollment(
        location_id,
        request,
        body,
        operator_id=None,
    )


async def create_operator_enrollment(
    location_id: UUID,
    request: Request,
    body: EnrollmentCreateRequest,
    *,
    operator_id: str,
):
    """Issue an enrollment code in a tenant-qualified OIDC operator transaction."""
    return await _create_enrollment(
        location_id,
        request,
        body,
        operator_id=operator_id,
    )


async def _create_enrollment(
    location_id: UUID,
    request: Request,
    body: EnrollmentCreateRequest,
    *,
    operator_id: str | None,
):
    code = secrets.token_urlsafe(32)
    conn = get_db()
    try:
        operator_context = None
        gateway_context = None
        _set_mobile_mutation_timeouts(conn)
        if operator_id is not None:
            operator_context = set_operator_tenant_context(
                conn,
                operator_id=operator_id,
                location_id=str(location_id),
                resource="mobile_device",
                action="enroll",
            )
        else:
            gateway_context = _set_gateway_mobile_device_context(
                conn, request, str(location_id), "enroll"
            )
        if gateway_context is not None:
            tenant_id = gateway_context.tenant_id
        else:
            cur = conn.cursor()
            tenant_id = _verified_location_tenant(cur, str(location_id))
        if operator_context is not None and operator_context.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Operator grant does not match the current verified location owner",
            )
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mobile_device_enrollment
                (code_hash, user_id, location_id, tenant_organization_id, created_by, expires_at)
            VALUES (%s, %s, %s, %s::uuid, %s, NOW() + (%s * INTERVAL '1 minute'))
            RETURNING id::text, expires_at
            """,
            (
                _token_hash(code),
                body.user_id,
                str(location_id),
                tenant_id,
                request.state.caller,
                body.expires_in_minutes,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Enrollment could not be created")
        conn.commit()
        cur.close()
    except HTTPException:
        conn.rollback()
        raise
    except TenantContextDenied as exc:
        conn.rollback()
        raise HTTPException(
            status_code=403,
            detail="Tenant-qualified access is required for enrollment",
        ) from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    expires_at = row[1].isoformat() if hasattr(row[1], "isoformat") else row[1]
    return {
        "enrollment_id": row[0],
        "enrollment_code": code,
        "expires_at": expires_at,
    }


@router.post("/register")
async def register_device(request: RegisterRequest):
    """Consume a one-time enrollment code and issue an opaque device token."""
    token = secrets.token_urlsafe(32)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT result, registered_location_id::text
              FROM kokonut_security.redeem_mobile_enrollment(
                  %s, %s, %s, %s, %s, %s, %s, %s
              )
            """,
            (
                _token_hash(request.enrollment_code),
                request.device_id,
                request.device_name,
                request.device_type,
                request.os,
                request.os_version,
                request.app_version,
                _token_hash(token),
            ),
        )
        registration = cur.fetchone()
        if not registration:
            raise HTTPException(status_code=401, detail="Invalid or expired enrollment code")
        result, location_id = registration
        if result == "invalid":
            raise HTTPException(status_code=401, detail="Invalid or expired enrollment code")
        if result == "owner_changed":
            raise HTTPException(status_code=403, detail=DEVICE_REENROLLMENT_REQUIRED_DETAIL)
        if result == "device_conflict":
            raise HTTPException(status_code=409, detail="Device is already registered")
        if result != "registered" or location_id is None:
            raise HTTPException(status_code=500, detail="Enrollment redemption failed")
        conn.commit()
        cur.close()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "device_id": request.device_id,
        "location_id": location_id,
        "device_token": token,
        "status": "registered",
    }


@router.delete("/locations/{location_id}/enrollments/{enrollment_id}")
async def revoke_enrollment(location_id: UUID, enrollment_id: UUID, request: Request):
    """Revoke an unused enrollment code within its location."""
    return await _revoke_enrollment(
        location_id,
        enrollment_id,
        operator_id=None,
        request=request,
    )


async def revoke_operator_enrollment(
    location_id: UUID,
    enrollment_id: UUID,
    *,
    operator_id: str,
):
    """Revoke an enrollment in a tenant-qualified OIDC operator transaction."""
    return await _revoke_enrollment(
        location_id,
        enrollment_id,
        operator_id=operator_id,
        request=None,
    )


async def _revoke_enrollment(
    location_id: UUID,
    enrollment_id: UUID,
    *,
    operator_id: str | None,
    request: Request | None,
):
    conn = get_db()
    try:
        _set_mobile_mutation_timeouts(conn)
        if operator_id is not None:
            set_operator_tenant_context(
                conn,
                operator_id=operator_id,
                location_id=str(location_id),
                resource="mobile_device",
                action="revoke",
            )
        elif request is not None:
            _set_gateway_mobile_device_context(conn, request, str(location_id), "revoke")
        else:
            raise TenantContextDenied("verified Gateway route authorization is required")
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE mobile_device_enrollment
            SET revoked_at = NOW()
            WHERE id = %s AND location_id = %s
              AND used_at IS NULL AND revoked_at IS NULL
            RETURNING id::text
            """,
            (str(enrollment_id), str(location_id)),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Active enrollment not found")
        conn.commit()
        cur.close()
    except HTTPException:
        conn.rollback()
        raise
    except TenantContextDenied as exc:
        conn.rollback()
        if operator_id is not None:
            raise
        raise HTTPException(
            status_code=403,
            detail="Tenant-qualified access is required to revoke enrollment",
        ) from exc
    finally:
        conn.close()
    return {"enrollment_id": row[0], "status": "revoked"}


@router.post("/locations/{location_id}/devices/{device_id}/revoke")
async def revoke_device(location_id: UUID, device_id: str, request: Request):
    """Revoke one active device token, scoped to the authorized location."""
    return await _revoke_device(
        location_id,
        device_id,
        operator_id=None,
        request=request,
    )


async def revoke_operator_device(
    location_id: UUID,
    device_id: str,
    *,
    operator_id: str,
):
    """Revoke a device in a tenant-qualified OIDC operator transaction."""
    return await _revoke_device(
        location_id, device_id, operator_id=operator_id, request=None
    )


async def _revoke_device(
    location_id: UUID,
    device_id: str,
    *,
    operator_id: str | None,
    request: Request | None,
):
    conn = get_db()
    try:
        _set_mobile_mutation_timeouts(conn)
        if operator_id is not None:
            set_operator_tenant_context(
                conn,
                operator_id=operator_id,
                location_id=str(location_id),
                resource="mobile_device",
                action="revoke",
            )
        elif request is not None:
            _set_gateway_mobile_device_context(conn, request, str(location_id), "revoke")
        else:
            raise TenantContextDenied("verified Gateway route authorization is required")
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE mobile_device
            SET status = 'revoked', device_token_hash = NULL,
                revoked_at = NOW(), updated_at = NOW()
            WHERE device_id = %s AND location_id = %s AND status = 'active'
            RETURNING device_id
            """,
            (device_id, str(location_id)),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Active device not found")
        conn.commit()
        cur.close()
    except HTTPException:
        conn.rollback()
        raise
    except TenantContextDenied as exc:
        conn.rollback()
        if operator_id is not None:
            raise
        raise HTTPException(
            status_code=403,
            detail="Tenant-qualified access is required to revoke device",
        ) from exc
    finally:
        conn.close()
    return {"device_id": row[0], "status": "revoked"}


def _same_sync_record(
    existing, device_id, user_id, location_id, item, photo_refs,
    form_revision_id, participant_link_id,
) -> bool:
    """Match an idempotency key only when its full caller-controlled record matches."""
    if not existing or len(existing) < 14:
        return False
    existing_location_id = str(existing[2]) if existing[2] is not None else None
    if (
        existing[0] != device_id
        or existing[1] != user_id
        or existing_location_id != location_id
        or existing[3] != item.collection_type
        or existing[4] != item.form_id
        or existing[5] != item.form_version
        or existing[6] != item.payload
        or list(existing[7] or []) != list(photo_refs or [])
        or existing[8] != item.latitude
        or existing[9] != item.longitude
        or existing[10] != item.accuracy_m
    ):
        return False
    if item.collected_at is not None:
        if existing[11] is None:
            return False
        if _normalise_datetime(existing[11]) != _normalise_datetime(item.collected_at):
            return False
    if existing[12] is None:
        # Preserve idempotent acknowledgement for pre-migration rows without
        # retroactively assigning a revision or participant identity.
        return existing[13] is None and participant_link_id is None and item.participant_ref is None
    return (
        str(existing[12]) == str(form_revision_id)
        and (str(existing[13]) if existing[13] is not None else None)
        == (str(participant_link_id) if participant_link_id is not None else None)
    )


@router.post("/sync")
async def sync_collections(request: SyncRequest, x_device_token: str | None = Header(default=None)):
    """Idempotently enqueue a batch of offline collections and attach private media."""
    from uuid import UUID

    from services.mobile.media_storage import MediaStorageNotConfigured

    device_id, user_id, registered_location_id = _device_for_token(x_device_token)
    if request.device_id != device_id:
        raise HTTPException(status_code=403, detail="Device token does not match device_id")
    # Inline image data must never cross the API boundary into PostgreSQL JSONB.
    for item in request.collections:
        if "photos" in item.payload:
            raise HTTPException(status_code=422, detail="Upload images first and send their media references")

    accepted_client_ids: list[str] = []
    duplicate_client_ids: list[str] = []
    conn = get_db()
    try:
        if not registered_location_id:
            raise TenantContextDenied("device has no assigned location")
        set_mobile_device_tenant_context(
            conn,
            device_id=device_id,
            location_id=registered_location_id,
            device_token_hash=_token_hash(x_device_token),
        )
        cur = conn.cursor()
        for item in request.collections:
            if len(json.dumps(item.payload, separators=(",", ":"))) > 256_000:
                raise HTTPException(status_code=413, detail="Collection payload is too large")
            try:
                media_ids = [UUID(ref) for ref in item.photo_refs]
            except (ValueError, TypeError, AttributeError) as exc:
                raise HTTPException(status_code=422, detail="photo_refs must contain uploaded media IDs") from exc
            if len(set(media_ids)) != len(media_ids):
                raise HTTPException(status_code=422, detail="photo_refs cannot contain duplicates")
            photo_refs = [str(media_id) for media_id in media_ids]
            if not registered_location_id:
                raise HTTPException(status_code=403, detail="Device has no server-assigned location")

            # A byte-for-byte retry of a pre-migration row can be acknowledged
            # without assigning it a new validation status or identity link.
            cur.execute(
                """
                SELECT device_id, user_id, location_id::text, collection_type, form_id,
                       form_version, payload, photo_refs, latitude, longitude, accuracy_m,
                       collected_at, form_revision_id::text, participant_link_id::text
                  FROM offline_collection WHERE client_id = %s FOR UPDATE
                """,
                (item.client_id,),
            )
            legacy_existing = cur.fetchone()
            if legacy_existing and legacy_existing[12] is None:
                if not _same_sync_record(
                    legacy_existing, device_id, user_id, registered_location_id,
                    item, photo_refs, None, None,
                ):
                    raise HTTPException(status_code=409, detail="Client ID already belongs to another record")
                duplicate_client_ids.append(item.client_id)
                continue

            revision = _form_revision_for_sync(cur, item, registered_location_id)
            form_revision_id = revision["id"]
            try:
                validate_form_payload(revision["form_schema"], item.payload)
            except FormSchemaUnavailable as exc:
                logger.error("Invalid stored form schema for revision %s", revision["id"])
                raise HTTPException(status_code=503, detail="Form schema is unavailable") from exc
            except FormPayloadInvalid as exc:
                raise HTTPException(
                    status_code=422,
                    detail="Collection payload does not match the selected form revision",
                ) from exc
            collected_at = _normalise_datetime(item.collected_at)
            if collected_at < revision["created_at"]:
                raise HTTPException(status_code=422, detail="Collection predates the referenced form revision")
            link = None
            if item.participant_ref:
                link = _participant_link_for_ref(cur, item.participant_ref, registered_location_id)
                if not link:
                    raise HTTPException(status_code=403, detail="Participant reference is not assigned to this location")

            active_revision = revision["status"] == "active"
            policy_status = revision["consent_policy_status"]
            if policy_status in {"unclassified", "not_required"} and item.participant_ref:
                raise HTTPException(status_code=422, detail="This form revision does not accept a participant reference")
            if policy_status == "required" and not item.participant_ref:
                raise HTTPException(status_code=422, detail="This form revision requires a participant reference")

            # Retired revisions are accepted only into the private review queue.
            # They never inherit an active consent result during sync.
            participant_link_id = link[0] if (link and (active_revision or policy_status == "required")) else None
            consent_status = "unassessed"
            consent_event_id_at_collection = None
            consent_event_id_at_sync = None
            consent_validated_at = None
            if active_revision and policy_status == "not_required":
                consent_status = "not_required"
            form_validation_status = "active" if active_revision else "retired_review"
            form_review_required = (
                not active_revision or policy_status == "unclassified"
            )

            # Check idempotency before requiring media to remain in the uploaded state.
            cur.execute(
                """
                SELECT device_id, user_id, location_id::text, collection_type, form_id,
                       form_version, payload, photo_refs, latitude, longitude, accuracy_m,
                       collected_at, form_revision_id::text, participant_link_id::text
                FROM offline_collection WHERE client_id = %s FOR UPDATE
                """,
                (item.client_id,),
            )
            existing = cur.fetchone()
            if existing:
                if not _same_sync_record(
                    existing, device_id, user_id, registered_location_id, item, photo_refs,
                    form_revision_id, participant_link_id,
                ):
                    raise HTTPException(status_code=409, detail="Client ID already belongs to another record")
                duplicate_client_ids.append(item.client_id)
                continue

            if revision["status"] not in {"active", "retired"}:
                raise HTTPException(status_code=409, detail="Form revision is no longer accepted")

            if policy_status == "required":
                if link[2] is not None:
                    raise HTTPException(status_code=403, detail="Participant reference has been revoked")
                consent_event_id_at_collection, consent_event_id_at_sync, consent_validated_at = _validate_required_consent(
                    cur,
                    party_id=link[1],
                    policy=revision,
                    location_id=registered_location_id,
                    collected_at=collected_at,
                )
                if active_revision:
                    consent_status = "granted"

            media_rows = []
            if media_ids:
                if not registered_location_id:
                    raise HTTPException(status_code=403, detail="Device has no server-assigned location")
                cur.execute(
                    """
                    SELECT media_id::text, object_key, content_type, size_bytes
                    FROM mobile_media_upload
                    WHERE media_id = ANY(%s::uuid[]) AND device_id = %s
                      AND collection_client_id = %s AND location_id = %s::uuid
                      AND status = 'uploaded' AND expires_at > NOW()
                    FOR UPDATE
                    """,
                    (photo_refs, device_id, item.client_id, registered_location_id),
                )
                media_rows = cur.fetchall()
                if len(media_rows) != len(media_ids):
                    # A concurrent retry may have committed after the first idempotency read.
                    cur.execute(
                        """
                        SELECT device_id, user_id, location_id::text, collection_type, form_id,
                               form_version, payload, photo_refs, latitude, longitude, accuracy_m,
                               collected_at, form_revision_id::text, participant_link_id::text
                        FROM offline_collection WHERE client_id = %s
                        """,
                        (item.client_id,),
                    )
                    existing = cur.fetchone()
                    if existing and _same_sync_record(
                        existing, device_id, user_id, registered_location_id, item, photo_refs,
                        form_revision_id, participant_link_id,
                    ):
                        duplicate_client_ids.append(item.client_id)
                        continue
                    raise HTTPException(status_code=403, detail="One or more media references are not available to this device")
                try:
                    store = get_media_store()
                except MediaStorageNotConfigured as exc:
                    raise HTTPException(status_code=503, detail="Private media storage is not configured") from exc
                for media_row in media_rows:
                    try:
                        head = store.head_private(media_row[1])
                    except Exception as exc:
                        logger.error("Private media verification failed (%s)", type(exc).__name__)
                        raise HTTPException(status_code=502, detail="Private media could not be verified") from exc
                    if head.get("ContentLength") != media_row[3] or head.get("ContentType") != media_row[2]:
                        raise HTTPException(status_code=409, detail="Private media does not match its upload record")

            location_id = registered_location_id
            cur.execute(
                """
                INSERT INTO offline_collection
                    (device_id, user_id, location_id, collection_type,
                     form_id, form_version, payload, photo_refs, latitude,
                     longitude, accuracy_m, collected_at, client_id, sync_status,
                     form_revision_id, participant_link_id,
                     consent_event_id_at_collection, consent_event_id_at_sync,
                     form_validation_status, consent_validation_status,
                     form_review_required, consent_validated_at)
                VALUES (%s, %s, NULLIF(%s, '')::uuid, %s, %s, %s, %s::jsonb,
                        %s::jsonb, %s, %s, %s, %s, %s, 'pending',
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                        %s, %s, %s, %s)
                ON CONFLICT (client_id) WHERE client_id IS NOT NULL DO NOTHING
                RETURNING id
                """,
                (
                    device_id,
                    user_id,
                    location_id,
                    item.collection_type,
                    item.form_id,
                    item.form_version,
                    json.dumps(item.payload),
                    json.dumps(photo_refs),
                    item.latitude,
                    item.longitude,
                    item.accuracy_m,
                    collected_at,
                    item.client_id,
                    form_revision_id,
                    participant_link_id,
                    consent_event_id_at_collection,
                    consent_event_id_at_sync,
                    form_validation_status,
                    consent_status,
                    form_review_required,
                    consent_validated_at,
                ),
            )
            inserted = cur.fetchone()
            if inserted:
                if media_ids:
                    cur.execute(
                        """
                        UPDATE mobile_media_upload
                        SET status = 'attached', attached_collection_id = %s
                        WHERE media_id = ANY(%s::uuid[]) AND device_id = %s
                          AND collection_client_id = %s AND location_id = %s::uuid
                          AND status = 'uploaded' AND expires_at > NOW()
                        """,
                        (inserted[0], photo_refs, device_id, item.client_id, registered_location_id),
                    )
                    if cur.rowcount != len(media_ids):
                        raise HTTPException(status_code=409, detail="Media could not be attached to the collection")
                accepted_client_ids.append(item.client_id)
            else:
                cur.execute(
                    """
                    SELECT device_id, user_id, location_id::text, collection_type, form_id,
                           form_version, payload, photo_refs, latitude, longitude, accuracy_m,
                           collected_at, form_revision_id::text, participant_link_id::text
                    FROM offline_collection WHERE client_id = %s
                    """,
                    (item.client_id,),
                )
                existing = cur.fetchone()
                if not existing or not _same_sync_record(
                    existing, device_id, user_id, registered_location_id, item, photo_refs,
                    form_revision_id, participant_link_id,
                ):
                    raise HTTPException(status_code=409, detail="Client ID already belongs to another record")
                duplicate_client_ids.append(item.client_id)

        cur.execute(
            "UPDATE mobile_device SET last_seen_at = NOW(), updated_at = NOW() WHERE device_id = %s",
            (device_id,),
        )
        cur.execute(
            """
            INSERT INTO sync_log
                (device_id, sync_action, direction, status, records_synced)
            VALUES (%s, 'upload', 'push', 'success', %s)
            """,
            (device_id, len(accepted_client_ids)),
        )
        conn.commit()
        cur.close()
    except TenantContextDenied as exc:
        conn.rollback()
        raise _device_reenrollment_error() from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "device_id": device_id,
        "accepted": len(accepted_client_ids),
        "accepted_client_ids": accepted_client_ids,
        "duplicates": len(duplicate_client_ids),
        "duplicate_client_ids": duplicate_client_ids,
    }


@router.get("/sync/status")
async def sync_status(x_device_token: str | None = Header(default=None)):
    """Return pending and error counts for the authenticated device."""
    device_id, _, location_id = _device_for_token(x_device_token)
    conn = get_db()
    try:
        if not location_id:
            raise TenantContextDenied("device has no assigned location")
        set_mobile_device_tenant_context(
            conn,
            device_id=device_id,
            location_id=location_id,
            device_token_hash=_token_hash(x_device_token),
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE sync_status = 'pending'),
                COUNT(*) FILTER (WHERE sync_status = 'error'),
                COUNT(*) FILTER (WHERE sync_status = 'conflict')
            FROM offline_collection
            WHERE device_id = %s
            """,
            (device_id,),
        )
        pending, errors, conflicts = cur.fetchone()
        cur.execute("SELECT last_sync_at FROM mobile_device WHERE device_id = %s", (device_id,))
        last_sync = cur.fetchone()[0]
        cur.close()
        conn.commit()
    except TenantContextDenied as exc:
        conn.rollback()
        raise _device_reenrollment_error() from exc
    finally:
        conn.close()
    return {
        "device_id": device_id,
        "pending": pending,
        "errors": errors,
        "conflicts": conflicts,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
    }
