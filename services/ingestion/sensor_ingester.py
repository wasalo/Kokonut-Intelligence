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
from datetime import datetime, timezone

from ..common.logging import get_logger
from .base import get_db, hash_payload, insert_clickhouse_rows, log_ingestion
from .clickhouse_outbox import enqueue
from .field_validation import parse_reading_timestamp, validate_sensor_reading

# Lazy event bus — initialized on first publish to avoid import-time side effects
_event_bus = None


def _get_event_bus(conn=None):
    global _event_bus
    if _event_bus is None:
        from services.events.bus import EventBus
        _event_bus = EventBus(conn=conn)
    return _event_bus

logger = get_logger("ingestion.sensor")

# Validation patterns
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


def _validate_ch_value(value: str, pattern, name: str) -> str:
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
    result = validate_sensor_reading(value, sensor_type, unit="sensor", ranges=ranges)
    if not result.normalized.get("value") == result.normalized.get("value"):
        return ["Value is NaN"]
    warnings = []
    if sensor_type in ranges:
        min_val, max_val = ranges[sensor_type]
        if value < min_val:
            warnings.append(f"Below minimum ({min_val} {sensor_type}): {value}")
        if value > max_val:
            warnings.append(f"Above maximum ({max_val} {sensor_type}): {value}")
    return warnings + [w for w in result.errors if w != "value must be finite"]


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
                   value: float, quality: str = "good", metadata: dict = None,
                   source_system: str = "sensor_ingester", source_id: str = None,
                   source_raw: dict = None) -> str:
    """Insert a sensor reading into PostgreSQL. Returns record ID."""
    sensor_id, name, slug, sensor_type_id, sensor_type, location_id, plot_id, status, protocol = sensor_info
    reading_time = reading_time or "00:00:00"

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sensor_reading
                (location_id, plot_id, sensor_id, sensor_type, reading_date,
                 reading_time, value, unit, quality, metadata, source_system,
                 source_id, source_raw, schema_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    (SELECT unit FROM sensor_type WHERE id = %s),
                    %s, %s::jsonb, %s, %s, %s::jsonb, 'field-ingestion-v1')
            ON CONFLICT (sensor_id, reading_date, reading_time) DO NOTHING
            RETURNING id
            """,
            (
                location_id, plot_id, str(sensor_id), sensor_type,
                reading_date, reading_time, value, sensor_type_id,
                quality, json.dumps(metadata or {}), source_system, source_id,
                json.dumps(source_raw if source_raw is not None else metadata or {}),
            ),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])
        cur.execute(
            "SELECT id FROM sensor_reading WHERE sensor_id = %s AND reading_date = %s AND reading_time = %s",
            (str(sensor_id), reading_date, reading_time),
        )
        return str(cur.fetchone()[0])


def insert_reading_clickhouse(sensor_info: dict, reading_date: str, reading_time: str,
                               value: float, quality: str = "good", conn=None) -> None:
    """Queue canonical sensor rows; direct writes are demo-only when conn is absent."""
    sensor_id, name, slug, sensor_type_id, sensor_type, location_id, plot_id, status, protocol = sensor_info

    # Build timestamp
    ts_str = f"{reading_date} {reading_time}" if reading_time else f"{reading_date} 00:00:00"
    try:
        ts = datetime.fromisoformat(ts_str.replace(" ", "T") + "+00:00")
    except Exception:
        ts = datetime.now(timezone.utc)

    unit = sensor_type if _UNIT_RE.match(sensor_type) else "unknown"

    try:
        columns = [
            "timestamp", "sensor_id", "sensor_type", "location_id",
            "plot_id", "value", "unit", "quality", "metadata",
        ]
        rows = [[
            ts, str(sensor_id), sensor_type, str(location_id), str(plot_id) if plot_id else "",
            float(value), unit, quality, {},
        ]]
        if conn is not None:
            payload_hash = hash_payload({"sensor_id": str(sensor_id), "reading_date": reading_date,
                                         "reading_time": reading_time, "value": value})
            enqueue(conn, event_key=f"sensor_reading:sensor_readings:{payload_hash}",
                    source_table="sensor_reading", source_id=payload_hash,
                    target_table="sensor_readings", columns=columns, rows=rows,
                    payload_hash=payload_hash)
            return
        # No PostgreSQL transaction means this is an explicit demo/maintenance path.
        insert_clickhouse_rows(
            "sensor_readings",
            columns, rows,
        )
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
                log_ingestion(
                    source_system="csv_upload", source_table="sensor_csv", source_id=f"row_{i + 1}",
                    target_table="sensor_reading", target_id=None, operation="insert",
                    payload_hash=hash_payload(row), status="failed", error_message="missing required fields",
                    validation_status="rejected", validation_errors=["missing required fields"],
                )
                logger.warning("  ✗ Row %d: missing required fields (device_id, reading_date, value)", i + 1)
                continue

            try:
                timestamp = parse_reading_timestamp(reading_date, reading_time)
            except ValueError as exc:
                errors += 1
                log_ingestion(
                    source_system="csv_upload", source_table="sensor_csv", source_id=f"row_{i + 1}",
                    target_table="sensor_reading", target_id=None, operation="insert",
                    payload_hash=hash_payload(row), status="failed", error_message=str(exc),
                    validation_status="rejected", validation_errors=[str(exc)],
                )
                logger.warning("  ✗ Row %d: invalid timestamp: %s", i + 1, exc)
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
            validation = validate_sensor_reading(
                value, sensor_type, "sensor", timestamp, ranges=ranges, identity=device_id
            )
            if validation.status == "rejected":
                errors += 1
                log_ingestion(
                    source_system="csv_upload", source_table="sensor_csv", source_id=f"row_{i + 1}",
                    target_table="sensor_reading", target_id=None, operation="insert",
                    payload_hash=hash_payload(row), status="failed", error_message="; ".join(validation.errors),
                    validation_status="rejected", validation_errors=validation.errors,
                    validation_warnings=validation.warnings, dedupe_key=validation.dedupe_key,
                )
                continue
            quality = "suspect" if validation.status == "suspect" else "good"
            if validation.warnings:
                warnings += 1
                logger.warning("  ⚠ Row %d: %s", i + 1, ', '.join(validation.warnings))

            try:
                pg_id = insert_reading(
                    db, sensor_info, reading_date, reading_time, value, quality,
                    {"csv_row": i + 1, "source_file": file_path},
                    source_system="csv_upload", source_id=f"row_{i + 1}", source_raw=row,
                )
                insert_reading_clickhouse(sensor_info, reading_date, reading_time, value, quality, db)

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
                    validation_status=validation.status,
                    validation_warnings=validation.warnings,
                    dedupe_key=validation.dedupe_key,
                )

                bus = _get_event_bus(conn=db)
                bus.publish(
                    "sensor_reading",
                    {
                        "sensor_id": str(sensor_info[0]),
                        "sensor_type": sensor_info[4],
                        "location_id": str(sensor_info[5]),
                        "value": value,
                        "quality": quality,
                        "reading_date": reading_date,
                        "reading_time": reading_time,
                    },
                    source_table="sensor_reading",
                    source_id=pg_id,
                    priority="normal",
                )

                success += 1

            except Exception as e:
                db.rollback()
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
        global _event_bus
        _event_bus = None
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
        timestamp = parse_reading_timestamp(reading_date, reading_time)

        # Validate
        sensor_type = sensor_info[4]
        validation = validate_sensor_reading(
            value, sensor_type, "sensor", timestamp, ranges=ranges, identity=sensor_id
        )
        if validation.status == "rejected":
            raise ValueError("; ".join(validation.errors))
        quality = "suspect" if validation.status == "suspect" else "good"
        for warning in validation.warnings:
            logger.warning("  ⚠ %s", warning)

        pg_id = insert_reading(
            db, sensor_info, reading_date, reading_time, value, quality,
            {"source": "api", "ingested_at": now.isoformat()},
            source_system="api", source_id=sensor_id,
            source_raw={"sensor_id": sensor_id, "value": value},
        )
        insert_reading_clickhouse(sensor_info, reading_date, reading_time, value, quality, db)

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
            validation_status=validation.status,
            validation_warnings=validation.warnings,
            dedupe_key=validation.dedupe_key,
        )

        bus = _get_event_bus(conn=db)
        bus.publish(
            "sensor_reading",
            {
                "sensor_id": str(sensor_info[0]),
                "sensor_type": sensor_info[4],
                "location_id": str(sensor_info[5]),
                "value": value,
                "quality": quality,
                "reading_date": reading_date,
                "reading_time": reading_time,
                "source": "api",
            },
            source_table="sensor_reading",
            source_id=pg_id,
            priority="normal",
        )

        db.commit()

        name = sensor_info[1]
        logger.info("✓ %s: %.2f (%s) at %s %s", name, value, sensor_type, reading_date, reading_time)
    finally:
        global _event_bus
        _event_bus = None
        db.close()


def list_sensors():
    """List all registered sensors."""
    db = get_db()
    try:
        sensors = get_active_sensors(db)
    finally:
        db.close()

    if not sensors:
        logger.info("No active sensors found.")
        return

    logger.info("%d active sensors:", len(sensors))
    for sid, name, slug, stid, stype, loc_id, plot_id, status, protocol in sensors:
        logger.info("  %s | %s | %s | %s | %s", name, stype, str(loc_id)[:8], protocol or '—', sid)


def check_calibration_status(db) -> list:
    """Check calibration status for all active sensors.

    Returns list of dicts with sensor info and calibration status.
    """
    overdue = []
    with db.cursor() as cur:
        cur.execute("""
            SELECT sd.id, sd.name, sd.slug, st.name as sensor_type,
                   sd.calibration_date, sd.calibration_interval_days,
                   sd.location_id, l.name as location_name
            FROM sensor_device sd
            JOIN sensor_type st ON sd.sensor_type_id = st.id
            LEFT JOIN location l ON sd.location_id = l.id
            WHERE sd.status = 'active'
              AND sd.calibration_date IS NOT NULL
        """)
        for row in cur.fetchall():
            sensor_id = str(row[0])
            name = row[1]
            sensor_type = row[3]
            cal_date = row[4]
            interval_days = row[5] or 365
            location_name = row[7] or "Unknown"

            if cal_date is None:
                continue

            days_since = (datetime.now(timezone.utc).date() - cal_date).days
            days_overdue = days_since - interval_days

            if days_overdue > 0:
                overdue.append({
                    "sensor_id": sensor_id,
                    "name": name,
                    "sensor_type": sensor_type,
                    "location_name": location_name,
                    "calibration_date": cal_date.isoformat(),
                    "interval_days": interval_days,
                    "days_overdue": days_overdue,
                })

    return overdue


def list_calibration_status():
    """List calibration status for all active sensors."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT sd.name, st.name as sensor_type, sd.calibration_date,
                       sd.calibration_interval_days, l.name as location_name
                FROM sensor_device sd
                JOIN sensor_type st ON sd.sensor_type_id = st.id
                LEFT JOIN location l ON sd.location_id = l.id
                WHERE sd.status = 'active'
                ORDER BY sd.calibration_date ASC NULLS LAST
            """)
            sensors = cur.fetchall()

        if not sensors:
            logger.info("No active sensors found.")
            return

        logger.info("Calibration status for %d active sensors:", len(sensors))
        today = datetime.now(timezone.utc).date()
        for name, stype, cal_date, interval_days, loc_name in sensors:
            if cal_date:
                days_since = (today - cal_date).days
                days_remaining = (interval_days or 365) - days_since
                if days_remaining < 0:
                    status = f"OVERDUE by {abs(days_remaining)} days"
                elif days_remaining < 30:
                    status = f"Due in {days_remaining} days"
                else:
                    status = f"OK ({days_remaining} days remaining)"
                logger.info("  %s | %s | %s | %s | %s", name, stype, loc_name or "—", cal_date, status)
            else:
                logger.info("  %s | %s | %s | No calibration date set", name, stype, loc_name or "—")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sensor data ingestion")
    parser.add_argument("--file", help="CSV file path for batch ingestion")
    parser.add_argument("--sensor", help="Sensor UUID or slug for single reading")
    parser.add_argument("--value", type=float, help="Sensor value (with --sensor)")
    parser.add_argument("--date", help="Reading date YYYY-MM-DD (with --sensor)")
    parser.add_argument("--time", help="Reading time HH:MM:SS (with --sensor)")
    parser.add_argument("--list", action="store_true", help="List active sensors")
    parser.add_argument("--calibration", action="store_true", help="List calibration status")
    args = parser.parse_args()

    if args.list:
        list_sensors()
    elif args.calibration:
        list_calibration_status()
    elif args.file:
        run_csv(args.file)
    elif args.sensor and args.value is not None:
        run_single(args.sensor, args.value, args.date, args.time)
    else:
        parser.print_help()
