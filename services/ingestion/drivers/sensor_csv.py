"""CSV sensor driver — wraps services.ingestion.sensor_ingester CSV path."""

from __future__ import annotations

from services.drivers.base import BaseDriver

MAX_SENSOR_CSV_RECORDS = 10_000


class Driver(BaseDriver):
    name = "sensor_csv"
    version = "1.0.0"
    driver_type = "sensor"
    supports_scheduled_pull = True

    def validate_config(self, config: dict) -> bool:
        return "file_path" in config

    def discover(self, config: dict) -> list[dict]:
        return [{"source_id": config.get("file_path", ""), "display_name": "CSV file"}]

    def fetch(self, source: dict) -> dict:
        import csv

        file_path = source.get("source_id", "")
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            rows = []
            for row in reader:
                if len(rows) >= MAX_SENSOR_CSV_RECORDS:
                    raise ValueError(
                        f"sensor CSV exceeds the {MAX_SENSOR_CSV_RECORDS}-record limit"
                    )
                rows.append(row)
        return {"data": rows}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        import os
        file_path = config.get("file_path", "")
        return os.path.isfile(file_path) if file_path else False
