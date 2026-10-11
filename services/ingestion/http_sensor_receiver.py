"""HTTP webhook receiver for IoT sensor data.

FastAPI-based HTTP server that receives sensor readings via POST,
validates HMAC signatures, and writes to PostgreSQL + ClickHouse.

Requires:
    - fastapi package
    - uvicorn package

Usage:
    python3 -m services.ingestion.http_sensor_receiver
    uvicorn services.ingestion.http_sensor_receiver:app --host 0.0.0.0 --port 8056
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.events.backend import get_event_store

from ..common.logging import get_logger
from .base import get_db, hash_payload, log_ingestion
from .field_validation import get_transport_timestamp_mode, parse_transport_timestamp, validate_sensor_reading
from .sensor_ingester import get_sensor_type_ranges
from .sensor_projection import project_sensor_reading

logger = get_logger("ingestion.http_sensor_receiver")

# FastAPI app (created lazily)
app = None


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify an HMAC-SHA256 signature for the exact request body."""
    if not payload or not signature or not secret:
        return False
    provided = signature.strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def _get_app():
    """Create FastAPI app lazily."""
    global app
    if app is not None:
        return app

    timestamp_mode = get_transport_timestamp_mode()

    try:
        from fastapi import FastAPI, Header, HTTPException, Request
        from pydantic import BaseModel, Field
    except ImportError:
        logger.error("fastapi not installed. Run: pip install fastapi uvicorn")
        return None

    app = FastAPI(
        title="Kokonut Sensor Receiver",
        description="HTTP webhook for IoT sensor readings",
        version="1.0.0",
    )
    from .http_sensor_limits import SensorBodyLimit

    app.add_middleware(SensorBodyLimit)

    class SensorReading(BaseModel):
        device_id: str = Field(min_length=1, max_length=255)
        value: float
        unit: str = Field(default="", max_length=64)
        timestamp: Optional[str] = Field(default=None, max_length=128)
        quality: str = Field(default="good", max_length=32)

    class BatchReadings(BaseModel):
        readings: List[SensorReading] = Field(min_length=1, max_length=100)

    def _get_device_secret(device_id: str) -> Optional[str]:
        """Get shared secret for a device from metadata."""
        db = get_db()
        cur = None
        try:
            cur = db.cursor()
            cur.execute(
                "SELECT metadata->>'shared_secret' FROM sensor_device WHERE slug = %s AND status = 'active'",
                (device_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None
        finally:
            try:
                if cur is not None:
                    cur.close()
            finally:
                db.close()

    def _process_reading(reading: SensorReading, authenticated_secret: str) -> Dict[str, Any]:
        """Process a single sensor reading."""
        db = None
        cur = None
        try:
            db = get_db()
            cur = db.cursor()
            cur.execute("SET LOCAL lock_timeout = '5s'")

            # Look up device
            cur.execute("""
                SELECT sd.id, sd.location_id, sd.plot_id, st.name AS sensor_type,
                       sd.metadata->>'shared_secret'
                FROM sensor_device sd
                JOIN sensor_type st ON st.id = sd.sensor_type_id
                WHERE sd.slug = %s AND sd.status = 'active'
                FOR SHARE OF sd
            """, (reading.device_id,))
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": f"Unknown device: {reading.device_id}"}
            if not row[4] or not hmac.compare_digest(row[4], authenticated_secret):
                return {"status": "error", "message": "Device credentials changed; authenticate again",
                        "retryable": False}

            device_db_id = str(row[0])
            location_id = str(row[1])
            plot_id = str(row[2]) if row[2] else None
            sensor_type = row[3]

            # Parse timestamp
            try:
                ts = parse_transport_timestamp(reading.timestamp, timestamp_mode)
            except (TypeError, ValueError, OverflowError):
                return {"status": "error", "message": "Invalid reading timestamp", "retryable": False}

            ranges = get_sensor_type_ranges(db, strict=True)
            validation = validate_sensor_reading(
                reading.value, sensor_type, reading.unit, ts, reading.quality,
                ranges=ranges, identity=reading.device_id,
            )
            if validation.status == "rejected":
                log_ingestion(
                    source_system="http_sensor", source_table="sensor_reading",
                    source_id=reading.device_id, target_table="sensor_reading", target_id=None,
                    operation="insert", payload_hash=hash_payload(reading.dict()),
                    status="failed", error_message="; ".join(validation.errors),
                    validation_status="rejected", validation_errors=validation.errors,
                    validation_warnings=validation.warnings, dedupe_key=validation.dedupe_key,
                )
                return {"status": "error", "message": "; ".join(validation.errors)}
            quality = "suspect" if validation.status == "suspect" else "good"

            # Insert reading
            cur.execute("""
                INSERT INTO sensor_reading
                    (location_id, plot_id, sensor_id, sensor_type, reading_date, reading_time, value, unit, quality,
                     source_system, source_id, source_raw, schema_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'field-ingestion-v1')
                ON CONFLICT (sensor_id, reading_date, reading_time) DO NOTHING
                RETURNING id
            """, (
                location_id, plot_id, device_db_id, sensor_type,
                ts.date(), ts.time(), reading.value, reading.unit, quality,
                "http_sensor", reading.device_id, json.dumps(reading.dict()),
            ))
            inserted = cur.fetchone()
            if not inserted:
                db.commit()
                log_ingestion(
                    source_system="http_sensor", source_table="sensor_reading",
                    source_id=reading.device_id, target_table="sensor_reading", target_id=None,
                    operation="insert", payload_hash=hash_payload(reading.dict()),
                    status="partial", error_message="duplicate reading",
                    validation_status="duplicate", dedupe_key=validation.dedupe_key,
                )
                return {"status": "duplicate", "device_id": reading.device_id}
            reading_id = str(inserted[0])

            # Update device health
            cur.execute("""
                INSERT INTO sensor_device_health (device_id, last_seen_at, status)
                VALUES (%s, NOW(), 'online')
                ON CONFLICT (device_id) DO UPDATE SET
                    last_seen_at = NOW(),
                    status = 'online',
                    updated_at = NOW()
            """, (device_db_id,))

            # Enqueue before commit so the source row and analytical delivery are atomic.
            _insert_ch(
                reading_id, location_id, plot_id, device_db_id, sensor_type,
                reading.value, reading.unit, ts, quality, db,
            )
            event_store = get_event_store(conn=db)
            event_store.publish(
                "sensor_reading",
                {
                    "sensor_id": device_db_id,
                    "sensor_type": sensor_type,
                    "location_id": location_id,
                    "value": reading.value,
                    "quality": quality,
                    "reading_date": ts.date().isoformat(),
                    "reading_time": ts.time().replace(tzinfo=None).isoformat(),
                    "source": "http_sensor",
                },
                source_table="sensor_reading",
                source_id=reading_id,
                priority="normal",
            )
            # Publish with the same connection so source, health, outbox, and
            # durable platform event become visible atomically.
            db.commit()

            log_ingestion(
                    source_system="http_sensor",
                source_table="sensor_reading",
                source_id=reading.device_id,
                target_table="sensor_reading",
                target_id=reading_id,
                operation="insert",
                payload_hash=hash_payload(reading.dict()),
                    status="success",
                    rows_affected=1,
                    validation_status=validation.status,
                    validation_warnings=validation.warnings,
                    dedupe_key=validation.dedupe_key,
                )

            return {"status": "success", "reading_id": reading_id}

        except Exception as e:
            logger.exception("Error processing reading: %s", e)
            return {"status": "error", "message": "Unable to process sensor reading", "retryable": True}
        finally:
            try:
                if cur is not None:
                    cur.close()
            finally:
                try:
                    # Clear rejected, failed, and read-only transactions as well
                    # as any transaction opened after a successful commit.
                    if db is not None:
                        db.rollback()
                finally:
                    if db is not None:
                        db.close()

    def _authenticated_secret(device_id: str) -> Optional[str]:
        try:
            return _get_device_secret(device_id)
        except Exception:
            logger.exception("Sensor credential lookup unavailable")
            raise HTTPException(status_code=503, detail="Sensor storage unavailable", headers={"Retry-After": "30"})

    def _process_with_retry_outcome(reading: SensorReading, authenticated_secret: str) -> Dict[str, Any]:
        try:
            return _process_reading(reading, authenticated_secret)
        except Exception:
            # Cleanup/commit uncertainty can occur after a durable write. The
            # caller must retry the same timestamp, not generate a new reading.
            logger.exception("Sensor processing cleanup failed")
            return {"status": "error", "message": "Unable to process sensor reading", "retryable": True}

    @app.post("/api/v1/sensors/{device_id}/readings")
    async def receive_reading(
        device_id: str,
        reading: SensorReading,
        request: Request,
        x_signature: Optional[str] = Header(None),
    ):
        """Receive a single sensor reading."""
        secret = _authenticated_secret(device_id)
        if not secret or not x_signature or not _verify_signature(
            await request.body(), x_signature, secret
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing signature")

        if reading.device_id != device_id:
            raise HTTPException(status_code=400, detail="Payload device does not match URL device")
        reading.device_id = device_id

        result = _process_with_retry_outcome(reading, secret)
        if result["status"] == "error":
            if result.get("retryable"):
                raise HTTPException(status_code=503, detail=result["message"], headers={"Retry-After": "30"})
            raise HTTPException(status_code=400, detail=result["message"])
        return result

    @app.post("/api/v1/sensors/{device_id}/readings/batch")
    async def receive_batch(
        device_id: str,
        batch: BatchReadings,
        request: Request,
        x_signature: Optional[str] = Header(None),
    ):
        """Receive multiple sensor readings."""
        secret = _authenticated_secret(device_id)
        if not secret or not x_signature or not _verify_signature(
            await request.body(), x_signature, secret
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing signature")

        if any(reading.device_id != device_id for reading in batch.readings):
            raise HTTPException(status_code=400, detail="Payload device does not match URL device")
        results = []
        for reading in batch.readings:
            reading.device_id = device_id
            result = _process_with_retry_outcome(reading, secret)
            results.append(result)

        success = sum(1 for r in results if r["status"] == "success")
        retryable = sum(1 for r in results if r.get("retryable"))
        return {"total": len(results), "success": success, "results": results,
                "retryable": retryable, "retry_after_seconds": 30 if retryable else 0}

    @app.get("/api/v1/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

    return app


def _insert_ch(reading_id, location_id, plot_id, sensor_id, sensor_type, value, unit, timestamp, quality="good", conn=None):
    """Compatibility wrapper over the shared sensor projection."""
    if conn is not None:
        return project_sensor_reading(reading_id, location_id, plot_id, sensor_id, sensor_type,
                                      value, unit, timestamp, quality, conn)
    try:
        project_sensor_reading(reading_id, location_id, plot_id, sensor_id, sensor_type,
                               value, unit, timestamp, quality)
    except Exception as exc:
        logger.warning("ClickHouse insert failed: %s", exc)

def run(host: str = "0.0.0.0", port: int = 8056):
    """Run the HTTP sensor receiver."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is required for the HTTP sensor receiver") from exc

    if not 1 <= port <= 65535:
        raise ValueError("Receiver port must be between 1 and 65535")

    _get_app()
    if app is None:
        raise RuntimeError("FastAPI is required for the HTTP sensor receiver")

    logger.info("Starting HTTP sensor receiver on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, proxy_headers=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HTTP sensor receiver")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8056, help="Bind port")
    args = parser.parse_args()

    run(host=args.host, port=args.port)
