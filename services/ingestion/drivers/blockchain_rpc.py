"""RPC wallet activity indexer driver — wraps services.ingestion.rpc_indexer."""

from __future__ import annotations

import os

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "blockchain_rpc"
    version = "1.0.0"
    driver_type = "blockchain"

    def validate_config(self, config: dict) -> bool:
        return bool(os.environ.get("ETH_RPC_URL") or os.environ.get("CELO_RPC_URL"))

    def discover(self, config: dict) -> list[dict]:
        return [{"source_id": "wallet_activity", "display_name": "Wallet Activity"}]

    def fetch(self, source: dict) -> dict:
        return {"data": [], "note": "RPC indexer is run as CLI module"}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        return bool(os.environ.get("ETH_RPC_URL") or os.environ.get("CELO_RPC_URL"))
