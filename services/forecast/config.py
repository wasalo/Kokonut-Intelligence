"""
Forecast Engine Configuration

Loads database connection details from environment variables.
"""

import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "kokonut_intelligence")
PG_USER = os.environ.get("PG_USER", "kokonut")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "dev-kokonut-postgres-2026")

CALCULATION_VERSION = "v1.0"
CONFIDENCE_LEVEL = 0.80
