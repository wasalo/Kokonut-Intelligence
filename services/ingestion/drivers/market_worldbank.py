"""World Bank Pink Sheet market data driver — wraps services.ingestion.market_data."""

from __future__ import annotations

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "market_worldbank"
    version = "1.0.0"
    driver_type = "market"

    def validate_config(self, config: dict) -> bool:
        return True  # Uses seed data fallback

    def discover(self, config: dict) -> list[dict]:
        commodities = [
            ("coffee", "Coffee (ICO)"),
            ("cocoa", "Cocoa"),
            ("palm_oil", "Palm Oil"),
            ("rice", "Rice"),
            ("maize", "Maize"),
            ("sugar", "Sugar"),
            ("tea", "Tea"),
            ("banana", "Banana"),
        ]
        return [{"source_id": c[0], "display_name": c[1]} for c in commodities]

    def fetch(self, source: dict) -> dict:
        from services.ingestion.market_data import fetch_world_bank_prices

        result = fetch_world_bank_prices()
        return {"data": result}

    def transform(self, raw: dict) -> list[dict]:
        data = raw.get("data")
        if data is None:
            return []
        return [data] if isinstance(data, dict) else list(data)

    def health_check(self, config: dict) -> bool:
        return True  # Always available (seed fallback)
