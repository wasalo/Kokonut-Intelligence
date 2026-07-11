#!/usr/bin/env python3
"""
Weather Ingestion — OpenWeatherMap

Fetches current weather data for all active locations and inserts into
weather_observation (PostgreSQL) and weather_events (ClickHouse).

Usage:
    python -m services.ingestion.weather
    python -m services.ingestion.weather --location-id <uuid>
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import requests

from ..common.logging import get_logger
from .base import get_db, get_clickhouse, log_ingestion, hash_payload, retry
from .config import OPENWEATHERMAP_API_KEY

logger = get_logger("ingestion.weather")

API_BASE = "https://api.openweathermap.org/data/2.5/weather"



@retry(max_retries=3, backoff=2.0)
def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current weather from OpenWeatherMap API."""
    resp = requests.get(
        API_BASE,
        params={
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHERMAP_API_KEY,
            "units": "metric",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def parse_weather(data: dict, location_id: str) -> dict:
    """Map OpenWeatherMap response to weather_observation schema."""
    main = data.get("main", {})
    wind = data.get("wind", {})
    rain = data.get("rain", {})
    clouds = data.get("clouds", {})

    obs_timestamp = data.get("dt", 0)
    obs_datetime = datetime.fromtimestamp(obs_timestamp, tz=timezone.utc)

    return {
        "location_id": location_id,
        "observation_date": obs_datetime.date().isoformat(),
        "observation_time": obs_datetime.time().replace(microsecond=0).isoformat(),
        "temperature_c": main.get("temp"),
        "humidity_pct": main.get("humidity"),
        "precipitation_mm": rain.get("1h", 0) or rain.get("3h", 0),
        "wind_speed_kmh": (wind.get("speed", 0) or 0) * 3.6,
        "wind_direction_deg": wind.get("deg"),
        "pressure_hpa": main.get("pressure"),
        "visibility_km": (data.get("visibility") or 0) / 1000,
        "cloud_cover_pct": clouds.get("all"),
        "source": "openweathermap",
        "station_id": str(data.get("id", "")),
        "metadata": json.dumps({
            "weather_main": data.get("weather", [{}])[0].get("main"),
            "weather_description": data.get("weather", [{}])[0].get("description"),
            "country": data.get("sys", {}).get("country"),
            "sunrise": data.get("sys", {}).get("sunrise"),
            "sunset": data.get("sys", {}).get("sunset"),
        }),
    }


def insert_weather(db, record: dict, source_raw: dict = None) -> str:
    """Insert weather observation into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weather_observation
                (location_id, observation_date, observation_time, temperature_c,
                 humidity_pct, precipitation_mm, wind_speed_kmh, wind_direction_deg,
                 pressure_hpa, visibility_km, cloud_cover_pct, source, metadata, source_raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING id
            """,
            (
                record["location_id"], record["observation_date"],
                record["observation_time"],
                record["temperature_c"],
                record["humidity_pct"], record["precipitation_mm"],
                record["wind_speed_kmh"], record["wind_direction_deg"],
                record["pressure_hpa"], record["visibility_km"],
                record["cloud_cover_pct"], record["source"],
                record["metadata"],
                json.dumps(source_raw) if source_raw else None,
            ),
        )
        return str(cur.fetchone()[0])


def insert_weather_clickhouse(records: list[dict]) -> None:
    """Insert weather records into ClickHouse weather_events table."""
    client = get_clickhouse()
    if client is None:
        logger.warning("ClickHouse client unavailable — skipping weather_events insert")
        return

    rows = []
    for rec in records:
        meta = rec.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)

        obs_date = rec.get("observation_date", "")
        obs_time = rec.get("observation_time") or "00:00:00"
        try:
            ts = datetime.fromisoformat(f"{obs_date}T{obs_time}+00:00")
        except Exception:
            ts = datetime.now(timezone.utc)

        rows.append([
            ts,
            str(rec.get("location_id", "")),
            "openweathermap",
            float(rec.get("temperature_c") or 0),
            float(rec.get("precipitation_mm") or 0),
            float(rec.get("humidity_pct") or 0),
            float(rec.get("wind_speed_kmh") or 0),
            float(rec.get("solar_radiation_wm2") or 0),
            float(rec.get("cloud_cover_pct") or 0),
            {str(k): str(v) for k, v in meta.items()},
        ])

    if not rows:
        return

    try:
        client.insert(
            "weather_events",
            rows,
            column_names=[
                "timestamp", "location_id", "source", "temperature_c",
                "precipitation_mm", "humidity_pct", "wind_speed_kmh",
                "solar_radiation_wm2", "cloud_cover_pct", "metadata",
            ],
        )
    except Exception as e:
        logger.warning("ClickHouse insert failed: %s", e)


def run(location_id: str = None):
    """Main ingestion entry point."""
    if not OPENWEATHERMAP_API_KEY:
        logger.error("OpenWeatherMap_API_KEY not set in .env")
        sys.exit(1)

    db = get_db()
    with db.cursor() as cur:
        if location_id:
            cur.execute(
                "SELECT id, name, ST_Y(center) as lat, ST_X(center) as lng FROM location WHERE id = %s AND status = 'active'",
                (location_id,),
            )
        else:
            cur.execute(
                "SELECT id, name, ST_Y(center) as lat, ST_X(center) as lng FROM location WHERE status = 'active' AND center IS NOT NULL"
            )
        locations = cur.fetchall()

    if not locations:
        logger.info("No active locations with coordinates found.")
        return

    logger.info("Fetching weather for %d locations...", len(locations))
    records = []
    success = 0
    errors = 0

    for loc_id, name, lat, lng in locations:
        try:
            start = time.time()
            raw = fetch_weather(lat, lng)
            elapsed_ms = int((time.time() - start) * 1000)

            record = parse_weather(raw, loc_id)
            pg_id = insert_weather(db, record, source_raw=raw)
            records.append(record)

            log_ingestion(
                source_system="openweathermap",
                source_table="weather_api",
                source_id=str(raw.get("id", "")),
                target_table="weather_observation",
                target_id=pg_id,
                operation="insert",
                payload_hash=hash_payload(raw),
                status="success",
                rows_affected=1,
                processing_time_ms=elapsed_ms,
            )
            success += 1
            logger.info("  ✓ %s: %.1f°C, %d%% humidity", name, record['temperature_c'], record['humidity_pct'])
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            errors += 1
            log_ingestion(
                source_system="openweathermap",
                source_table="weather_api",
                source_id="",
                target_table="weather_observation",
                target_id=None,
                operation="insert",
                payload_hash="",
                status="failed",
                error_message=str(e),
            )
            logger.error("  ✗ %s: %s", name, e)

    db.commit()
    db.close()

    # Insert into ClickHouse
    if records:
        insert_weather_clickhouse(records)

    logger.info("Done: %d success, %d errors", success, errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weather data ingestion")
    parser.add_argument("--location-id", help="Specific location UUID to fetch")
    args = parser.parse_args()
    run(location_id=args.location_id)
