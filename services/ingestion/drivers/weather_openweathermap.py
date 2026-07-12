"""OpenWeatherMap weather driver — wraps services.ingestion.weather."""

from __future__ import annotations

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "weather_openweathermap"
    version = "1.0.0"
    driver_type = "weather"

    def validate_config(self, config: dict) -> bool:
        return True  # Uses env vars (OPENWEATHERMAP_API_KEY)

    def discover(self, config: dict) -> list[dict]:
        from services.ingestion.base import get_db

        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT id, name FROM location WHERE status = 'active'")
                return [{"source_id": str(r[0]), "display_name": r[1]} for r in cur.fetchall()]
        finally:
            db.close()

    def fetch(self, source: dict) -> dict:
        from services.ingestion.weather import fetch_weather_for_location

        result = fetch_weather_for_location(source["source_id"])
        return {"data": result}

    def transform(self, raw: dict) -> list[dict]:
        data = raw.get("data")
        if data is None:
            return []
        return [data] if isinstance(data, dict) else list(data)

    def health_check(self, config: dict) -> bool:
        import os
        return bool(os.environ.get("OPENWEATHERMAP_API_KEY"))
