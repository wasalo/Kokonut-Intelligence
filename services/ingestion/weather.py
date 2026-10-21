#!/usr/bin/env python3
"""
Weather Ingestion — OpenWeatherMap

Fetches current weather data for all active locations and inserts into
weather_observation (PostgreSQL) and weather_events (ClickHouse).

Usage:
    python -m services.ingestion.weather --location-id <uuid>
    python -m services.ingestion.weather --all-locations
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone

from services.common.http import http

from ..common.logging import get_logger
from .base import get_db, hash_payload, insert_clickhouse_rows, log_ingestion, retry
from .clickhouse_outbox import enqueue
from .config import OPENWEATHERMAP_API_KEY

logger = get_logger("ingestion.weather")

API_BASE = "https://api.openweathermap.org/data/2.5/weather"
WEATHER_CLICKHOUSE_COLUMNS = [
    "timestamp", "location_id", "source", "temperature_c",
    "precipitation_mm", "humidity_pct", "wind_speed_kmh",
    "solar_radiation_wm2", "cloud_cover_pct", "metadata",
]



@retry(max_retries=3, backoff=2.0)
def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current weather from OpenWeatherMap API."""
    resp = http.get(
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


def build_weather_clickhouse_projection(records: list[dict]) -> dict:
    """Build the canonical ClickHouse rows for current weather observations."""
    rows = []
    for rec in records:
        meta = rec.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)

        obs_date = rec.get("observation_date", "")
        obs_time = rec.get("observation_time") or "00:00:00"
        try:
            ts = datetime.fromisoformat(f"{obs_date}T{obs_time}")
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
        except (TypeError, ValueError):
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

    return {
        "columns": list(WEATHER_CLICKHOUSE_COLUMNS),
        "rows": rows,
        "payload_hash": hash_payload(records) if rows else "",
    }


def insert_weather_clickhouse(records: list[dict], conn=None) -> None:
    """Queue canonical weather rows; direct writes are demo-only when conn is absent."""
    projection = build_weather_clickhouse_projection(records)
    rows = projection["rows"]
    if not rows:
        return

    try:
        if conn is not None:
            payload_hash = projection["payload_hash"]
            enqueue(conn, event_key=f"weather:weather_events:{payload_hash}",
                    source_table="weather_observation", source_id=payload_hash,
                    target_table="weather_events",
                    columns=projection["columns"],
                    rows=rows, payload_hash=payload_hash)
            return
        # No PostgreSQL transaction means this is an explicit demo/maintenance path.
        insert_clickhouse_rows(
            "weather_events",
            projection["columns"],
            rows,
        )
    except Exception as e:
        if conn is not None:
            raise
        logger.warning("ClickHouse insert failed (%s)", type(e).__name__)


def run(location_id: str = None, *, all_locations: bool = False):
    """Main ingestion entry point."""
    if all_locations and location_id is not None:
        raise ValueError("choose one location or the explicit all-locations mode")
    if not all_locations and location_id is None:
        raise ValueError("provide --location-id or explicitly select all locations")
    if location_id is not None:
        try:
            location_id = str(uuid.UUID(str(location_id)))
        except (ValueError, AttributeError, TypeError):
            raise ValueError("location_id must be a UUID") from None

    if not OPENWEATHERMAP_API_KEY:
        logger.error("OpenWeatherMap_API_KEY not set in .env")
        sys.exit(1)

    db = get_db()
    try:
        with db.cursor() as cur:
            if location_id:
                cur.execute(
                    "SELECT id, name, ST_Y(center) as lat, ST_X(center) as lng FROM location WHERE id = %s AND status = 'active' AND center IS NOT NULL",
                    (location_id,),
                )
            else:
                cur.execute(
                    "SELECT id, name, ST_Y(center) as lat, ST_X(center) as lng FROM location WHERE status = 'active' AND center IS NOT NULL"
                )
            locations = cur.fetchall()
    except Exception:
        try:
            db.close()
        except Exception as close_error:
            logger.warning("Database close failed (%s)", type(close_error).__name__)
        raise

    if not locations:
        logger.info("No active locations with coordinates found.")
        db.close()
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
            safe_error = f"weather location processing failed ({type(e).__name__})"
            log_ingestion(
                source_system="openweathermap",
                source_table="weather_api",
                source_id="",
                target_table="weather_observation",
                target_id=None,
                operation="insert",
                payload_hash="",
                status="failed",
                error_message=safe_error,
            )
            logger.error("  ✗ %s failed (%s)", name, type(e).__name__)

    try:
        if records:
            insert_weather_clickhouse(records, db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("Done: %d success, %d errors", success, errors)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Weather data ingestion")
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--location-id", help="Specific location UUID to fetch")
    location.add_argument(
        "--all-locations",
        action="store_true",
        help="Fetch weather for every active location (explicit aggregate operation)",
    )
    args = parser.parse_args(argv)

    if args.location_id is None and not args.all_locations:
        parser.print_help()
        return

    try:
        run(location_id=args.location_id, all_locations=args.all_locations)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
