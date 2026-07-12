"""EAS attestation indexer driver — wraps services.ingestion.eas_indexer."""

from __future__ import annotations

import os

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "blockchain_eas"
    version = "1.0.0"
    driver_type = "blockchain"

    def validate_config(self, config: dict) -> bool:
        return bool(os.environ.get("EAS_GRAPHQL_URL"))

    def discover(self, config: dict) -> list[dict]:
        return [{"source_id": "eas_attestations", "display_name": "EAS Attestations"}]

    def fetch(self, source: dict) -> dict:
        return {"data": [], "note": "EAS indexer is run as CLI module"}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        return bool(os.environ.get("EAS_GRAPHQL_URL"))
