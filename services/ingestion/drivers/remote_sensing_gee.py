"""Google Earth Engine remote sensing driver — wraps services.ingestion.gee_remote_sensing."""

from __future__ import annotations

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "remote_sensing_gee"
    version = "1.0.0"
    driver_type = "remote_sensing"

    def validate_config(self, config: dict) -> bool:
        return True  # Uses GEE service account from env

    def discover(self, config: dict) -> list[dict]:
        from services.ingestion.base import get_db

        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT id, name FROM location WHERE status = 'active'"
                )
                return [{"source_id": str(r[0]), "display_name": r[1]} for r in cur.fetchall()]
        finally:
            db.close()

    def fetch(self, source: dict) -> dict:
        return {"data": [], "note": "GEE fetch delegated to remote_sensing_fetcher"}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        try:
            import ee
            ee.Initialize()
            return True
        except Exception:
            return False
