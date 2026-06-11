"""
Ingestion Configuration

Loads API keys and connection details from environment variables.
"""

import os
from pathlib import Path

# Load .env file from project root
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# PostgreSQL
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "kokonut_intelligence")
PG_USER = os.environ.get("PG_USER", "kokonut")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "dev-kokonut-postgres-2026")

# ClickHouse
CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", "8123"))
CH_USER = os.environ.get("CH_USER", "kokonut")
CH_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "dev-clickhouse-kokonut-2026")
CH_DB = os.environ.get("CH_DB", "kokonut_analytics")

# OpenWeatherMap
OPENWEATHERMAP_API_KEY = os.environ.get("OpenWeatherMap_API_KEY", "")

# Ethereum RPC
ETH_RPC_URL = os.environ.get("ETH_RPC_URL", "https://eth.llamarpc.com")
OPTIMISM_RPC_URL = os.environ.get("OPTIMISM_RPC_URL", "https://mainnet.optimism.io")
BASE_RPC_URL = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
ARBITRUM_RPC_URL = os.environ.get("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc")

# EAS
EAS_GRAPHQL_URL = os.environ.get("EAS_GRAPHQL_URL", "https://attest.sh")

# Chain mapping
CHAIN_RPC_MAP = {
    "ethereum": ETH_RPC_URL,
    "optimism": OPTIMISM_RPC_URL,
    "base": BASE_RPC_URL,
    "arbitrum": ARBITRUM_RPC_URL,
}
