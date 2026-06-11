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


def insert_weather(db, record: dict) -> str:
    """Insert weather observation into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weather_observation
                (location_id, observation_date, temperature_c,
                 humidity_pct, precipitation_mm, wind_speed_kmh, wind_direction_deg,
                 pressure_hpa, visibility_km, cloud_cover_pct, source, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                record["location_id"], record["observation_date"],
                record["temperature_c"],
                record["humidity_pct"], record["precipitation_mm"],
                record["wind_speed_kmh"], record["wind_direction_deg"],
                record["pressure_hpa"], record["visibility_km"],
                record["cloud_cover_pct"], record["source"],
                record["metadata"],
            ),
        )
        return str(cur.fetchone()[0])


def insert_weather_clickhouse(records: list[dict]) -> None:
    """Insert weather records into ClickHouse weather_events table via HTTP."""
    import requests as req
    from datetime import datetime, timezone
    ch_url = "http://localhost:8123"
    ch_user = "kokonut"
    ch_pass = "dev-clickhouse-kokonut-2026"

    for rec in records:
        meta = rec.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)
        meta_str = ",".join(f"'{k}','{v}'" for k, v in meta.items()) if meta else ""
        meta_map = f"map({meta_str})" if meta_str else "map()"

        # Parse ISO timestamp to ClickHouse DateTime64 format
        obs_date = rec.get("observation_date", "")
        try:
            dt = datetime.fromisoformat(obs_date.replace("Z", "+00:00"))
            ch_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except Exception:
            ch_timestamp = obs_date

        query = f"""INSERT INTO weather_events
            (timestamp, location_id, source, temperature_c, precipitation_mm,
             humidity_pct, wind_speed_kmh, solar_radiation_wm2, cloud_cover_pct, metadata)
            VALUES (
                '{ch_timestamp}',
                '{rec.get("location_id", "")}',
                'openweathermap',
                {rec.get("temperature_c") or 0},
                {rec.get("precipitation_mm") or 0},
                {rec.get("humidity_pct") or 0},
                {rec.get("wind_speed_kmh") or 0},
                {rec.get("solar_radiation_wm2") or 0},
                {rec.get("cloud_cover_pct") or 0},
                {meta_map}
            )"""

        try:
            resp = req.post(
                ch_url,
                data=query.encode("utf-8"),
                auth=(ch_user, ch_pass),
                headers={"Content-Type": "text/plain"},
                timeout=10,
            )
            resp.raise_for_status()
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
