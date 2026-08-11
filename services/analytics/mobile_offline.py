#!/usr/bin/env python3
"""
Mobile / Offline Data Collection

Device registration, offline queue management, sync coordination,
and conflict resolution for field workers.

Usage:
    python -m services.analytics.mobile_offline register --device-id sensor-phone-001 --name "Field Phone 1"
    python -m services.analytics.mobile_offline queue --device-id sensor-phone-001 --type soil_reading --location-id UUID
    python -m services.analytics.mobile_offline sync --device-id sensor-phone-001
    python -m services.analytics.mobile_offline status
    python -m services.analytics.mobile_offline devices
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.mobile_offline")


# ============================================================
# Device Management
# ============================================================

def register_device(
    conn,
    device_id: str,
    device_name: str = None,
    device_type: str = "phone",
    os: str = None,
    os_version: str = None,
    app_version: str = None,
    user_id: str = None,
    location_id: str = None,
    push_token: str = None,
    has_camera: bool = True,
    has_gps: bool = True,
    has_offline: bool = True,
) -> dict:
    """Register or update a mobile device."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mobile_device
            (id, device_id, device_name, device_type, os, os_version,
             app_version, user_id, location_id, push_token,
             has_camera, has_gps, has_offline, status, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', NOW())
        ON CONFLICT (device_id) DO UPDATE SET
            device_name = COALESCE(EXCLUDED.device_name, mobile_device.device_name),
            os = COALESCE(EXCLUDED.os, mobile_device.os),
            os_version = COALESCE(EXCLUDED.os_version, mobile_device.os_version),
            app_version = COALESCE(EXCLUDED.app_version, mobile_device.app_version),
            push_token = COALESCE(EXCLUDED.push_token, mobile_device.push_token),
            last_seen_at = NOW(),
            updated_at = NOW()
        RETURNING id
        """,
        (
            str(uuid.uuid4()), device_id, device_name, device_type,
            os, os_version, app_version, user_id, location_id,
            push_token, has_camera, has_gps, has_offline,
        ),
    )
    conn.commit()
    cur.close()

    return {"device_id": device_id, "status": "registered"}


def list_devices(conn, user_id: str = None, location_id: str = None) -> list:
    """List registered devices."""
    cur = conn.cursor()
    where = "1=1"
    params = []
    if user_id:
        where += " AND user_id = %s"
        params.append(user_id)
    if location_id:
        where += " AND location_id = %s"
        params.append(location_id)

    cur.execute(
        f"""
        SELECT device_id, device_name, device_type, user_id, status,
               last_sync_at, last_seen_at, app_version,
               (SELECT COUNT(*) FROM offline_collection oc
                WHERE oc.device_id = mobile_device.device_id
                  AND oc.sync_status = 'pending') AS pending_count
        FROM mobile_device
        WHERE {where}
        ORDER BY last_seen_at DESC NULLS LAST
        """,
        tuple(params),
    )
    cols = [d[0] for d in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return results


# ============================================================
# Offline Queue
# ============================================================

def queue_collection(
    conn,
    device_id: str,
    collection_type: str,
    payload: dict,
    user_id: str = None,
    location_id: str = None,
    latitude: float = None,
    longitude: float = None,
    accuracy_m: float = None,
    photo_refs: list = None,
    form_id: str = None,
    form_version: str = None,
    client_id: str = None,
) -> dict:
    """Queue an offline collection for sync."""
    cur = conn.cursor()
    col_id = str(uuid.uuid4())

    # Check for duplicate client_id
    if client_id:
        cur.execute(
            "SELECT id FROM offline_collection WHERE client_id = %s",
            (client_id,),
        )
        if cur.fetchone():
            cur.close()
            return {"error": "Duplicate collection", "client_id": client_id, "sync_status": "duplicate"}

    cur.execute(
        """
        INSERT INTO offline_collection
            (id, device_id, user_id, location_id, collection_type,
             form_id, form_version, payload, photo_refs,
             latitude, longitude, accuracy_m, client_id, sync_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, 'pending')
        RETURNING id
        """,
        (
            col_id, device_id, user_id, location_id, collection_type,
            form_id, form_version, json.dumps(payload),
            json.dumps(photo_refs or []),
            latitude, longitude, accuracy_m, client_id,
        ),
    )
    conn.commit()
    cur.close()

    return {"collection_id": col_id, "sync_status": "pending", "device_id": device_id}


def get_pending_collections(conn, device_id: str = None, limit: int = 100) -> list:
    """Get pending collections for sync."""
    cur = conn.cursor()
    if device_id:
        cur.execute(
            """
            SELECT id, device_id, collection_type, payload, latitude, longitude,
                   collected_at, client_id, server_version, conflict_flag
            FROM offline_collection
            WHERE sync_status = 'pending' AND device_id = %s
            ORDER BY collected_at ASC
            LIMIT %s
            """,
            (device_id, limit),
        )
    else:
        cur.execute(
            """
            SELECT id, device_id, collection_type, payload, latitude, longitude,
                   collected_at, client_id, server_version, conflict_flag
            FROM offline_collection
            WHERE sync_status = 'pending'
            ORDER BY collected_at ASC
            LIMIT %s
            """,
            (limit,),
        )
    cols = [d[0] for d in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return results


# ============================================================
# Sync
# ============================================================

def sync_collections(conn, device_id: str) -> dict:
    """Process pending collections from a device (server-side sync)."""
    cur = conn.cursor()
    start_time = datetime.now(timezone.utc)

    # Get pending
    cur.execute(
        """
        SELECT id, collection_type, payload, client_id, server_version, collected_at
        FROM offline_collection
        WHERE device_id = %s AND sync_status = 'pending'
        ORDER BY collected_at ASC
        LIMIT 50
        """,
        (device_id,),
    )
    cols = [d[0] for d in cur.description]
    pending = [dict(zip(cols, row)) for row in cur.fetchall()]

    synced = 0
    conflicts = 0
    errors = 0

    for item in pending:
        try:
            # Conflict check: if client_id exists, verify version
            if item["client_id"]:
                cur.execute(
                    "SELECT server_version FROM offline_collection WHERE client_id = %s",
                    (item["client_id"],),
                )
                existing = cur.fetchone()
                if existing and existing[0] > item["server_version"]:
                    # Conflict detected
                    cur.execute(
                        "UPDATE offline_collection SET conflict_flag = TRUE, sync_status = 'conflict' WHERE id = %s",
                        (item["id"],),
                    )
                    conflicts += 1
                    continue

            # Mark as synced
            cur.execute(
                """
                UPDATE offline_collection
                SET sync_status = 'synced', synced_at = NOW(),
                    server_version = server_version + 1, updated_at = NOW()
                WHERE id = %s
                """,
                (item["id"],),
            )
            synced += 1

        except Exception as e:
            logger.error(f"Sync error for {item['id']}: {e}")
            cur.execute(
                "UPDATE offline_collection SET sync_status = 'error', sync_error = %s WHERE id = %s",
                (str(e), item["id"]),
            )
            errors += 1

    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    # Log sync event
    cur.execute(
        """
        INSERT INTO sync_log (id, device_id, sync_action, direction, status,
                              records_synced, conflict_count, duration_ms)
        VALUES (%s, %s, 'batch_sync', 'push', %s, %s, %s, %s)
        """,
        (
            str(uuid.uuid4()), device_id,
            'success' if errors == 0 else 'partial',
            synced, conflicts, duration_ms,
        ),
    )

    # Update device last_sync_at
    cur.execute(
        "UPDATE mobile_device SET last_sync_at = NOW() WHERE device_id = %s",
        (device_id,),
    )
    conn.commit()
    cur.close()

    return {
        "device_id": device_id,
        "synced": synced,
        "conflicts": conflicts,
        "errors": errors,
        "duration_ms": duration_ms,
        "status": "completed",
    }


def resolve_conflict(
    conn,
    collection_id: str,
    resolution: str = "keep_server",
    resolved_by: str = None,
) -> dict:
    """Resolve a sync conflict."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, sync_status, conflict_flag FROM offline_collection WHERE id = %s",
        (collection_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "Collection not found"}
    if not row[2]:
        cur.close()
        return {"error": "No conflict on this collection"}

    new_status = "synced" if resolution == "keep_server" else "synced"
    cur.execute(
        """
        UPDATE offline_collection
        SET sync_status = %s, conflict_flag = FALSE, resolved_by = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (new_status, resolved_by, collection_id),
    )
    conn.commit()
    cur.close()
    return {"collection_id": collection_id, "resolution": resolution, "status": "resolved"}


# ============================================================
# Status / Stats
# ============================================================

def get_sync_status(conn) -> dict:
    """Get overall sync status."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT sync_status, COUNT(*)
        FROM offline_collection
        GROUP BY sync_status
        """
    )
    status_counts = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT COUNT(*) FROM mobile_device WHERE status = 'active'
        """
    )
    active_devices = cur.fetchone()[0]

    cur.execute(
        """
        SELECT AVG(duration_ms) FROM sync_log
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        """
    )
    avg_sync_time = cur.fetchone()[0]
    cur.close()

    return {
        "total_collections": sum(status_counts.values()),
        "by_status": status_counts,
        "active_devices": active_devices,
        "avg_sync_time_ms": round(avg_sync_time, 1) if avg_sync_time else 0,
    }


# ============================================================
# CLI
# ============================================================

cli = CommandLine("mobile_offline", "Mobile/offline data collection")


def _render(result, args, human):
    print(json.dumps(result, indent=2, default=str) if args.json else human(result))


def _format_status(r: dict) -> str:
    lines = [
        f"Sync Status ({r['active_devices']} active devices)",
        f"  Total collections: {r['total_collections']}",
    ]
    for status, count in r["by_status"].items():
        lines.append(f"  {status}: {count}")
    lines.append(f"  Avg sync time: {r['avg_sync_time_ms']:.0f}ms")
    return "\n".join(lines)


def _format_devices(results: list) -> str:
    if not results:
        return "No devices registered."
    lines = [f"Devices ({len(results)}):"]
    for d in results:
        lines.append(f"  {d['device_id']:30s} {d['device_type']:10s} pending={d.get('pending_count', 0)}")
    return "\n".join(lines)


def _cmd_register(db, a):
    return register_device(
        db, a.device_id, a.name, a.type,
        user_id=a.user, location_id=a.location_id,
    )


def _cmd_queue(db, a):
    payload = json.loads(a.payload)
    return queue_collection(
        db, a.device_id, a.type, payload,
        location_id=a.location_id,
        latitude=a.latitude, longitude=a.longitude,
    )


cli.subcommand("register", "Register device") \
    .add("--device-id", required=True) \
    .add("--name") \
    .add("--type", default="phone") \
    .add("--user") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(_cmd_register) \
    .render_with(lambda r, a: _render(r, a, lambda x: f"Device {x['device_id']}: {x['status']}"))

cli.subcommand("queue", "Queue collection") \
    .add("--device-id", required=True) \
    .add("--type", required=True, help="Collection type") \
    .add("--location-id") \
    .add("--payload", default="{}", help="JSON payload") \
    .add("--latitude", type=float) \
    .add("--longitude", type=float) \
    .add("--json", action="store_true") \
    .run(_cmd_queue) \
    .render_with(lambda r, a: _render(r, a, lambda x: f"Queued: {x.get('collection_id', 'N/A')[:8]}... ({x['sync_status']})"))

cli.subcommand("sync", "Sync pending collections") \
    .add("--device-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: sync_collections(db, a.device_id)) \
    .render_with(lambda r, a: _render(r, a, lambda x: f"Synced {x['synced']}, conflicts={x['conflicts']}, errors={x['errors']} ({x['duration_ms']}ms)"))

cli.subcommand("status", "Sync status") \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_sync_status(db)) \
    .render_with(lambda r, a: _render(r, a, _format_status))

cli.subcommand("devices", "List devices") \
    .add("--user") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(lambda db, a: list_devices(db, a.user, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_devices))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()
