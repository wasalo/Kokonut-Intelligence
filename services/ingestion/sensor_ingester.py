#!/usr/bin/env python3
"""
Sensor Ingestion — Batch and HTTP API

Ingests sensor readings from CSV files or direct API calls.
Validates readings against sensor type ranges, writes to both
PostgreSQL and ClickHouse, and logs to ingestion_log.

Usage:
    # Batch CSV upload
    python -m services.ingestion.sensor_ingester --file data.csv --location-id UUID

    # Single reading (API-style)
    python -m services.ingestion.sensor_ingester --sensor <uuid> --value 25.3 --location-id UUID

    # List registered sensors
    python -m services.ingestion.sensor_ingester --list --location-id UUID
"""

import argparse
import csv
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from uuid import UUID

from ..common.logging import get_logger
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


def get_db():
    """Load database configuration only for an operation that uses the DB."""
    from .base import get_db as get_ingestion_db

    return get_ingestion_db()


def hash_payload(data):
    """Load shared ingestion helpers only when a source operation needs them."""
    from .base import hash_payload as hash_ingestion_payload

    return hash_ingestion_payload(data)


def insert_clickhouse_rows(table, columns, rows):
    """Load the optional ClickHouse adapter only when projecting a reading."""
    from .base import insert_clickhouse_rows as insert_rows

    return insert_rows(table, columns, rows)


def log_ingestion(**kwargs):
    """Load persistence helpers only while recording an ingestion attempt."""
    from .base import log_ingestion as log_ingestion_attempt

    return log_ingestion_attempt(**kwargs)

# Validation patterns
_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
_TS_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
_QUALITY_RE = re.compile(r'^(good|suspect|missing|estimated)$')
_SENSOR_TYPE_RE = re.compile(r'^[a-z_]+$')
_UNIT_RE = re.compile(r'^[a-zA-Z°%µ]+$')
_MAX_SCHEDULED_SENSOR_SOURCES = 100
_MAX_SCHEDULED_SENSOR_RECORDS = 10_000


def _canonical_location_id(location_id: str | None) -> str:
    """Require one canonical location scope before sensor database access."""
    if location_id is None:
        raise ValueError("sensor operations require an explicit location UUID")
    try:
        return str(UUID(str(location_id)))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("location_id must be a UUID") from None

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


def get_sensor_type_ranges(db, *, strict: bool = False) -> dict:
    """Load ranges; strict callers propagate query failures to their transaction."""
    ranges = dict(SENSOR_TYPE_RANGES)
    try:
        with db.cursor() as cur:
            cur.execute("SELECT name, min_value, max_value FROM sensor_type")
            for name, min_val, max_val in cur.fetchall():
                if min_val is not None and max_val is not None:
                    ranges[name] = (float(min_val), float(max_val))
    except Exception:
        if strict:
            raise
    return ranges


def get_active_sensors(db, location_id: str) -> list:
    """Get active sensor devices with type info for one location."""
    location_id = _canonical_location_id(location_id)
    with db.cursor() as cur:
        cur.execute("""
            SELECT sd.id, sd.name, sd.slug, sd.sensor_type_id, st.name as sensor_type,
                   sd.location_id, sd.plot_id, sd.status, sd.protocol
            FROM sensor_device sd
            JOIN sensor_type st ON sd.sensor_type_id = st.id
            WHERE sd.status = 'active'
              AND sd.location_id = %s
        """, (location_id,))
        return cur.fetchall()


def get_sensor_by_id_or_slug(db, identifier: str, location_id: str):
    """Get a sensor by UUID or slug, constrained to one location."""
    location_id = _canonical_location_id(location_id)
    with db.cursor() as cur:
        cur.execute("""
            SELECT sd.id, sd.name, sd.slug, sd.sensor_type_id, st.name as sensor_type,
                   sd.location_id, sd.plot_id, sd.status, sd.protocol
            FROM sensor_device sd
            JOIN sensor_type st ON sd.sensor_type_id = st.id
            WHERE (sd.id::text = %s OR sd.slug = %s)
              AND sd.location_id = %s
        """, (identifier, identifier, location_id))
        return cur.fetchone()


def insert_reading(db, sensor_info: dict, reading_date: str, reading_time: str,
                   value: float, quality: str = "good", metadata: dict = None,
                   source_system: str = "sensor_ingester", source_id: str = None,
                   source_raw: dict = None, *, return_created: bool = False) -> str | tuple[str, bool]:
    """Insert a sensor reading and optionally report whether it was new."""
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
            result = str(row[0])
            return (result, True) if return_created else result
        cur.execute(
            "SELECT id, value, quality FROM sensor_reading WHERE sensor_id = %s AND reading_date = %s AND reading_time = %s",
            (str(sensor_id), reading_date, reading_time),
        )
        existing = cur.fetchone()
        from decimal import ROUND_HALF_UP, Decimal

        canonical_value = Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if existing[1] != canonical_value or existing[2] != quality:
            raise ValueError("Sensor timestamp conflicts with an existing reading")
        result = str(existing[0])
        return (result, False) if return_created else result


def insert_reading_clickhouse(sensor_info: dict, reading_date: str, reading_time: str,
                               value: float, quality: str = "good", conn=None) -> None:
    """Queue canonical sensor rows; direct writes are demo-only when conn is absent."""
    sensor_id, name, slug, sensor_type_id, sensor_type, location_id, plot_id, status, protocol = sensor_info

    if conn is not None:
        # Project the stored source, including its numeric precision and unit.
        # Failure must propagate so the caller can roll back source and outbox.
        from .sensor_projection import project_sensor_reading

        with conn.cursor() as cur:
            cur.execute("""
                SELECT id,location_id,plot_id,sensor_id,sensor_type,value,unit,
                       reading_date,reading_time,quality
                FROM sensor_reading
                WHERE sensor_id=%s AND reading_date=%s AND reading_time=%s
            """, (str(sensor_id), reading_date, reading_time or "00:00:00"))
            reading = cur.fetchone()
        if reading is None:
            raise ValueError("Canonical sensor reading must exist before projection")
        timestamp = datetime.combine(reading[7], reading[8], tzinfo=timezone.utc)
        project_sensor_reading(*reading[:7], timestamp, quality=reading[9], conn=conn)
        return

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
        # No PostgreSQL transaction means this is an explicit demo/maintenance path.
        insert_clickhouse_rows(
            "sensor_readings",
            columns, rows,
        )
    except Exception as e:
        logger.warning("ClickHouse insert failed (%s)", type(e).__name__)


def run_csv(file_path: str, location_id: str | None = None):
    """Batch ingest CSV readings for sensors in one explicit location."""
    location_id = _canonical_location_id(location_id)
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
            device_id = (row.get("device_id") or "").strip()
            reading_date = (row.get("reading_date") or "").strip()
            reading_time = (row.get("reading_time") or "").strip()
            value_str = (row.get("value") or "").strip()

            if not device_id or not reading_date or not value_str:
                errors += 1
                log_ingestion(
                    source_system="csv_upload", source_table="sensor_csv", source_id=f"row_{i + 1}",
                    target_table="sensor_reading", target_id=None, operation="insert",
                    payload_hash=hash_payload(row), status="failed", error_message="missing required fields",
                    validation_status="rejected", validation_errors=["missing required fields"],
                    db=db, location_id=location_id,
                )
                logger.warning("  ✗ Row %d: missing required fields (device_id, reading_date, value)", i + 1)
                continue

            try:
                timestamp = parse_reading_timestamp(reading_date, reading_time)
            except ValueError:
                errors += 1
                log_ingestion(
                    source_system="csv_upload", source_table="sensor_csv", source_id=f"row_{i + 1}",
                    target_table="sensor_reading", target_id=None, operation="insert",
                    payload_hash=hash_payload(row), status="failed", error_message="invalid timestamp",
                    validation_status="rejected", validation_errors=["invalid timestamp"],
                    db=db, location_id=location_id,
                )
                logger.warning("  ✗ Row %d: invalid timestamp", i + 1)
                continue

            try:
                value = float(value_str)
            except (TypeError, ValueError, OverflowError):
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
                    error_message="invalid numeric value",
                    validation_status="rejected",
                    validation_errors=["invalid numeric value"],
                    db=db,
                    location_id=location_id,
                )
                logger.warning("  ✗ Row %d: invalid numeric value", i + 1)
                continue

            # Look up sensor
            sensor_info = get_sensor_by_id_or_slug(db, device_id, location_id)
            if not sensor_info:
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
                    error_message="sensor not found in scoped location",
                    validation_status="rejected",
                    validation_errors=["sensor not found in scoped location"],
                    db=db,
                    location_id=location_id,
                )
                logger.warning("  ✗ Row %d: sensor not found in scoped location", i + 1)
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
                    db=db, location_id=location_id,
                )
                continue
            quality = "suspect" if validation.status == "suspect" else "good"
            if validation.warnings:
                warnings += 1
                logger.warning("  ⚠ Row %d: %s", i + 1, ', '.join(validation.warnings))

            with db.cursor() as cur:
                cur.execute("SAVEPOINT sensor_csv_row")

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
                    db=db,
                    location_id=location_id,
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
                    commit=False,
                )

                with db.cursor() as cur:
                    cur.execute("RELEASE SAVEPOINT sensor_csv_row")

                success += 1

            except Exception as e:
                with db.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT sensor_csv_row")
                    cur.execute("RELEASE SAVEPOINT sensor_csv_row")
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
                    error_message=f"row processing failed ({type(e).__name__})",
                    db=db,
                    location_id=location_id,
                )
                logger.error("  ✗ Row %d processing failed (%s)", i + 1, type(e).__name__)

        db.commit()
        logger.info("Done: %d success, %d warnings, %d errors", success, warnings, errors)
    except Exception:
        db.rollback()
        raise
    finally:
        global _event_bus
        _event_bus = None
        db.close()


def run_driver_instance(instance_id: str, location_id: str) -> dict:
    """Fetch and ingest one enabled sensor pull-driver instance for one location.

    Persisted scheduler arguments contain only the instance and location UUIDs;
    driver configuration and source paths are resolved from the scoped registry.
    The complete instance batch shares one PostgreSQL transaction so a failed
    canonical projection or event enqueue cannot leave partially accepted rows.
    """
    location_id = _canonical_location_id(location_id)
    try:
        instance_id = str(UUID(str(instance_id)))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("driver_instance_id must be a UUID") from None

    from services.drivers.registry import DriverRegistry

    db = get_db()
    registry = DriverRegistry(conn=db)
    instance = None
    started = time.monotonic()
    records_fetched = 0
    records_written = 0
    rejected = 0
    global _event_bus
    _event_bus = None
    try:
        instance = registry.get_schedulable_instance(instance_id, location_id)
        if instance is None:
            raise ValueError("enabled sensor driver instance was not found for this location")

        driver_class = registry.load_schedulable_sensor_driver(instance)
        driver = driver_class(config=instance["config"])
        if getattr(driver, "name", None) != instance["driver_name"]:
            raise ValueError("sensor driver identity does not match its registry entry")
        if getattr(driver, "supports_scheduled_pull", False) is not True:
            raise ValueError("sensor driver does not support scheduled pull ingestion")
        if driver.driver_type != "sensor" or not driver.validate_config(instance["config"]):
            raise ValueError("sensor driver configuration is invalid")

        sources = driver.discover(instance["config"])
        if (
            not isinstance(sources, list)
            or not sources
            or len(sources) > _MAX_SCHEDULED_SENSOR_SOURCES
        ):
            raise ValueError("sensor driver returned an invalid or oversized source list")

        batches = []
        for source_index, source in enumerate(sources):
            if not isinstance(source, dict):
                raise ValueError("sensor driver source descriptors must be objects")
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id.strip():
                raise ValueError("sensor driver source requires a non-empty source_id")
            raw = driver.fetch_scheduled(source)
            records = driver.transform(raw)
            if not isinstance(records, list):
                raise ValueError("sensor driver transform must return a list")
            records_fetched += len(records)
            if records_fetched > _MAX_SCHEDULED_SENSOR_RECORDS:
                raise ValueError("sensor driver exceeded the scheduled record limit")
            source_digest = hash_payload({"source_id": source_id})
            batches.append((source_index, source_digest, records))

        ranges = get_sensor_type_ranges(db, strict=True)
        bus = None
        for source_index, source_digest, records in batches:
            for record_index, record in enumerate(records):
                if not isinstance(record, dict):
                    raise ValueError("sensor driver records must be objects")
                record_location = record.get("location_id")
                if record_location is not None and _canonical_location_id(record_location) != location_id:
                    raise ValueError("sensor driver record location does not match its instance")

                device_id = record.get("device_id")
                reading_date = record.get("reading_date")
                reading_time = record.get("reading_time") or "00:00:00"
                value = record.get("value")
                errors = []
                timestamp = None
                try:
                    timestamp = parse_reading_timestamp(reading_date, reading_time)
                except (TypeError, ValueError):
                    errors.append("invalid reading timestamp")
                try:
                    numeric_value = float(value)
                    if not math.isfinite(numeric_value):
                        raise ValueError
                except (TypeError, ValueError, OverflowError):
                    numeric_value = None
                    errors.append("reading value must be a finite number")
                if not isinstance(device_id, str) or not device_id.strip():
                    errors.append("device_id is required")

                source_key = f"{instance_id}:{source_digest}:{record_index}"
                payload_hash = hash_payload(record)
                if errors:
                    log_ingestion(
                        source_system="sensor_driver",
                        source_table="sensor_driver_record",
                        source_id=source_key,
                        target_table="sensor_reading",
                        target_id=None,
                        operation="insert",
                        payload_hash=payload_hash,
                        status="failed",
                        error_message="; ".join(errors),
                        validation_status="rejected",
                        validation_errors=errors,
                        db=db,
                        location_id=location_id,
                    )
                    rejected += 1
                    continue

                sensor_info = get_sensor_by_id_or_slug(db, device_id, location_id)
                if not sensor_info:
                    errors = ["sensor is not registered as active in the instance location"]
                    log_ingestion(
                        source_system="sensor_driver",
                        source_table="sensor_driver_record",
                        source_id=source_key,
                        target_table="sensor_reading",
                        target_id=None,
                        operation="insert",
                        payload_hash=payload_hash,
                        status="failed",
                        error_message=errors[0],
                        validation_status="rejected",
                        validation_errors=errors,
                        db=db,
                        location_id=location_id,
                    )
                    rejected += 1
                    continue

                validation = validate_sensor_reading(
                    numeric_value,
                    sensor_info[4],
                    "sensor",
                    timestamp,
                    ranges=ranges,
                    identity=device_id,
                )
                if validation.status == "rejected":
                    log_ingestion(
                        source_system="sensor_driver",
                        source_table="sensor_driver_record",
                        source_id=source_key,
                        target_table="sensor_reading",
                        target_id=None,
                        operation="insert",
                        payload_hash=payload_hash,
                        status="failed",
                        error_message="; ".join(validation.errors),
                        validation_status="rejected",
                        validation_errors=validation.errors,
                        validation_warnings=validation.warnings,
                        dedupe_key=validation.dedupe_key,
                        db=db,
                        location_id=location_id,
                    )
                    rejected += 1
                    continue

                quality = "suspect" if validation.status == "suspect" else "good"
                metadata = {
                    "driver_instance_id": instance_id,
                    "source_id_sha256": source_digest,
                    "source_index": source_index,
                    "record_index": record_index,
                }
                pg_id, created = insert_reading(
                    db,
                    sensor_info,
                    reading_date,
                    reading_time,
                    numeric_value,
                    quality,
                    metadata,
                    source_system="sensor_driver",
                    source_id=source_key,
                    source_raw=record,
                    return_created=True,
                )
                insert_reading_clickhouse(
                    sensor_info, reading_date, reading_time, numeric_value, quality, db
                )
                log_ingestion(
                    source_system="sensor_driver",
                    source_table="sensor_driver_record",
                    source_id=source_key,
                    target_table="sensor_reading",
                    target_id=pg_id,
                    operation="insert",
                    payload_hash=payload_hash,
                    rows_affected=1,
                    validation_status=validation.status,
                    validation_warnings=validation.warnings,
                    dedupe_key=validation.dedupe_key,
                    db=db,
                    location_id=location_id,
                )
                if created:
                    if bus is None:
                        bus = _get_event_bus(conn=db)
                    bus.publish(
                        "sensor_reading",
                        {
                            "sensor_id": str(sensor_info[0]),
                            "sensor_type": sensor_info[4],
                            "location_id": location_id,
                            "value": numeric_value,
                            "quality": quality,
                            "reading_date": reading_date,
                            "reading_time": reading_time,
                        },
                        source_table="sensor_reading",
                        source_id=pg_id,
                        priority="normal",
                        commit=False,
                    )
                    records_written += 1

        db.commit()
        duration_ms = int((time.monotonic() - started) * 1000)
        registry.update_instance_status(
            instance_id,
            "success",
            records_fetched=records_fetched,
            records_written=records_written,
            duration_ms=duration_ms,
        )
        logger.info(
            "Scheduled sensor driver %s processed %d records (%d written, %d rejected)",
            instance_id,
            records_fetched,
            records_written,
            rejected,
        )
        return {
            "instance_id": instance_id,
            "location_id": location_id,
            "records_fetched": records_fetched,
            "records_written": records_written,
            "records_rejected": rejected,
            "duration_ms": duration_ms,
        }
    except Exception as exc:
        db.rollback()
        if instance is not None:
            registry.update_instance_status(
                instance_id,
                "failed",
                records_fetched=records_fetched,
                records_written=0,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_message=type(exc).__name__,
            )
        raise
    finally:
        _event_bus = None
        db.close()


def run_single(
    sensor_id: str,
    value: float,
    date_str: str = None,
    time_str: str = None,
    location_id: str | None = None,
):
    """Ingest one reading for a sensor in an explicit location."""
    location_id = _canonical_location_id(location_id)
    db = get_db()
    committed = False
    try:
        ranges = get_sensor_type_ranges(db)

        sensor_info = get_sensor_by_id_or_slug(db, sensor_id, location_id)
        if not sensor_info:
            log_ingestion(
                source_system="api",
                source_table="sensor_api",
                source_id=sensor_id,
                target_table="sensor_reading",
                target_id=None,
                operation="insert",
                payload_hash=hash_payload({"sensor_id": sensor_id, "value": value}),
                status="failed",
                error_message="sensor not found in scoped location",
                validation_status="rejected",
                validation_errors=["sensor not found in scoped location"],
                db=db,
                location_id=location_id,
            )
            db.commit()
            committed = True
            logger.error("Sensor not found in scoped location")
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
            log_ingestion(
                source_system="api",
                source_table="sensor_api",
                source_id=sensor_id,
                target_table="sensor_reading",
                target_id=None,
                operation="insert",
                payload_hash=hash_payload({"sensor_id": sensor_id, "value": value}),
                status="failed",
                error_message="sensor reading rejected by validation",
                validation_status="rejected",
                validation_errors=validation.errors,
                validation_warnings=validation.warnings,
                dedupe_key=validation.dedupe_key,
                db=db,
                location_id=location_id,
            )
            db.commit()
            committed = True
            raise ValueError("sensor reading rejected by validation")
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
            db=db,
            location_id=location_id,
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
            commit=False,
        )

        db.commit()
        committed = True

        name = sensor_info[1]
        logger.info("✓ %s: %.2f (%s) at %s %s", name, value, sensor_type, reading_date, reading_time)
    except Exception:
        if not committed:
            db.rollback()
        raise
    finally:
        global _event_bus
        _event_bus = None
        db.close()


def list_sensors(location_id: str):
    """List registered sensors for one location."""
    location_id = _canonical_location_id(location_id)
    db = get_db()
    try:
        sensors = get_active_sensors(db, location_id)
    finally:
        db.close()

    if not sensors:
        logger.info("No active sensors found.")
        return

    logger.info("%d active sensors:", len(sensors))
    for sid, name, slug, stid, stype, loc_id, plot_id, status, protocol in sensors:
        logger.info("  %s | %s | %s | %s | %s", name, stype, str(loc_id)[:8], protocol or '—', sid)


def check_calibration_status(db, location_id: str) -> list:
    """Check calibration status for active sensors in one location.

    Returns list of dicts with sensor info and calibration status.
    """
    location_id = _canonical_location_id(location_id)
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
              AND sd.location_id = %s
        """, (location_id,))
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


def list_calibration_status(location_id: str):
    """List calibration status for active sensors in one location."""
    location_id = _canonical_location_id(location_id)
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
                  AND sd.location_id = %s
                ORDER BY sd.calibration_date ASC NULLS LAST
            """, (location_id,))
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


def main(argv: list[str] | None = None) -> None:
    """Run one explicit sensor operation; never treat missing input as success."""
    parser = argparse.ArgumentParser(description="Sensor data ingestion")
    parser.add_argument("--file", help="CSV file path for batch ingestion")
    parser.add_argument("--sensor", help="Sensor UUID or slug for single reading")
    parser.add_argument("--value", type=float, help="Sensor value (with --sensor)")
    parser.add_argument("--date", help="Reading date YYYY-MM-DD (with --sensor)")
    parser.add_argument("--time", help="Reading time HH:MM:SS (with --sensor)")
    parser.add_argument("--location-id", help="Required UUID scope for every sensor operation")
    parser.add_argument(
        "--driver-instance-id",
        help="Run one registered, enabled sensor pull-driver instance",
    )
    parser.add_argument("--list", action="store_true", help="List active sensors")
    parser.add_argument("--calibration", action="store_true", help="List calibration status")
    args = parser.parse_args(argv)

    operations = [
        args.file is not None,
        args.sensor is not None,
        args.list,
        args.calibration,
        args.driver_instance_id is not None,
    ]
    if sum(operations) != 1:
        parser.error("choose exactly one of --file, --sensor, --list, or --calibration")
    if args.file is not None and not args.file.strip():
        parser.error("--file requires a non-empty path")
    if args.sensor is not None and not args.sensor.strip():
        parser.error("--sensor requires a non-empty UUID or slug")
    if args.sensor is not None and args.value is None:
        parser.error("--sensor requires --value")
    if args.value is not None and args.sensor is None:
        parser.error("--value requires --sensor")
    if args.sensor is None and (args.date is not None or args.time is not None):
        parser.error("--date and --time require --sensor and --value")

    if args.location_id is None:
        parser.error("sensor operations require --location-id")
    try:
        location_id = _canonical_location_id(args.location_id)
    except ValueError as exc:
        parser.error(str(exc))
    if args.driver_instance_id is not None:
        try:
            args.driver_instance_id = str(UUID(str(args.driver_instance_id)))
        except (ValueError, AttributeError, TypeError):
            parser.error("--driver-instance-id must be a UUID")

    if args.list:
        list_sensors(location_id)
    elif args.calibration:
        list_calibration_status(location_id)
    elif args.driver_instance_id is not None:
        try:
            run_driver_instance(args.driver_instance_id, location_id)
        except Exception as exc:
            parser.exit(1, f"sensor driver failed: {type(exc).__name__}\n")
    elif args.file:
        run_csv(args.file, location_id)
    elif args.sensor and args.value is not None:
        run_single(args.sensor, args.value, args.date, args.time, location_id)


if __name__ == "__main__":
    main()
