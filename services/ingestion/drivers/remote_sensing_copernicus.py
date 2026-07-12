"""Copernicus Data Space remote sensing driver — wraps services.ingestion.copernicus_remote_sensing."""

from __future__ import annotations

import os

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "remote_sensing_copernicus"
    version = "1.0.0"
    driver_type = "remote_sensing"

    def validate_config(self, config: dict) -> bool:
        return bool(os.environ.get("COPERNICUS_CLIENT_ID"))

    def discover(self, config: dict) -> list[dict]:
        return [{"source_id": "copernicus_catalog", "display_name": "Copernicus OData Catalog"}]

    def fetch(self, source: dict) -> dict:
        return {"data": [], "note": "Copernicus fetch delegated to remote_sensing_fetcher"}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        return bool(os.environ.get("COPERNICUS_CLIENT_ID"))
