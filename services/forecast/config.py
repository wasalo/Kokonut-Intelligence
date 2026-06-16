"""
Forecast Engine Configuration
"""

from datetime import datetime, timezone

from ..common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

# Dynamic version: v{YYYY}.{MM} — bumps monthly
CALCULATION_VERSION = f"v{datetime.now(timezone.utc).strftime('%Y.%m')}"
CONFIDENCE_LEVEL = 0.80
