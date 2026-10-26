#!/usr/bin/env python3
"""Print global mismatch counts for location-bound landscape references.

Set LANDSCAPE_REFERENCE_PREFLIGHT_DSN to an explicitly selected read-only
database target. The DSN is never printed. No database is selected by default.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.analytics.landscape_reference_preflight import (  # noqa: E402
    get_location_reference_mismatch_counts,
)


def main() -> int:
    dsn = os.environ.get("LANDSCAPE_REFERENCE_PREFLIGHT_DSN", "")
    if not dsn:
        print(json.dumps({
            "result": "blocked",
            "reason": "LANDSCAPE_REFERENCE_PREFLIGHT_DSN must select the read-only target",
        }, sort_keys=True))
        return 2

    connection = None
    try:
        connection = psycopg2.connect(
            dsn,
            connect_timeout=8,
            application_name="kokonut-landscape-reference-preflight",
        )
        report = get_location_reference_mismatch_counts(connection)
        connection.commit()
    except Exception as exc:  # noqa: BLE001 - sanitize database/DSN details.
        if connection is not None:
            connection.rollback()
        print(json.dumps({
            "result": "failed",
            "error_type": type(exc).__name__,
            "sqlstate": getattr(exc, "pgcode", None),
        }, sort_keys=True))
        return 1
    finally:
        if connection is not None:
            connection.close()

    print(json.dumps({"result": "completed", **report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
