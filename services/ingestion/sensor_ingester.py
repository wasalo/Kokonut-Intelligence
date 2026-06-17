#!/usr/bin/env python3
"""
Sensor Ingestion — Batch and HTTP API

Ingests sensor readings from CSV files or direct API calls.
Validates readings against sensor type ranges, writes to both
PostgreSQL and ClickHouse, and logs to ingestion_log.

Usage:
    # Batch CSV upload
    python -m services.ingestion.sensor_ingester --file data.csv

    # Single reading (API-style)
    python -m services.ingestion.sensor_ingester --sensor <uuid> --value 25.3

    # List registered sensors
    python -m services.ingestion.sensor_ingester --list
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone

import requests

from ..common.logging import get_logger
from .base import get_db, log_ingestion, hash_payload, retry
from .config import CH_HOST, CH_PORT, CH_USER, CH_PASSWORD

logger = get_logger("ingestion.sensor")

# Validation patterns for ClickHouse SQL interpolation
_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
_TS_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
_QUALITY_RE = re.compile(r'^(good|suspect|missing|estimated)$')
_SENSOR_TYPE_RE = re.compile(r'^[a-z_]+$')
_UNIT_RE = re.compile(r'^[a-zA-Z°%µ]+$')

# Sensor type range validation (fallback if sensor_type table not loaded)
SENSOR_TYPE_RANGES = {
    "soil_moisture": (0, 100),
    "soil_temperature": (-40, 80),
    "air_temperature": (-50, 60),
    "humidity": (0, 100),
    "light": (0, 200000),
    "rainfall": (0, 500),
    "water_level": (0, 10000),
}

CSV_COLUMNS = {
    "device_id",  # sensor_device.id or slug
    "reading_date",
    "reading_time",
    "value",
}


def _validate_ch_value(value: str, pattern: re.Pattern, name: str) -> str:
    """Validate a value against a regex pattern for ClickHouse SQL safety."""
    if not pattern.match(value):
        raise ValueError(f"Invalid {name} for ClickHouse insert: {value!r}")
    return value


def _ch_str(value: str) -> str:
    """Escape a string value for ClickHouse SQL single-quoted context."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def get_sensor_type_ranges(db) -> dict:
    """Load sensor type ranges from database."""
    ranges = dict(SENSOR_TYPE_RANGES)
    try:
        with db.cursor() as cur:
            cur.execute("SELECT name, min_value, max_value FROM sensor_type")
            for name, min_val, max_val in cur.fetchall():
                if min_val is not None and max_val is not None:
                    ranges[name] = (float(min_val), float(max_val))
    except Exception:
        pass
    return ranges


def validate_reading(value: float, sensor_type: str, ranges: dict) -> list:
    """Validate a sensor reading. Returns list of warnings."""
    warnings = []
    if sensor_type in ranges:
        min_val, max_val = ranges[sensor_type]
        if value < min_val:
            warnings.append(f"Below minimum ({min_val} {sensor_type}): {value}")
        if value > max_val:
            warnings.append(f"Above maximum ({max_val} {sensor_type}): {value}")
    if value != value:  # NaN check
        warnings.append("Value is NaN")
    return warnings


def get_active_sensors(db) -> list:
    """Get all active sensor devices with type info."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT sd.id, sd.name, sd.slug, sd.sensor_type_id, st.name as sensor_type,
                   sd.location_id, sd.plot_id, sd.status, sd.protocol
            FROM sensor_device sd
            JOIN sensor_type st ON sd.sensor_type_id = st.id
            WHERE sd.status = 'active'
        """)
        return cur.fetchall()


def get_sensor_by_id_or_slug(db, identifier: str):
    """Get a sensor by UUID or slug."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT sd.id, sd.name, sd.slug, sd.sensor_type_id, st.name as sensor_type,
                   sd.location_id, sd.plot_id, sd.status, sd.protocol
            FROM sensor_device sd
            JOIN sensor_type st ON sd.sensor_type_id = st.id
            WHERE sd.id::text = %s OR sd.slug = %s
        """, (identifier, identifier))
        return cur.fetchone()


def insert_reading(db, sensor_info: dict, reading_date: str, reading_time: str,
                   value: float, quality: str = "good", metadata: dict = None) -> str:
    """Insert a sensor reading into PostgreSQL. Returns record ID."""
    sensor_id, name, slug, sensor_type_id, sensor_type, location_id, plot_id, status, protocol = sensor_info

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sensor_reading
                (location_id, plot_id, sensor_id, sensor_type, reading_date,
                 reading_time, value, unit, quality, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    (SELECT unit FROM sensor_type WHERE id = %s),
                    %s, %s::jsonb)
            RETURNING id
            """,
            (
                location_id, plot_id, str(sensor_id), sensor_type,
                reading_date, reading_time, value, sensor_type_id,
                quality, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_reading_clickhouse(sensor_info: dict, reading_date: str, reading_time: str,
                               value: float, quality: str = "good") -> None:
    """Insert a sensor reading into ClickHouse sensor_readings table."""
    sensor_id, name, slug, sensor_type_id, sensor_type, location_id, plot_id, status, protocol = sensor_info

    # Build timestamp
    if reading_time:
        ts = f"{reading_date} {reading_time}"
    else:
        ts = f"{reading_date} 00:00:00"

    # Validate all interpolated values for SQL safety
    _validate_ch_value(ts, _TS_RE, "timestamp")
    _validate_ch_value(str(sensor_id), _UUID_RE, "sensor_id")
    _validate_ch_value(sensor_type, _SENSOR_TYPE_RE, "sensor_type")
    _validate_ch_value(str(location_id), _UUID_RE, "location_id")
    if plot_id:
        _validate_ch_value(str(plot_id), _UUID_RE, "plot_id")
    _validate_ch_value(quality, _QUALITY_RE, "quality")

    ch_url = f"http://{CH_HOST}:{CH_PORT}"

    # Use the sensor_type name as a readable unit label for ClickHouse
    unit = sensor_type
    if not _UNIT_RE.match(unit):
        unit = "unknown"

    query = f"""INSERT INTO sensor_readings
        (timestamp, sensor_id, sensor_type, location_id, plot_id,
         value, unit, quality, metadata)
        VALUES (
            '{ts}',
            '{sensor_id}',
            '{sensor_type}',
            '{location_id}',
            '{str(plot_id) if plot_id else ''}',
            {value},
            '{unit}',
            '{quality}',
            map()
        )"""

    try:
        resp = requests.post(
            ch_url,
            data=query.encode("utf-8"),
            auth=(CH_USER, CH_PASSWORD),
            headers={"Content-Type": "text/plain"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("ClickHouse insert failed: %s", e)


def run_csv(file_path: str):
    """Batch ingest sensor readings from CSV."""
    db = get_db()
    try:
        ranges = get_sensor_type_ranges(db)

        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        logger.info("Processing %d readings from %s...", len(rows), file_path)
        success = 0
        warnings = 0
        errors = 0

        for i, row in enumerate(rows):
            device_id = row.get("device_id", "").strip()
            reading_date = row.get("reading_date", "").strip()
            reading_time = row.get("reading_time", "").strip()
            value_str = row.get("value", "").strip()

            if not device_id or not reading_date or not value_str:
                errors += 1
                logger.warning("  ✗ Row %d: missing required fields (device_id, reading_date, value)", i + 1)
                continue

            try:
                value = float(value_str)
            except ValueError:
                errors += 1
                logger.warning("  ✗ Row %d: invalid value '%s'", i + 1, value_str)
                continue

            # Look up sensor
            sensor_info = get_sensor_by_id_or_slug(db, device_id)
            if not sensor_info:
                errors += 1
                logger.warning("  ✗ Row %d: sensor '%s' not found", i + 1, device_id)
                continue

            # Validate range
            sensor_type = sensor_info[4]
            range_warnings = validate_reading(value, sensor_type, ranges)
            quality = "good"
            if range_warnings:
                quality = "suspect"
                warnings += 1
                logger.warning("  ⚠ Row %d: %s", i + 1, ', '.join(range_warnings))

            try:
                pg_id = insert_reading(db, sensor_info, reading_date, reading_time, value, quality,
                                        {"csv_row": i + 1, "source_file": file_path})
                insert_reading_clickhouse(sensor_info, reading_date, reading_time, value, quality)

                log_ingestion(
                    source_system="csv_upload",
                    source_table="sensor_csv",
                    source_id=f"row_{i + 1}",
                    target_table="sensor_reading",
                    target_id=pg_id,
                    operation="insert",
                    payload_hash=hash_payload(row),
                    status="success",
                    rows_affected=1,
                )
                success += 1

            except Exception as e:
                errors += 1
                log_ingestion(
                    source_system="csv_upload",
                    source_table="sensor_csv",
                    source_id=f"row_{i + 1}",
                    target_table="sensor_reading",
                    target_id=None,
                    operation="insert",
                    payload_hash=hash_payload(row),
                    status="failed",
                    error_message=str(e),
                )
                logger.error("  ✗ Row %d: %s", i + 1, e)

        db.commit()
        logger.info("Done: %d success, %d warnings, %d errors", success, warnings, errors)
    finally:
        db.close()


def run_single(sensor_id: str, value: float, date_str: str = None, time_str: str = None):
    """Ingest a single sensor reading (API-style)."""
    db = get_db()
    try:
        ranges = get_sensor_type_ranges(db)

        sensor_info = get_sensor_by_id_or_slug(db, sensor_id)
        if not sensor_info:
            logger.error("Sensor '%s' not found", sensor_id)
            sys.exit(1)

        now = datetime.now(timezone.utc)
        reading_date = date_str or now.strftime("%Y-%m-%d")
        reading_time = time_str or now.strftime("%H:%M:%S")

        # Validate
        sensor_type = sensor_info[4]
        range_warnings = validate_reading(value, sensor_type, ranges)
        quality = "good"
        if range_warnings:
            quality = "suspect"
            for w in range_warnings:
                logger.warning("  ⚠ %s", w)

        pg_id = insert_reading(db, sensor_info, reading_date, reading_time, value, quality,
                                {"source": "api", "ingested_at": now.isoformat()})
        insert_reading_clickhouse(sensor_info, reading_date, reading_time, value, quality)

        log_ingestion(
            source_system="api",
            source_table="sensor_api",
            source_id=sensor_id,
            target_table="sensor_reading",
            target_id=pg_id,
            operation="insert",
            payload_hash=hash_payload({"sensor_id": sensor_id, "value": value}),
            status="success",
            rows_affected=1,
        )

        db.commit()

        name = sensor_info[1]
        logger.info("✓ %s: %.2f (%s) at %s %s", name, value, sensor_type, reading_date, reading_time)
    finally:
        db.close()


def list_sensors():
    """List all registered sensors."""
    db = get_db()
    sensors = get_active_sensors(db)
    db.close()

    if not sensors:
        logger.info("No active sensors found.")
        return

    logger.info("%d active sensors:", len(sensors))
    for sid, name, slug, stid, stype, loc_id, plot_id, status, protocol in sensors:
        logger.info("  %s | %s | %s | %s | %s", name, stype, str(loc_id)[:8], protocol or '—', sid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sensor data ingestion")
    parser.add_argument("--file", help="CSV file path for batch ingestion")
    parser.add_argument("--sensor", help="Sensor UUID or slug for single reading")
    parser.add_argument("--value", type=float, help="Sensor value (with --sensor)")
    parser.add_argument("--date", help="Reading date YYYY-MM-DD (with --sensor)")
    parser.add_argument("--time", help="Reading time HH:MM:SS (with --sensor)")
    parser.add_argument("--list", action="store_true", help="List active sensors")
    args = parser.parse_args()

    if args.list:
        list_sensors()
    elif args.file:
        run_csv(args.file)
    elif args.sensor and args.value is not None:
        run_single(args.sensor, args.value, args.date, args.time)
    else:
        parser.print_help()
