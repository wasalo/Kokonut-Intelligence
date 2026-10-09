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

try:
    from fastapi import APIRouter, Header, HTTPException, Request  # type: ignore[reportAssignmentType]
    from fastapi.responses import FileResponse
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


APP_PATH = Path(__file__).with_name("field-collector.html")
VAULT_SCRIPT_PATH = Path(__file__).with_name("field-collector-vault.js")
router = APIRouter(prefix="/mobile", tags=["mobile"]) if APIRouter else None
logger = logging.getLogger(__name__)


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
    payload: dict[str, Any] = Field(default_factory=dict)
    photo_refs: list[str] = Field(default_factory=list, max_length=5)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100000)
    collected_at: datetime | None = None


class SyncRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    collections: list[CollectionRequest] = Field(min_length=1, max_length=50)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
            SELECT device_id, user_id, location_id::text
            FROM mobile_device
            WHERE device_token_hash = %s AND status = 'active'
            """,
            (_token_hash(token),),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid device token")
    return row[0], row[1], row[2]


@router.get("/app")
async def mobile_app():
    """Serve the app from the gateway's API namespace."""
    return FileResponse(APP_PATH, media_type="text/html")


@router.get("/field-collector-vault.js")
async def mobile_vault_script():
    """Serve the local encryption helper used by the companion page."""
    return FileResponse(VAULT_SCRIPT_PATH, media_type="application/javascript")


def get_media_store():
    """Return the configured private S3-compatible object-store adapter."""
    from services.mobile.media_storage import create_media_store

    return create_media_store()


@router.post("/media/uploads", status_code=201)
async def upload_private_media(
    request: Request,
    x_device_token: str | None = Header(default=None),
    x_collection_client_id: str = Header(default="", min_length=1, max_length=200),  # type: ignore[reportArgumentType]
):
    """Store a size-limited JPEG under a random, device-scoped private key."""
    from services.mobile.media_storage import MAX_MEDIA_BYTES, MediaStorageNotConfigured

    device_id, user_id, location_id = _device_for_token(x_device_token)
    if not location_id:
        raise HTTPException(status_code=403, detail="Device is not assigned to a location")
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "image/jpeg":
        raise HTTPException(status_code=415, detail="Only JPEG images are accepted")
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
    registered_location_id = None
    if x_device_token:
        _, _, registered_location_id = _device_for_token(x_device_token)
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
        cur = conn.cursor()
        if x_device_token:
            cur.execute(
                """
                SELECT form_id, name, description, form_schema, ui_schema,
                       version, collection_type, min_app_version
                FROM mobile_form
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
                       version, collection_type, min_app_version
                FROM mobile_form
                WHERE status = 'active'
                  AND location_id IS NULL
                  AND is_public IS TRUE
                ORDER BY name
                """
            )
        columns = [item[0] for item in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
    finally:
        conn.close()
    return {"forms": rows}


@router.post("/locations/{location_id}/enrollments", status_code=201)
async def create_enrollment(
    location_id: UUID,
    request: Request,
    body: EnrollmentCreateRequest,
):
    """Issue a short-lived, single-use device enrollment code."""
    code = secrets.token_urlsafe(32)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mobile_device_enrollment
                (code_hash, user_id, location_id, created_by, expires_at)
            VALUES (%s, %s, %s, %s, NOW() + (%s * INTERVAL '1 minute'))
            RETURNING id::text, expires_at
            """,
            (
                _token_hash(code),
                body.user_id,
                str(location_id),
                request.state.caller,
                body.expires_in_minutes,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Enrollment could not be created")
        conn.commit()
        cur.close()
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
            SELECT id::text, user_id, location_id::text
            FROM mobile_device_enrollment
            WHERE code_hash = %s
              AND used_at IS NULL
              AND revoked_at IS NULL
              AND expires_at > NOW()
            FOR UPDATE
            """,
            (_token_hash(request.enrollment_code),),
        )
        enrollment = cur.fetchone()
        if not enrollment:
            raise HTTPException(status_code=401, detail="Invalid or expired enrollment code")

        enrollment_id, user_id, location_id = enrollment
        cur.execute(
            """
            INSERT INTO mobile_device
                (device_id, device_name, device_type, os, os_version,
                 app_version, user_id, location_id, device_token_hash,
                 has_camera, has_gps, has_offline, status, last_seen_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::uuid, %s,
                    TRUE, TRUE, TRUE, 'active', NOW())
            ON CONFLICT (device_id) DO NOTHING
            RETURNING device_id
            """,
            (
                request.device_id,
                request.device_name,
                request.device_type,
                request.os,
                request.os_version,
                request.app_version,
                user_id,
                location_id,
                _token_hash(token),
            ),
        )
        registered = cur.fetchone()
        if not registered:
            raise HTTPException(status_code=409, detail="Device is already registered")
        cur.execute(
            """
            UPDATE mobile_device_enrollment
            SET used_at = NOW(), consumed_device_id = %s
            WHERE id = %s AND used_at IS NULL
            """,
            (request.device_id, enrollment_id),
        )
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
async def revoke_enrollment(location_id: UUID, enrollment_id: UUID):
    """Revoke an unused enrollment code within its location."""
    conn = get_db()
    try:
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
    finally:
        conn.close()
    return {"enrollment_id": row[0], "status": "revoked"}


@router.post("/locations/{location_id}/devices/{device_id}/revoke")
async def revoke_device(location_id: UUID, device_id: str):
    """Revoke one active device token, scoped to the authorized location."""
    conn = get_db()
    try:
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
    finally:
        conn.close()
    return {"device_id": row[0], "status": "revoked"}


def _same_sync_record(existing, device_id, user_id, location_id, item, photo_refs) -> bool:
    """Match an idempotency key only when its full caller-controlled record matches."""
    if not existing or len(existing) < 12:
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
        return _normalise_datetime(existing[11]) == _normalise_datetime(item.collected_at)
    return True


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

            # Check idempotency before requiring media to remain in the uploaded state.
            cur.execute(
                """
                SELECT device_id, user_id, location_id::text, collection_type, form_id,
                       form_version, payload, photo_refs, latitude, longitude, accuracy_m,
                       collected_at
                FROM offline_collection WHERE client_id = %s FOR UPDATE
                """,
                (item.client_id,),
            )
            existing = cur.fetchone()
            if existing:
                if not _same_sync_record(existing, device_id, user_id, registered_location_id, item, photo_refs):
                    raise HTTPException(status_code=409, detail="Client ID already belongs to another record")
                duplicate_client_ids.append(item.client_id)
                continue

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
                               collected_at
                        FROM offline_collection WHERE client_id = %s
                        """,
                        (item.client_id,),
                    )
                    existing = cur.fetchone()
                    if existing and _same_sync_record(existing, device_id, user_id, registered_location_id, item, photo_refs):
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

            collected_at = _normalise_datetime(item.collected_at)
            location_id = registered_location_id
            cur.execute(
                """
                INSERT INTO offline_collection
                    (device_id, user_id, location_id, collection_type,
                     form_id, form_version, payload, photo_refs, latitude,
                     longitude, accuracy_m, collected_at, client_id, sync_status)
                VALUES (%s, %s, NULLIF(%s, '')::uuid, %s, %s, %s, %s::jsonb,
                        %s::jsonb, %s, %s, %s, %s, %s, 'pending')
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
                           collected_at
                    FROM offline_collection WHERE client_id = %s
                    """,
                    (item.client_id,),
                )
                existing = cur.fetchone()
                if not existing or not _same_sync_record(existing, device_id, user_id, registered_location_id, item, photo_refs):
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
    device_id, _, _ = _device_for_token(x_device_token)
    conn = get_db()
    try:
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
    finally:
        conn.close()
    return {
        "device_id": device_id,
        "pending": pending,
        "errors": errors,
        "conflicts": conflicts,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
    }
