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

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..common.logging import get_logger
from .base import get_db, log_ingestion, hash_payload, post_clickhouse_rows

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

    try:
        from fastapi import FastAPI, HTTPException, Header, Request
        from fastapi.responses import JSONResponse
        from pydantic import BaseModel, Field
    except ImportError:
        logger.error("fastapi not installed. Run: pip install fastapi uvicorn")
        return None

    app = FastAPI(
        title="Kokonut Sensor Receiver",
        description="HTTP webhook for IoT sensor readings",
        version="1.0.0",
    )

    class SensorReading(BaseModel):
        device_id: str
        value: float
        unit: str = ""
        timestamp: Optional[str] = None
        quality: str = "good"

    class BatchReadings(BaseModel):
        readings: List[SensorReading]

    def _get_device_secret(device_id: str) -> Optional[str]:
        """Get shared secret for a device from metadata."""
        db = get_db()
        try:
            cur = db.cursor()
            cur.execute(
                "SELECT metadata->>'shared_secret' FROM sensor_device WHERE slug = %s",
                (device_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None
        finally:
            db.close()

    def _process_reading(reading: SensorReading) -> Dict[str, Any]:
        """Process a single sensor reading."""
        db = get_db()
        try:
            cur = db.cursor()

            # Look up device
            cur.execute("""
                SELECT sd.id, sd.location_id, sd.plot_id, st.name AS sensor_type
                FROM sensor_device sd
                JOIN sensor_type st ON st.id = sd.sensor_type_id
                WHERE sd.slug = %s
            """, (reading.device_id,))
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": f"Unknown device: {reading.device_id}"}

            device_db_id = str(row[0])
            location_id = str(row[1])
            plot_id = str(row[2]) if row[2] else None
            sensor_type = row[3]

            # Parse timestamp
            if reading.timestamp:
                ts = datetime.fromisoformat(reading.timestamp.replace("Z", "+00:00"))
            else:
                ts = datetime.now(timezone.utc)

            # Insert reading
            cur.execute("""
                INSERT INTO sensor_reading
                    (location_id, plot_id, sensor_id, sensor_type, reading_date, reading_time, value, unit, quality)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                location_id, plot_id, device_db_id, sensor_type,
                ts.date(), ts.time(), reading.value, reading.unit, reading.quality,
            ))
            reading_id = str(cur.fetchone()[0])

            # Update device health
            cur.execute("""
                INSERT INTO sensor_device_health (device_id, last_seen_at, status)
                VALUES (%s, NOW(), 'online')
                ON CONFLICT (device_id) DO UPDATE SET
                    last_seen_at = NOW(),
                    status = 'online',
                    updated_at = NOW()
            """, (device_db_id,))

            db.commit()

            # Dual-write to ClickHouse
            _insert_ch(reading_id, location_id, plot_id, device_db_id, sensor_type, reading.value, reading.unit, ts)

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
            )

            return {"status": "success", "reading_id": reading_id}

        except Exception as e:
            logger.exception("Error processing reading: %s", e)
            return {"status": "error", "message": "Unable to process sensor reading"}
        finally:
            db.close()

    @app.post("/api/v1/sensors/{device_id}/readings")
    async def receive_reading(
        device_id: str,
        reading: SensorReading,
        request: Request,
        x_signature: Optional[str] = Header(None),
    ):
        """Receive a single sensor reading."""
        secret = _get_device_secret(device_id)
        if not secret or not x_signature or not _verify_signature(
            await request.body(), x_signature, secret
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing signature")

        if reading.device_id != device_id:
            raise HTTPException(status_code=400, detail="Payload device does not match URL device")
        reading.device_id = device_id

        result = _process_reading(reading)
        if result["status"] == "error":
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
        secret = _get_device_secret(device_id)
        if not secret or not x_signature or not _verify_signature(
            await request.body(), x_signature, secret
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing signature")

        results = []
        for reading in batch.readings:
            if reading.device_id != device_id:
                raise HTTPException(status_code=400, detail="Payload device does not match URL device")
            reading.device_id = device_id
            result = _process_reading(reading)
            results.append(result)

        success = sum(1 for r in results if r["status"] == "success")
        return {"total": len(results), "success": success, "results": results}

    @app.get("/api/v1/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

    return app


def _insert_ch(reading_id, location_id, plot_id, sensor_id, sensor_type, value, unit, timestamp):
    """Insert reading into ClickHouse."""
    try:
        post_clickhouse_rows(
            "sensor_readings",
            ["timestamp", "sensor_id", "sensor_type", "location_id", "plot_id",
             "value", "unit", "quality", "metadata"],
            [[timestamp, str(sensor_id), str(sensor_type), str(location_id),
              str(plot_id or ""), float(value), str(unit or ""), "good", {}]],
        )
    except Exception as e:
        logger.warning("ClickHouse insert failed: %s", e)


def run(host: str = "0.0.0.0", port: int = 8056):
    """Run the HTTP sensor receiver."""
    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn not installed. Run: pip install uvicorn")
        return

    _get_app()
    if app is None:
        return

    logger.info("Starting HTTP sensor receiver on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HTTP sensor receiver")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8056, help="Bind port")
    args = parser.parse_args()

    run(host=args.host, port=args.port)
