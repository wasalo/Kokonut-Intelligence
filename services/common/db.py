"""Shared database configuration for Kokonut Intelligence services."""

from __future__ import annotations

import os
from pathlib import Path

from .env import load_dotenv

load_dotenv()

KOKONUT_ENV = os.environ.get("KOKONUT_ENV", "development").lower()
IS_DEV = KOKONUT_ENV in ("development", "dev", "local")

_DEV_PG_PASSWORD = "dev-kokonut-postgres-2026"
_DEV_CH_PASSWORD = "dev-clickhouse-kokonut-2026"


def _require_secret(name: str, dev_fallback: str) -> str:
    value = os.environ.get(name, "")
    if value:
        return value
    if IS_DEV:
        return dev_fallback
    raise RuntimeError(
        f"{name} is required when KOKONUT_ENV={KOKONUT_ENV!r}. "
        f"Set the variable or use KOKONUT_ENV=development for local dev."
    )


# PostgreSQL
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "kokonut_intelligence")
PG_USER = os.environ.get("PG_USER", "kokonut")
PG_PASSWORD = _require_secret("POSTGRES_PASSWORD", _DEV_PG_PASSWORD)

# ClickHouse
CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", "8123"))
CH_USER = os.environ.get("CH_USER", "kokonut")
CH_PASSWORD = _require_secret("CLICKHOUSE_PASSWORD", _DEV_CH_PASSWORD)
CH_DB = os.environ.get("CH_DB", "kokonut_analytics")
