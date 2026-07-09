"""IoT device manager.

Handles device auto-registration, health monitoring, and status tracking.
Works with both MQTT and HTTP sensor ingestion paths.

Usage:
    python3 -m services.ingestion.device_manager --list
    python3 -m services.ingestion.device_manager --register --device-id sensor001 --sensor-type air_temperature --location-id UUID
    python3 -m services.ingestion.device_manager --health --device-id sensor001
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger
from .base import get_db

logger = get_logger("ingestion.device_manager")


def register_device(
    conn,
    device_id: str,
    sensor_type: str,
    location_id: str,
    name: str = None,
    protocol: str = "mqtt",
    manufacturer: str = None,
    model: str = None,
    serial_number: str = None,
    metadata: dict = None,
) -> str:
    """Register a new sensor device.

    Returns:
        Device UUID.
    """
    cur = conn.cursor()

    # Get sensor type ID
    cur.execute("SELECT id FROM sensor_type WHERE name = %s", (sensor_type,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown sensor type: {sensor_type}")
    sensor_type_id = str(row[0])

    cur.execute("""
        INSERT INTO sensor_device
            (name, slug, sensor_type_id, location_id, protocol, manufacturer, model, serial_number, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            sensor_type_id = EXCLUDED.sensor_type_id,
            location_id = EXCLUDED.location_id,
            protocol = EXCLUDED.protocol,
            manufacturer = EXCLUDED.manufacturer,
            model = EXCLUDED.model,
            serial_number = EXCLUDED.serial_number,
            status = 'active',
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
    """, (
        name or f"Sensor {device_id}",
        device_id,
        sensor_type_id,
        location_id,
        protocol,
        manufacturer,
        model,
        serial_number,
        json.dumps(metadata or {}),
    ))
    device_id_db = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    # Initialize device health
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sensor_device_health (device_id, last_seen_at, status)
        VALUES (%s, NOW(), 'unknown')
        ON CONFLICT (device_id) DO NOTHING
    """, (device_id_db,))
    conn.commit()
    cur.close()

    logger.info("Registered device: %s (id=%s, type=%s)", device_id, device_id_db[:8], sensor_type)
    return device_id_db


def list_devices(conn, location_id: str = None, status: str = None) -> List[Dict[str, Any]]:
    """List registered sensor devices."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT
            sd.id, sd.name, sd.slug, sd.status, sd.protocol,
            st.name AS sensor_type, sd.manufacturer, sd.model,
            sd.serial_number, sd.calibration_date, sd.calibration_interval_days,
            sd.latitude, sd.longitude,
            sdh.last_seen_at, sdh.battery_pct, sdh.status AS health_status,
            CASE
                WHEN sdh.last_seen_at IS NULL THEN 'never_seen'
                WHEN sdh.last_seen_at >= NOW() - INTERVAL '1 hour' THEN 'online'
                WHEN sdh.last_seen_at >= NOW() - INTERVAL '24 hours' THEN 'stale'
                ELSE 'offline'
            END AS connectivity
        FROM sensor_device sd
        JOIN sensor_type st ON st.id = sd.sensor_type_id
        LEFT JOIN sensor_device_health sdh ON sdh.device_id = sd.id
        WHERE 1=1
    """
    params = []
    if location_id:
        query += " AND sd.location_id = %s"
        params.append(location_id)
    if status:
        query += " AND sd.status = %s"
        params.append(status)
    query += " ORDER BY sd.name"

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def get_device_health(conn, device_id: str) -> Optional[Dict[str, Any]]:
    """Get device health status."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            sd.name, sd.slug, sd.status, st.name AS sensor_type,
            sdh.last_seen_at, sdh.battery_pct, sdh.signal_strength_dbm,
            sdh.firmware_version, sdh.reading_rate_per_hour, sdh.status AS health_status,
            CASE
                WHEN sdh.last_seen_at IS NULL THEN 'never_seen'
                WHEN sdh.last_seen_at >= NOW() - INTERVAL '1 hour' THEN 'online'
                WHEN sdh.last_seen_at >= NOW() - INTERVAL '24 hours' THEN 'stale'
                ELSE 'offline'
            END AS connectivity
        FROM sensor_device sd
        JOIN sensor_type st ON st.id = sd.sensor_type_id
        LEFT JOIN sensor_device_health sdh ON sdh.device_id = sd.id
        WHERE sd.slug = %s
    """, (device_id,))
    row = cur.fetchone()
    cur.close()
    return dict(row) if row else None


def update_health(
    conn,
    device_id: str,
    battery_pct: float = None,
    signal_strength_dbm: float = None,
    firmware_version: str = None,
    reading_rate: float = None,
) -> None:
    """Update device health metrics."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sensor_device_health (device_id, last_seen_at, battery_pct, signal_strength_dbm, firmware_version, reading_rate_per_hour, status)
        VALUES (%s, NOW(), %s, %s, %s, %s, 'online')
        ON CONFLICT (device_id) DO UPDATE SET
            last_seen_at = NOW(),
            battery_pct = COALESCE(EXCLUDED.battery_pct, sensor_device_health.battery_pct),
            signal_strength_dbm = COALESCE(EXCLUDED.signal_strength_dbm, sensor_device_health.signal_strength_dbm),
            firmware_version = COALESCE(EXCLUDED.firmware_version, sensor_device_health.firmware_version),
            reading_rate_per_hour = COALESCE(EXCLUDED.reading_rate_per_hour, sensor_device_health.reading_rate_per_hour),
            status = 'online',
            updated_at = NOW()
    """, (device_id, battery_pct, signal_strength_dbm, firmware_version, reading_rate))
    conn.commit()
    cur.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IoT device manager")
    parser.add_argument("--list", action="store_true", help="List all devices")
    parser.add_argument("--register", action="store_true", help="Register a new device")
    parser.add_argument("--health", action="store_true", help="Get device health")
    parser.add_argument("--device-id", help="Device slug/ID")
    parser.add_argument("--sensor-type", help="Sensor type name")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--name", help="Device name")
    parser.add_argument("--protocol", default="mqtt", choices=["mqtt", "http", "csv", "manual"])
    args = parser.parse_args()

    conn = get_db()
    try:
        if args.list:
            devices = list_devices(conn, location_id=args.location_id)
            print(json.dumps(devices, indent=2, default=str))
        elif args.register:
            if not all([args.device_id, args.sensor_type, args.location_id]):
                parser.error("--register requires --device-id, --sensor-type, --location-id")
            device_id = register_device(conn, args.device_id, args.sensor_type, args.location_id, args.name, args.protocol)
            print(json.dumps({"device_id": device_id, "status": "registered"}))
        elif args.health:
            if not args.device_id:
                parser.error("--health requires --device-id")
            health = get_device_health(conn, args.device_id)
            print(json.dumps(health, indent=2, default=str))
        else:
            parser.print_help()
    finally:
        conn.close()
