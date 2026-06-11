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

from .base import get_db, log_ingestion, hash_payload, retry
from .config import OPENWEATHERMAP_API_KEY

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

    # Convert timestamp to ISO format
    obs_timestamp = data.get("dt", 0)
    obs_date = datetime.fromtimestamp(obs_timestamp, tz=timezone.utc).isoformat()

    return {
        "location_id": location_id,
        "observation_date": obs_date,
        "temperature_c": main.get("temp"),
        "feels_like_c": main.get("feels_like"),
        "humidity_pct": main.get("humidity"),
        "precipitation_mm": rain.get("1h", 0) or rain.get("3h", 0),
        "wind_speed_kmh": (wind.get("speed", 0) or 0) * 3.6,
        "wind_direction_deg": wind.get("deg"),
        "pressure_hpa": main.get("pressure"),
        "visibility_m": data.get("visibility"),
        "cloud_cover_pct": clouds.get("all"),
        "source": "openweathermap",
        "station_id": data.get("id"),
        "metadata": json.dumps({
            "weather_main": data.get("weather", [{}])[0].get("main"),
            "weather_description": data.get("weather", [{}])[0].get("description"),
            "country": data.get("sys", {}).get("country"),
            "sunrise": data.get("sys", {}).get("sunrise"),
            "sunset": data.get("sys", {}).get("sunset"),
        }),
    }


def insert_weather(db, record: dict) -> str:
    """Insert weather observation into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weather_observation
                (location_id, observation_date, temperature_c, feels_like_c,
                 humidity_pct, precipitation_mm, wind_speed_kmh, wind_direction_deg,
                 pressure_hpa, visibility_m, cloud_cover_pct, source, station_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                record["location_id"], record["observation_date"],
                record["temperature_c"], record["feels_like_c"],
                record["humidity_pct"], record["precipitation_mm"],
                record["wind_speed_kmh"], record["wind_direction_deg"],
                record["pressure_hpa"], record["visibility_m"],
                record["cloud_cover_pct"], record["source"],
                record["station_id"], record["metadata"],
            ),
        )
        return str(cur.fetchone()[0])


def insert_weather_clickhouse(records: list[dict]) -> None:
    """Insert weather records into ClickHouse weather_events table."""
    try:
        import clickhouse_connect
        ch = clickhouse_connect.get_client(
            host="localhost", port=8123,
            username="kokonut", password="dev-clickhouse-kokonut-2026",
        )
        for rec in records:
            ch.insert(
                "weather_events",
                [[
                    rec.get("location_id", ""),
                    rec.get("observation_date", ""),
                    rec.get("temperature_c") or 0,
                    rec.get("precipitation_mm") or 0,
                    rec.get("humidity_pct") or 0,
                    rec.get("wind_speed_kmh") or 0,
                    rec.get("pressure_hpa") or 0,
                    rec.get("cloud_cover_pct") or 0,
                    "openweathermap",
                    json.dumps(rec.get("metadata", {})),
                ]],
                column_names=[
                    "location_id", "timestamp", "temperature", "precipitation",
                    "humidity", "wind_speed", "pressure", "cloud_cover",
                    "source", "metadata",
                ],
            )
    except Exception as e:
        print(f"[Weather] ClickHouse insert failed: {e}")


def run(location_id: str = None):
    """Main ingestion entry point."""
    if not OPENWEATHERMAP_API_KEY:
        print("[Weather] ERROR: OpenWeatherMap_API_KEY not set in .env")
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
        print("[Weather] No active locations with coordinates found.")
        return

    print(f"[Weather] Fetching weather for {len(locations)} locations...")
    records = []
    success = 0
    errors = 0

    for loc_id, name, lat, lng in locations:
        try:
            start = time.time()
            raw = fetch_weather(lat, lng)
            elapsed_ms = int((time.time() - start) * 1000)

            record = parse_weather(raw, loc_id)
            pg_id = insert_weather(db, record)
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
            print(f"  ✓ {name}: {record['temperature_c']}°C, {record['humidity_pct']}% humidity")
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
            print(f"  ✗ {name}: {e}")

    db.commit()
    db.close()

    # Insert into ClickHouse
    if records:
        insert_weather_clickhouse(records)

    print(f"\n[Weather] Done: {success} success, {errors} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weather data ingestion")
    parser.add_argument("--location-id", help="Specific location UUID to fetch")
    args = parser.parse_args()
    run(location_id=args.location_id)
