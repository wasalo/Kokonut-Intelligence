"""EAS chain configuration for Kokonut Intelligence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_CONTRACTS_DIR = Path(__file__).parent / "contracts"

EAS_CHAIN_CONFIG: dict[str, dict[str, Any]] = {
    "celo": {
        "chain_id": 42220,
        "rpc_url": os.environ.get("CELO_RPC_URL", "https://forno.celo.org"),
        "eas_address": "0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92",
        "schema_registry_address": "0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34",
        "explorer": "https://celoscan.io",
        "graphql_endpoint": "https://celo.easscan.org",
    },
    "celo-alfajores": {
        "chain_id": 44787,
        "rpc_url": os.environ.get("CELO_ALFAJORES_RPC_URL", "https://alfajores-forno.celo.org"),
        "eas_address": "0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92",
        "schema_registry_address": "0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34",
        "explorer": "https://alfajores.celoscan.io",
        "graphql_endpoint": "https://alfajores.easscan.org",
    },
    "optimism": {
        "chain_id": 10,
        "rpc_url": os.environ.get("OPTIMISM_RPC_URL", "https://mainnet.optimism.io"),
        "eas_address": "0x4200000000000000000000000000000000000021",
        "schema_registry_address": "0x4200000000000000000000000000000000000020",
        "explorer": "https://optimistic.etherscan.io",
        "graphql_endpoint": "https://optimism.easscan.org",
    },
    "base": {
        "chain_id": 8453,
        "rpc_url": os.environ.get("BASE_RPC_URL", "https://mainnet.base.org"),
        "eas_address": "0x4200000000000000000000000000000000000021",
        "schema_registry_address": "0x4200000000000000000000000000000000000020",
        "explorer": "https://basescan.org",
        "graphql_endpoint": "https://base.easscan.org",
    },
}

DEFAULT_CHAIN = "celo"
KOKONUT_MULTISIG = "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5"
ATTESTER_PRIVATE_KEY = os.environ.get("ATTESTER_PRIVATE_KEY", "")
EAS_RESOLVER_ADDRESS = os.environ.get("EAS_RESOLVER_ADDRESS", "")


def get_chain_config(chain: str) -> dict[str, Any]:
    """Return EAS config for a chain or raise."""
    config = EAS_CHAIN_CONFIG.get(chain)
    if not config:
        raise ValueError(f"Unsupported EAS chain: {chain}. Supported: {list(EAS_CHAIN_CONFIG)}")
    return config


def load_abi(name: str) -> list[dict]:
    """Load an ABI JSON file from the contracts directory."""
    path = _CONTRACTS_DIR / f"{name}.json"
    import json
    return json.loads(path.read_text())
