"""HTTP API for the offline-first Kokonut Field Collector."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from services.common.database import get_db

try:
    from fastapi import APIRouter, Header, HTTPException
    from fastapi.responses import FileResponse
except ImportError:  # pragma: no cover - gateway requires FastAPI at runtime
    APIRouter = None
    Header = None
    HTTPException = RuntimeError
    FileResponse = None


APP_PATH = Path(__file__).with_name("field-collector.html")
router = APIRouter(prefix="/mobile", tags=["mobile"]) if APIRouter else None


class RegisterRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    device_name: str | None = Field(default=None, max_length=300)
    device_type: str = Field(default="phone", max_length=100)
    os: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=50)
    app_version: str | None = Field(default="1.0.0", max_length=50)
    user_id: str | None = Field(default=None, max_length=200)
    location_id: UUID | None = None


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


@router.get("/forms")
async def list_forms(location_id: str | None = None):
    """Return active form definitions safe to cache on a device."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT form_id, name, description, form_schema, ui_schema,
                   version, collection_type, min_app_version
            FROM mobile_form
            WHERE status = 'active'
              AND (location_id IS NULL OR location_id::text = %s)
            ORDER BY name
            """,
            (location_id,),
        )
        columns = [item[0] for item in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
    finally:
        conn.close()
    return {"forms": rows}


@router.post("/register")
async def register_device(request: RegisterRequest):
    """Register a browser/device and issue an opaque token."""
    token = secrets.token_urlsafe(32)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mobile_device
                (device_id, device_name, device_type, os, os_version,
                 app_version, user_id, location_id, device_token_hash,
                 has_camera, has_gps, has_offline, status, last_seen_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULLIF(%s, '')::uuid, %s,
                    TRUE, TRUE, TRUE, 'active', NOW())
            ON CONFLICT (device_id) DO UPDATE SET
                device_name = EXCLUDED.device_name,
                device_type = EXCLUDED.device_type,
                os = EXCLUDED.os,
                os_version = EXCLUDED.os_version,
                app_version = EXCLUDED.app_version,
                user_id = EXCLUDED.user_id,
                location_id = EXCLUDED.location_id,
                device_token_hash = EXCLUDED.device_token_hash,
                status = 'active',
                last_seen_at = NOW(),
                updated_at = NOW()
            """,
            (
                request.device_id,
                request.device_name,
                request.device_type,
                request.os,
                request.os_version,
                request.app_version,
                request.user_id,
                str(request.location_id) if request.location_id else None,
                _token_hash(token),
            ),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return {"device_id": request.device_id, "device_token": token, "status": "registered"}


@router.post("/sync")
async def sync_collections(request: SyncRequest, x_device_token: str | None = Header(default=None)):
    """Idempotently enqueue a batch of offline collections."""
    device_id, user_id, registered_location_id = _device_for_token(x_device_token)
    if request.device_id != device_id:
        raise HTTPException(status_code=403, detail="Device token does not match device_id")

    accepted_client_ids: list[str] = []
    duplicate_client_ids: list[str] = []
    conn = get_db()
    try:
        cur = conn.cursor()
        for item in request.collections:
            if len(json.dumps(item.payload, separators=(",", ":"))) > 8_000_000:
                raise HTTPException(status_code=413, detail="Collection payload is too large")
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
                    json.dumps(item.photo_refs),
                    item.latitude,
                    item.longitude,
                    item.accuracy_m,
                    collected_at,
                    item.client_id,
                ),
            )
            if cur.fetchone():
                accepted_client_ids.append(item.client_id)
            else:
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
