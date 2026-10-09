#!/usr/bin/env python3
"""
Weather Forecast Driver — OpenWeatherMap 5-Day / 3-Hour

Driver plugin for the weather forecast ingestion pipeline.
"""

from services.drivers.base import BaseDriver
from services.common.logging import get_logger

logger = get_logger("drivers.weather_forecast")


class Driver(BaseDriver):
    name = "weather_forecast"
    version = "1.0.0"
    driver_type = "weather_forecast"

    def validate_config(self, config: dict) -> bool:
        import os
        return bool(os.environ.get("OPENWEATHERMAP_API_KEY"))

    def discover(self) -> list[dict]:
        from services.common.database import get_db
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM location WHERE status = 'active'"
            )
            rows = cur.fetchall()
        db.close()
        return [{"id": str(r[0]), "name": r[1]} for r in rows]

    def fetch(self, location: dict) -> list[dict]:
        from services.ingestion.weather_forecast import fetch_forecast_raw, parse_forecast_list
        from services.common.database import get_db
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "SELECT ST_Y(center) as lat, ST_X(center) as lng FROM location WHERE id = %s",
                (location["id"],),
            )
            row = cur.fetchone()
        db.close()
        if not row or row[0] is None:
            return []
        raw = fetch_forecast_raw(row[0], row[1])
        return parse_forecast_list(raw, location["id"])

    def transform(self, records: list[dict]) -> list[dict]:
        return records

    def health_check(self) -> bool:
        import os
        return bool(os.environ.get("OPENWEATHERMAP_API_KEY"))
