#!/usr/bin/env python3
"""
Mock Sensor Data Generator

Generates simulated sensor readings for testing the ingestion pipeline.
Creates sample sensor devices and generates realistic time-series data
with optional anomalies for testing alerting.

Usage:
    # Register 5 sample sensors
    python -m services.ingestion.mock_sensors --setup

    # Generate 24 hours of data for all sensors
    python -m services.ingestion.mock_sensors --generate

    # Generate with anomalies (for testing alerts)
    python -m services.ingestion.mock_sensors --generate --anomalies

    # Generate specific number of readings
    python -m services.ingestion.mock_sensors --generate --count 100

    # Cleanup test data
    python -m services.ingestion.mock_sensors --cleanup
"""

import argparse
import json
import math
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta

from ..common.logging import get_logger
from .base import get_db, log_ingestion, hash_payload
from .config import CH_HOST, CH_PORT, CH_USER, CH_PASSWORD

logger = get_logger("ingestion.mock_sensors")

# Validation patterns for ClickHouse SQL interpolation
_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
_TS_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
_SENSOR_TYPE_RE = re.compile(r'^[a-z_]+$')

# Sample sensor configurations
SAMPLE_SENSORS = [
    {
        "name": "Soil Moisture Probe A",
        "slug": "soil-moisture-a",
        "sensor_type_name": "soil_moisture",
        "manufacturer": "Watermark",
        "model": "200SS",
        "serial_number": "WM-001-A",
        "protocol": "http",
        "base_value": 35.0,
        "daily_variation": 8.0,
        "noise": 1.5,
    },
    {
        "name": "Soil Temperature Probe A",
        "slug": "soil-temp-a",
        "sensor_type_name": "soil_temperature",
        "manufacturer": "Watermark",
        "model": "200TS",
        "serial_number": "WT-001-A",
        "protocol": "http",
        "base_value": 22.0,
        "daily_variation": 5.0,
        "noise": 0.5,
    },
    {
        "name": "Weather Station — Air Temp",
        "slug": "air-temp-ws",
        "sensor_type_name": "air_temperature",
        "manufacturer": "Davis",
        "model": "Vantage Pro2",
        "serial_number": "DV-WS-001",
        "protocol": "http",
        "base_value": 25.0,
        "daily_variation": 8.0,
        "noise": 0.8,
    },
    {
        "name": "Weather Station — Humidity",
        "slug": "humidity-ws",
        "sensor_type_name": "humidity",
        "manufacturer": "Davis",
        "model": "Vantage Pro2",
        "serial_number": "DV-WS-002",
        "protocol": "http",
        "base_value": 65.0,
        "daily_variation": 15.0,
        "noise": 3.0,
    },
    {
        "name": "Rain Gauge",
        "slug": "rain-gauge-1",
        "sensor_type_name": "rainfall",
        "manufacturer": "Davis",
        "model": "Funnel Gauge",
        "serial_number": "DV-RG-001",
        "protocol": "http",
        "base_value": 0.0,
        "daily_variation": 0.0,
        "noise": 0.0,
    },
]


def _validate_ch_value(value: str, pattern: re.Pattern, name: str) -> str:
    """Validate a value against a regex pattern for ClickHouse SQL safety."""
    if not pattern.match(value):
        raise ValueError(f"Invalid {name} for ClickHouse insert: {value!r}")
    return value


def get_or_create_location(db):
    """Get existing test location or create one."""
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location WHERE name = 'Test Farm - Nairobi' LIMIT 1")
        row = cur.fetchone()
        if row:
            return str(row[0])

        cur.execute("""
            INSERT INTO location (name, slug, status, center)
            VALUES ('Test Farm - Nairobi', 'test-farm-nairobi', 'active',
                    ST_SetSRID(ST_MakePoint(36.8219, -1.2921), 4326))
            RETURNING id
        """)
        return str(cur.fetchone()[0])


def setup_sensors():
    """Register sample sensors in the database."""
    db = get_db()
    location_id = get_or_create_location(db)

    # Get sensor type IDs
    type_ids = {}
    with db.cursor() as cur:
        cur.execute("SELECT id, name FROM sensor_type")
        for row in cur.fetchall():
            type_ids[str(row[0])] = row[1]
            type_ids[row[1]] = str(row[0])

    created = 0
    for sensor in SAMPLE_SENSORS:
        st_name = sensor["sensor_type_name"]
        st_id = type_ids.get(st_name)
        if not st_id:
            logger.warning("  ✗ Sensor type '%s' not found — run 011_sensor_registry.sql first", st_name)
            continue

        with db.cursor() as cur:
            # Check if slug exists
            cur.execute("SELECT id FROM sensor_device WHERE slug = %s", (sensor["slug"],))
            if cur.fetchone():
                logger.info("  ⊙ %s: already exists", sensor['name'])
                continue

            cur.execute(
                """
                INSERT INTO sensor_device
                    (name, slug, sensor_type_id, location_id, manufacturer, model,
                     serial_number, protocol, status, latitude, longitude, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', -1.2921, 36.8219, %s)
                RETURNING id
                """,
                (
                    sensor["name"], sensor["slug"], st_id, location_id,
                    sensor["manufacturer"], sensor["model"], sensor["serial_number"],
                    sensor["protocol"],
                    json.dumps({"base_value": sensor["base_value"],
                                "daily_variation": sensor["daily_variation"],
                                "noise": sensor["noise"]}),
                ),
            )
            sid = cur.fetchone()[0]
            created += 1
            logger.info("  ✓ %s: %s", sensor['name'], sid)

    db.commit()
    db.close()
    logger.info("%d sensors registered", created)


def generate_reading(sensor: dict, timestamp: datetime, inject_anomaly: bool = False) -> float:
    """Generate a realistic sensor reading."""
    base = sensor["base_value"]
    variation = sensor["daily_variation"]
    noise = sensor["noise"]

    # Daily cycle (sinusoidal pattern)
    hour = timestamp.hour + timestamp.minute / 60.0
    daily_cycle = math.sin((hour - 6) * math.pi / 12) * variation / 2

    # Add noise
    reading = base + daily_cycle + random.gauss(0, noise)

    # Inject anomaly if requested
    if inject_anomaly:
        anomaly_type = random.choice(["spike", "drop", "flatline"])
        if anomaly_type == "spike":
            reading = base + variation * 2 + random.gauss(0, noise)
        elif anomaly_type == "drop":
            reading = base - variation * 2 + random.gauss(0, noise)
        elif anomaly_type == "flatline":
            reading = base  # No variation at all

    return round(reading, 2)


def generate_data(count: int = 96, inject_anomalies: bool = False):
    """Generate sensor readings for all active sensors."""
    db = get_db()
    try:
        sensors = []
        with db.cursor() as cur:
            cur.execute("""
                SELECT sd.id, sd.name, sd.slug, sd.sensor_type_id, st.name as sensor_type,
                       sd.location_id, sd.plot_id, sd.status, sd.protocol,
                       sd.metadata
                FROM sensor_device sd
                JOIN sensor_type st ON sd.sensor_type_id = st.id
                WHERE sd.status = 'active'
            """)
            sensors = cur.fetchall()

        if not sensors:
            logger.info("No active sensors found. Run --setup first.")
            return

        logger.info("Generating %d readings for %d sensors...", count, len(sensors))

        now = datetime.now(timezone.utc)
        interval = timedelta(hours=24) / count

        total = 0
        anomalies_injected = 0

        for sensor in sensors:
            sensor_id, name, slug, stid, stype, loc_id, plot_id, status, protocol, metadata = sensor
            sensor_meta = metadata if isinstance(metadata, dict) else json.loads(metadata or "{}")

            # Build sensor_info tuple for insert_reading
            sensor_info = (sensor_id, name, slug, stid, stype, loc_id, plot_id, status, protocol)

            for i in range(count):
                ts = now - timedelta(hours=24) + (interval * i)
                reading_date = ts.strftime("%Y-%m-%d")
                reading_time = ts.strftime("%H:%M:%S")

                # Decide if this reading should be an anomaly
                is_anomaly = inject_anomalies and random.random() < 0.03  # 3% chance

                value = generate_reading(
                    {"base_value": sensor_meta.get("base_value", 0),
                     "daily_variation": sensor_meta.get("daily_variation", 0),
                     "noise": sensor_meta.get("noise", 0)},
                    ts,
                    inject_anomaly=is_anomaly,
                )

                if is_anomaly:
                    anomalies_injected += 1

                # Insert into PostgreSQL
                try:
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
                                loc_id, plot_id, str(sensor_id), stype,
                                reading_date, reading_time, value, stid,
                                "good" if not is_anomaly else "suspect",
                                json.dumps({"mock": True, "anomaly": is_anomaly}),
                            ),
                        )
                        pg_id = cur.fetchone()[0]

                    # Insert into ClickHouse
                    ch_url = f"http://{CH_HOST}:{CH_PORT}"
                    ts_str = f"{reading_date} {reading_time}"

                    # Validate interpolated values
                    _validate_ch_value(ts_str, _TS_RE, "timestamp")
                    _validate_ch_value(str(sensor_id), _UUID_RE, "sensor_id")
                    _validate_ch_value(stype, _SENSOR_TYPE_RE, "sensor_type")
                    _validate_ch_value(str(loc_id), _UUID_RE, "location_id")

                    ch_query = f"""INSERT INTO sensor_readings
                        (timestamp, sensor_id, sensor_type, location_id, plot_id,
                         value, unit, quality, metadata)
                        VALUES (
                            '{ts_str}', '{sensor_id}', '{stype}', '{loc_id}',
                            '{str(plot_id) if plot_id else ''}',
                            {value}, 'mock_unit', 'good', map()
                        )"""
                    try:
                        import requests as req
                        resp = req.post(ch_url, data=ch_query.encode("utf-8"),
                                        auth=(CH_USER, CH_PASSWORD),
                                        headers={"Content-Type": "text/plain"}, timeout=10)
                        resp.raise_for_status()
                    except Exception:
                        pass

                    total += 1

                except Exception as e:
                    logger.error("  ✗ %s @ %s: %s", name, ts, e)

            logger.info("  ✓ %s: %d readings", name, count)

        db.commit()
        logger.info("Done: %d readings, %d anomalies", total, anomalies_injected)
    finally:
        db.close()


def cleanup():
    """Remove all mock sensor data."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM sensor_alert")
        cur.execute("DELETE FROM sensor_reading WHERE metadata->>'mock' = 'true'")
        cur.execute("DELETE FROM sensor_device WHERE metadata->>'mock' IS NOT NULL OR name LIKE 'Soil Moisture%' OR name LIKE 'Weather Station%' OR name LIKE 'Rain Gauge%'")
    db.commit()
    db.close()
    logger.info("Cleanup done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock sensor data generator")
    parser.add_argument("--setup", action="store_true", help="Register sample sensors")
    parser.add_argument("--generate", action="store_true", help="Generate sensor readings")
    parser.add_argument("--count", type=int, default=96, help="Number of readings per sensor (default: 96 = 15min intervals over 24h)")
    parser.add_argument("--anomalies", action="store_true", help="Inject anomalies for testing")
    parser.add_argument("--cleanup", action="store_true", help="Remove mock data")
    args = parser.parse_args()

    if args.setup:
        setup_sensors()
    elif args.generate:
        generate_data(count=args.count, inject_anomalies=args.anomalies)
    elif args.cleanup:
        cleanup()
    else:
        parser.print_help()
