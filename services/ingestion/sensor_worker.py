"""Run scheduled CSV sensor ingestion through signed bounded database calls."""

from __future__ import annotations

import argparse
import json
import math
import time
from uuid import UUID

from services.common.cli import print_json, run
from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.core.features import is_enabled
from services.drivers.registry import DriverRegistry
from services.ingestion.base import hash_payload
from services.ingestion.field_validation import parse_reading_timestamp, validate_sensor_reading

_MAX_SOURCES = 100
_MAX_RECORDS = 10_000
_MAX_RECORD_BYTES = 65_536
_MAX_BATCH_BYTES = 67_108_864
_WORKER_KEY = "sensor_ingestion"
_RESOURCE = "sensor_driver"
_ACTION = "ingest"


def _open_scoped_connection(location_id: str, credential: str):
    connection = get_worker_db(_WORKER_KEY)
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource=_RESOURCE,
            action=_ACTION,
        )
    except Exception:
        connection.close()
        raise
    return connection


def _resolve_instance(instance_id: str, location_id: str, credential: str) -> dict:
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT instance_id::text, instance_name, driver_name, module_path, "
                "class_name, driver_type, config, location_id::text "
                "FROM kokonut_security.resolve_sensor_driver_instance(%s::uuid, %s::uuid)",
                (instance_id, location_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("enabled sensor driver instance was not found in signed scope")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    config = row[6]
    if isinstance(config, str):
        config = json.loads(config)
    if not isinstance(config, dict):
        raise ValueError("sensor driver instance config must be an object")
    return {
        "instance_id": str(row[0]),
        "instance_name": str(row[1]),
        "driver_name": str(row[2]),
        "module_path": str(row[3]),
        "class_name": str(row[4]),
        "driver_type": str(row[5]),
        "config": config,
        "location_id": str(row[7]),
    }


def _load_catalog(location_id: str, credential: str) -> list[tuple]:
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sensor_id::text, sensor_name, sensor_slug, sensor_type_id::text, "
                "sensor_type, location_id::text, plot_id::text, sensor_status, protocol, "
                "unit, min_value, max_value "
                "FROM kokonut_security.read_sensor_driver_catalog(%s::uuid)",
                (location_id,),
            )
            rows = cursor.fetchall()
        connection.commit()
        return rows
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _prepare_records(
    instance: dict,
    location_id: str,
    catalog_rows: list[tuple],
) -> tuple[list[dict], int]:
    """Fetch and validate code-allowlisted source records without DB access."""
    driver_class = DriverRegistry.load_schedulable_sensor_driver(instance)
    driver = driver_class(config=instance["config"])
    if (
        getattr(driver, "name", None) != instance["driver_name"]
        or getattr(driver, "supports_scheduled_pull", False) is not True
        or driver.driver_type != "sensor"
        or not driver.validate_config(instance["config"])
    ):
        raise ValueError("sensor driver does not satisfy the scheduled-pull contract")

    sensors_by_id: dict[str, tuple] = {}
    sensors_by_slug: dict[str, tuple] = {}
    ranges: dict[str, tuple[float, float]] = {}
    for row in catalog_rows:
        sensors_by_id[str(row[0])] = row
        if row[2]:
            sensors_by_slug[str(row[2])] = row
        if row[10] is not None and row[11] is not None:
            ranges[str(row[4])] = (float(row[10]), float(row[11]))

    sources = driver.discover(instance["config"])
    if not isinstance(sources, list) or not sources or len(sources) > _MAX_SOURCES:
        raise ValueError("sensor driver returned an invalid or oversized source list")

    prepared: list[dict] = []
    records_fetched = 0
    estimated_batch_bytes = 2
    for source_index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("sensor driver source descriptors must be objects")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("sensor driver source requires a non-empty source identifier")
        raw = driver.fetch_scheduled(source)
        records = driver.transform(raw)
        if not isinstance(records, list):
            raise ValueError("sensor driver transform must return a list")
        records_fetched += len(records)
        if records_fetched > _MAX_RECORDS:
            raise ValueError("sensor driver exceeded the scheduled record limit")
        source_digest = hash_payload({"source_id": source_id})

        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError("sensor driver records must be objects")
            record_bytes = len(
                json.dumps(record, default=str, separators=(",", ":")).encode("utf-8")
            )
            if record_bytes > _MAX_RECORD_BYTES:
                raise ValueError("sensor driver record exceeds its payload limit")
            estimated_batch_bytes += record_bytes + 512
            if estimated_batch_bytes > _MAX_BATCH_BYTES:
                raise ValueError("sensor driver batch exceeds its payload limit")
            record_location = record.get("location_id")
            if record_location is not None:
                try:
                    canonical_record_location = str(UUID(str(record_location)))
                except (ValueError, TypeError, AttributeError):
                    raise ValueError("sensor driver record location is invalid") from None
                if canonical_record_location != location_id:
                    raise ValueError("sensor driver record location does not match its instance")

            errors: list[str] = []
            warnings: list[str] = []
            device_id = record.get("device_id")
            reading_date = record.get("reading_date")
            reading_time = record.get("reading_time") or "00:00:00"
            value = record.get("value")
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
                sensor = None
            else:
                sensor = sensors_by_id.get(device_id) or sensors_by_slug.get(device_id)
                if sensor is None:
                    errors.append("sensor is not registered in the instance location")

            dedupe_key = None
            validation_status = "rejected"
            if not errors and sensor is not None and timestamp is not None:
                validation = validate_sensor_reading(
                    numeric_value,
                    str(sensor[4]),
                    "sensor",
                    timestamp,
                    ranges=ranges,
                    identity=device_id,
                )
                validation_status = validation.status
                errors = list(validation.errors)
                warnings = list(validation.warnings)
                dedupe_key = validation.dedupe_key

            prepared.append({
                "source_id_sha256": source_digest,
                "source_index": source_index,
                "record_index": record_index,
                "payload_hash": hash_payload(record),
                "record": record,
                "validation_status": validation_status,
                "validation_errors": errors,
                "validation_warnings": warnings,
                "dedupe_key": dedupe_key,
            })
    return prepared, records_fetched


def _store_batch(
    instance_id: str,
    location_id: str,
    credential: str,
    records: list[dict],
) -> tuple[int, int, int]:
    payload = json.dumps(records, default=str)
    if len(payload.encode("utf-8")) > _MAX_BATCH_BYTES:
        raise ValueError("sensor driver batch exceeds its payload limit")
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT records_fetched, records_written, records_rejected "
                "FROM kokonut_security.store_sensor_driver_batch(%s::uuid, %s::uuid, %s::jsonb)",
                (instance_id, location_id, payload),
            )
            result = cursor.fetchone()
            if result is None:
                raise RuntimeError("sensor ingestion function returned no result")
        connection.commit()
        return tuple(int(value) for value in result)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _update_status(
    instance_id: str,
    location_id: str,
    credential: str,
    *,
    status: str,
    records_fetched: int,
    records_written: int,
    duration_ms: int,
    error: str | None,
) -> None:
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.update_sensor_driver_status(%s::uuid, %s::uuid, "
                "%s, %s, %s, %s, %s)",
                (
                    instance_id,
                    location_id,
                    status,
                    records_fetched,
                    records_written,
                    min(600_000, max(0, duration_ms)),
                    error,
                ),
            )
            row = cursor.fetchone()
            if row is None or row[0] is not True:
                raise ValueError("sensor driver instance status could not be updated")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ingest(instance_id: str, location_id: str) -> dict[str, int | str]:
    """Process one registered sensor driver within one signed location grant."""
    canonical_instance_id = str(UUID(str(instance_id)))
    canonical_location_id = str(UUID(str(location_id)))
    credential = get_worker_credential(_WORKER_KEY)
    started = time.monotonic()
    instance: dict | None = None
    records_fetched = 0
    records_written = 0
    records_rejected = 0

    try:
        instance = _resolve_instance(canonical_instance_id, canonical_location_id, credential)
        catalog = _load_catalog(canonical_location_id, credential)
        prepared, records_fetched = _prepare_records(instance, canonical_location_id, catalog)
        fetched, records_written, records_rejected = _store_batch(
            canonical_instance_id, canonical_location_id, credential, prepared
        )
        if fetched != records_fetched:
            raise RuntimeError("sensor ingestion batch count did not match its source count")
        duration_ms = min(600_000, max(0, int((time.monotonic() - started) * 1000)))
        _update_status(
            canonical_instance_id,
            canonical_location_id,
            credential,
            status="success",
            records_fetched=records_fetched,
            records_written=records_written,
            duration_ms=duration_ms,
            error=None,
        )
        return {
            "instance_id": canonical_instance_id,
            "location_id": canonical_location_id,
            "records_fetched": records_fetched,
            "records_written": records_written,
            "records_rejected": records_rejected,
            "duration_ms": duration_ms,
        }
    except Exception as exc:
        if instance is not None:
            try:
                _update_status(
                    canonical_instance_id,
                    canonical_location_id,
                    credential,
                    status="failed",
                    records_fetched=records_fetched,
                    records_written=0,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error=type(exc).__name__,
                )
            except Exception:
                pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest scheduled sensor CSV through signed worker scope")
    parser.add_argument("--driver-instance-id", required=True, help="Registered sensor driver instance UUID")
    parser.add_argument("--location-id", required=True, help="Authorized location UUID")
    args = parser.parse_args()
    try:
        instance_id = str(UUID(str(args.driver_instance_id)))
        location_id = str(UUID(str(args.location_id)))
    except (TypeError, ValueError, AttributeError):
        parser.error("driver instance and location IDs must be UUIDs")
    if not is_enabled("signed_sensor_ingestion_worker"):
        parser.error("signed sensor-ingestion worker is disabled")
    print_json({"status": "success", **ingest(instance_id, location_id)})


if __name__ == "__main__":
    run(main)
