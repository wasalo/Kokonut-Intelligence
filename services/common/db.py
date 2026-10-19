"""Shared database configuration for Kokonut Intelligence services."""

from __future__ import annotations

import os
import sys

from services.core.providers import ProviderSettings

from .env import load_dotenv
from .worker_environment import ISOLATED_WORKER_KEY_ENV

_HELP_REQUESTED = any(argument in {"-h", "--help"} for argument in sys.argv[1:])
if not _HELP_REQUESTED:
    # Importing a legacy CLI module to render argparse help must not require
    # database credentials. Argparse exits before command work when it sees
    # either help flag; runtime invocations still load and validate secrets.
    load_dotenv()

KOKONUT_ENV = os.environ.get("KOKONUT_ENV", "development").lower()
IS_DEV = KOKONUT_ENV in ("development", "dev", "local")


def _require_secret(name: str) -> str:
    if _HELP_REQUESTED:
        return ""
    value = os.environ.get(name, "")
    if value:
        return value
    if os.environ.get(ISOLATED_WORKER_KEY_ENV):
        # Legacy config may be imported by a CLI parser, but an isolated
        # worker must never inherit or synthesize the shared DB identity.
        return ""
    if IS_DEV:
        return f"placeholder-{name.lower()}"
    raise RuntimeError(
        f"{name} is required. Set the variable in your .env file or environment."
    )


# PostgreSQL
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "kokonut_intelligence")
PG_USER = os.environ.get("PG_USER", "kokonut")
PG_PASSWORD = os.environ.get("PG_PASSWORD") or _require_secret("POSTGRES_PASSWORD")

# ClickHouse
CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", "8123"))
CH_USER = os.environ.get("CH_USER", "kokonut")
CH_PASSWORD = (
    _require_secret("CLICKHOUSE_PASSWORD")
    if ProviderSettings.from_environment().clickhouse
    else os.environ.get("CLICKHOUSE_PASSWORD", "")
)
CH_DB = os.environ.get("CH_DB", "kokonut_analytics")
