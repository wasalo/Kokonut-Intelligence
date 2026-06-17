"""
Ingestion Configuration

Loads API keys and connection details from environment variables.
"""

import os

from ..common.db import (
    CH_DB,
    CH_HOST,
    CH_PASSWORD,
    CH_PORT,
    CH_USER,
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_USER,
)

# OpenWeatherMap
OPENWEATHERMAP_API_KEY = os.environ.get("OpenWeatherMap_API_KEY", "")

# Ethereum RPC
ETH_RPC_URL = os.environ.get("ETH_RPC_URL", "https://eth.llamarpc.com")
OPTIMISM_RPC_URL = os.environ.get("OPTIMISM_RPC_URL", "https://mainnet.optimism.io")
BASE_RPC_URL = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
ARBITRUM_RPC_URL = os.environ.get("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc")
CELO_RPC_URL = os.environ.get("CELO_RPC_URL", "https://forno.celo.org")
CELO_ALFAJORES_RPC_URL = os.environ.get("CELO_ALFAJORES_RPC_URL", "https://alfajores-forno.celo.org")
GNOSIS_RPC_URL = os.environ.get("GNOSIS_RPC_URL", "https://rpc.gnosischain.com")

# EAS
EAS_GRAPHQL_URL = os.environ.get("EAS_GRAPHQL_URL", "https://attest.sh")

# EAS Attestation
ATTESTER_PRIVATE_KEY = os.environ.get("ATTESTER_PRIVATE_KEY", "")
EAS_RESOLVER_ADDRESS = os.environ.get("EAS_RESOLVER_ADDRESS", "")

# Chain mapping
CHAIN_RPC_MAP = {
    "ethereum": ETH_RPC_URL,
    "optimism": OPTIMISM_RPC_URL,
    "base": BASE_RPC_URL,
    "arbitrum": ARBITRUM_RPC_URL,
    "celo": CELO_RPC_URL,
    "celo-alfajores": CELO_ALFAJORES_RPC_URL,
    "gnosis": GNOSIS_RPC_URL,
}

# Kokonut Moloch DAO contracts (Gnosis Chain)
KOKONUT_DAO_CHAIN = "gnosis"
KOKONUT_MOLOCH_ADDRESSES = {
    "treasury": "0xeb55b75328a8dffd45bbf34b7e7efc431a179085",
    "token_manager": "0x8977c56e979f0d8b76afb5ad85549acd2e96422d",
    "vkkn_token": "0xc6b075ac3234a7ac729114b27370b552fa284690",
    "loot_token": "0x2508a11aee11ad545bae87cd42131c04613b2099",
}

# EAS contract addresses per chain
EAS_CHAIN_CONFIG = {
    "celo": {
        "chain_id": 42220,
        "eas_address": "0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92",
        "schema_registry_address": "0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34",
        "eas_explorer": "https://celoscan.io",
        "graphql_endpoint": "https://celo.easscan.org",
    },
    "optimism": {
        "chain_id": 10,
        "eas_address": "0x4200000000000000000000000000000000000021",
        "schema_registry_address": "0x4200000000000000000000000000000000000020",
        "eas_explorer": "https://optimistic.etherscan.io",
        "graphql_endpoint": "https://optimism.easscan.org",
    },
    "base": {
        "chain_id": 8453,
        "eas_address": "0x4200000000000000000000000000000000000021",
        "schema_registry_address": "0x4200000000000000000000000000000000000020",
        "eas_explorer": "https://basescan.org",
        "graphql_endpoint": "https://base.easscan.org",
    },
    "celo-alfajores": {
        "chain_id": 44787,
        "eas_address": "0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92",
        "schema_registry_address": "0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34",
        "eas_explorer": "https://alfajores.celoscan.io",
        "graphql_endpoint": "https://alfajores.easscan.org",
    },
}
