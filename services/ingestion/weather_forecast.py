#!/usr/bin/env python3
"""
Weather Forecast — OpenWeatherMap 5-Day / 3-Hour

Fetches 5-day weather forecasts for all active locations and inserts into
weather_forecast (PostgreSQL) and weather_events (ClickHouse).

Usage:
    python -m services.ingestion.weather_forecast
    python -m services.ingestion.weather_forecast --location-id <uuid>
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone, date

import requests

from ..common.logging import get_logger
from .base import get_db, get_clickhouse, log_ingestion, hash_payload, retry
from .config import OPENWEATHERMAP_API_KEY

logger = get_logger("ingestion.weather_forecast")

API_BASE = "https://api.openweathermap.org/data/2.5/forecast"


@retry(max_retries=3, backoff=2.0)
def fetch_forecast_raw(lat: float, lon: float) -> dict:
    """Fetch 5-day / 3-hour forecast from OpenWeatherMap API."""
    resp = requests.get(
        API_BASE,
        params={
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHERMAP_API_KEY,
            "units": "metric",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def parse_forecast_list(data: dict, location_id: str) -> list[dict]:
    """Map OpenWeatherMap forecast list to weather_forecast records."""
    records = []
    for item in data.get("list", []):
        dt_timestamp = item.get("dt", 0)
        dt_obj = datetime.fromtimestamp(dt_timestamp, tz=timezone.utc)

        main = item.get("main", {})
        wind = item.get("wind", {})
        rain = item.get("rain", {})
        clouds = item.get("clouds", {})

        records.append({
            "location_id": location_id,
            "source": "openweathermap",
            "forecast_date": dt_obj.date().isoformat(),
            "forecast_hour": dt_obj.hour,
            "temp_c": main.get("temp"),
            "temp_min_c": main.get("temp_min"),
            "temp_max_c": main.get("temp_max"),
            "feels_like_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "precipitation_mm": rain.get("3h", 0) or 0,
            "precipitation_prob_pct": (item.get("pop", 0) or 0) * 100,
            "rain_3h_mm": rain.get("3h", 0) or 0,
            "wind_speed_kmh": (wind.get("speed", 0) or 0) * 3.6,
            "wind_direction_deg": wind.get("deg"),
            "wind_gust_kmh": (wind.get("gust", 0) or 0) * 3.6,
            "cloud_cover_pct": clouds.get("all"),
            "visibility_km": (item.get("visibility") or 0) / 1000,
            "pressure_hpa": main.get("pressure"),
            "uv_index": item.get("uv"),
            "description": item.get("weather", [{}])[0].get("description"),
            "metadata": json.dumps({
                "weather_main": item.get("weather", [{}])[0].get("main"),
                "weather_id": item.get("weather", [{}])[0].get("id"),
                "dt_txt": item.get("dt_txt"),
                "pop_raw": item.get("pop"),
            }),
        })
    return records


def insert_forecasts(db, records: list[dict], source_raw: dict = None) -> int:
    """Insert weather forecasts into PostgreSQL. Returns count inserted."""
    if not records:
        return 0

    inserted = 0
    with db.cursor() as cur:
        for rec in records:
            try:
                cur.execute(
                    """
                    INSERT INTO weather_forecast
                        (location_id, source, forecast_date, forecast_hour,
                         temp_c, temp_min_c, temp_max_c, feels_like_c,
                         humidity_pct, precipitation_mm, precipitation_prob_pct,
                         rain_3h_mm, wind_speed_kmh, wind_direction_deg,
                         wind_gust_kmh, cloud_cover_pct, visibility_km,
                         pressure_hpa, uv_index, description, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (location_id, forecast_date, forecast_hour, source)
                    DO UPDATE SET
                        temp_c = EXCLUDED.temp_c,
                        temp_min_c = EXCLUDED.temp_min_c,
                        temp_max_c = EXCLUDED.temp_max_c,
                        feels_like_c = EXCLUDED.feels_like_c,
                        humidity_pct = EXCLUDED.humidity_pct,
                        precipitation_mm = EXCLUDED.precipitation_mm,
                        precipitation_prob_pct = EXCLUDED.precipitation_prob_pct,
                        rain_3h_mm = EXCLUDED.rain_3h_mm,
                        wind_speed_kmh = EXCLUDED.wind_speed_kmh,
                        wind_direction_deg = EXCLUDED.wind_direction_deg,
                        wind_gust_kmh = EXCLUDED.wind_gust_kmh,
                        cloud_cover_pct = EXCLUDED.cloud_cover_pct,
                        visibility_km = EXCLUDED.visibility_km,
                        pressure_hpa = EXCLUDED.pressure_hpa,
                        uv_index = EXCLUDED.uv_index,
                        description = EXCLUDED.description,
                        metadata = EXCLUDED.metadata,
                        created_at = NOW()
                    """,
                    (
                        rec["location_id"], rec["source"], rec["forecast_date"],
                        rec["forecast_hour"], rec["temp_c"], rec["temp_min_c"],
                        rec["temp_max_c"], rec["feels_like_c"], rec["humidity_pct"],
                        rec["precipitation_mm"], rec["precipitation_prob_pct"],
                        rec["rain_3h_mm"], rec["wind_speed_kmh"],
                        rec["wind_direction_deg"], rec["wind_gust_kmh"],
                        rec["cloud_cover_pct"], rec["visibility_km"],
                        rec["pressure_hpa"], rec["uv_index"],
                        rec["description"], rec["metadata"],
                    ),
                )
                inserted += 1
            except Exception as e:
                logger.warning("Failed to insert forecast for %s %s: %s",
                               rec["forecast_date"], rec["forecast_hour"], e)
    return inserted


def insert_forecasts_clickhouse(records: list[dict]) -> None:
    """Insert forecast records into ClickHouse weather_events table."""
    client = get_clickhouse()
    if client is None:
        logger.warning("ClickHouse client unavailable — skipping weather_events insert")
        return

    rows = []
    for rec in records:
        meta = rec.get("metadata", "{}")
        if isinstance(meta, str):
            meta = json.loads(meta)

        try:
            ts = datetime.fromisoformat(
                f"{rec['forecast_date']}T{rec['forecast_hour']:02d}:00:00+00:00"
            )
        except Exception:
            ts = datetime.now(timezone.utc)

        rows.append([
            ts,
            str(rec.get("location_id", "")),
            "openweathermap_forecast",
            float(rec.get("temp_c") or 0),
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


def get_daily_summary(db, location_id: str, days: int = 5) -> list[dict]:
    """Query daily forecast summary view."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT forecast_date, temp_min_c, temp_max_c, temp_avg_c,
                   precipitation_total_mm, max_precip_prob_pct,
                   avg_humidity_pct, avg_wind_speed_kmh, max_uv_index
            FROM v_weather_forecast_daily
            WHERE location_id = %s
              AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + %s
            ORDER BY forecast_date
            """,
            (location_id, days),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_spray_windows(db, location_id: str, days: int = 5) -> list[dict]:
    """Query spray window view for suitable days."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT forecast_date, avg_wind_speed_kmh, max_precip_prob_pct,
                   temp_avg_c, spray_suitability
            FROM v_spray_window
            WHERE location_id = %s
              AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + %s
            ORDER BY forecast_date
            """,
            (location_id, days),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def run(location_id: str = None):
    """Main forecast ingestion entry point."""
    if not OPENWEATHERMAP_API_KEY:
        logger.error("OPENWEATHERMAP_API_KEY not set in .env")
        sys.exit(1)

    db = get_db()
    with db.cursor() as cur:
        if location_id:
            cur.execute(
                "SELECT id, name, ST_Y(center) as lat, ST_X(center) as lng "
                "FROM location WHERE id = %s AND status = 'active'",
                (location_id,),
            )
        else:
            cur.execute(
                "SELECT id, name, ST_Y(center) as lat, ST_X(center) as lng "
                "FROM location WHERE status = 'active' AND center IS NOT NULL"
            )
        locations = cur.fetchall()

    if not locations:
        logger.info("No active locations with coordinates found.")
        return

    logger.info("Fetching 5-day forecasts for %d locations...", len(locations))
    all_records = []
    success = 0
    errors = 0

    for loc_id, name, lat, lng in locations:
        try:
            start = time.time()
            raw = fetch_forecast_raw(lat, lng)
            elapsed_ms = int((time.time() - start) * 1000)

            records = parse_forecast_list(raw, loc_id)
            inserted = insert_forecasts(db, records, source_raw=raw)
            all_records.extend(records)

            log_ingestion(
                source_system="openweathermap",
                source_table="forecast_api",
                source_id=str(raw.get("city", {}).get("id", "")),
                target_table="weather_forecast",
                target_id=None,
                operation="insert",
                payload_hash=hash_payload(raw),
                status="success",
                rows_affected=inserted,
                processing_time_ms=elapsed_ms,
            )
            success += 1
            logger.info("  ✓ %s: %d forecast points", name, inserted)
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            errors += 1
            log_ingestion(
                source_system="openweathermap",
                source_table="forecast_api",
                source_id="",
                target_table="weather_forecast",
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
    if all_records:
        insert_forecasts_clickhouse(all_records)

    logger.info("Done: %d success, %d errors, %d total forecast points",
                success, errors, len(all_records))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weather forecast ingestion (5-day / 3-hour)")
    parser.add_argument("--location-id", help="Specific location UUID to fetch")
    args = parser.parse_args()
    run(location_id=args.location_id)
