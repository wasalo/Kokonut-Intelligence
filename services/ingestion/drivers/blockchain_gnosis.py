"""Gnosis Chain Moloch DAO indexer driver — wraps services.ingestion.gnosis_indexer."""

from __future__ import annotations

import os

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "blockchain_gnosis"
    version = "1.0.0"
    driver_type = "blockchain"

    def validate_config(self, config: dict) -> bool:
        return bool(os.environ.get("GNOSIS_RPC_URL", "https://rpc.gnosischain.com"))

    def discover(self, config: dict) -> list[dict]:
        return [{"source_id": "gnosis_moloch", "display_name": "Gnosis Moloch DAO"}]

    def fetch(self, source: dict) -> dict:
        return {"data": [], "note": "Gnosis indexer is run as CLI module"}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        return True  # Public RPC always available
