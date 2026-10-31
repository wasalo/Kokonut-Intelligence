"""Explicit operator maintenance for shared gateway throttle state."""

from __future__ import annotations

import argparse
import os
from typing import TYPE_CHECKING

import psycopg2
from psycopg2.extensions import parse_dsn

from services.common.cli import print_json, run

if TYPE_CHECKING:
    from services.common.database import DatabaseConnection

_MAINTENANCE_DSN_ENV = "KOKONUT_RATE_LIMIT_MAINTENANCE_DSN"
_MAINTENANCE_USER_ENV = "KOKONUT_RATE_LIMIT_MAINTENANCE_USER"
_DEFAULT_MAINTENANCE_USER = "kokonut_rate_limit_maintenance_login"


def _maintenance_connection() -> DatabaseConnection:
    """Open the one-shot cleanup connection as its dedicated login.

    This command must not fall back to the API runtime or database-owner
    credentials. The returned wrapper owns commit/rollback and connection
    cleanup using the shared database lifecycle.
    """
    dsn = os.environ.get(_MAINTENANCE_DSN_ENV, "").strip()
    if not dsn:
        raise RuntimeError(f"{_MAINTENANCE_DSN_ENV} is required for rate-limit cleanup")

    expected_user = os.environ.get(_MAINTENANCE_USER_ENV, _DEFAULT_MAINTENANCE_USER)
    if expected_user != _DEFAULT_MAINTENANCE_USER:
        raise RuntimeError(
            f"{_MAINTENANCE_USER_ENV} must be {_DEFAULT_MAINTENANCE_USER}"
        )
    try:
        parameters = parse_dsn(dsn)
    except Exception as exc:
        raise ValueError(f"{_MAINTENANCE_DSN_ENV} is invalid") from exc
    if parameters.get("user") != expected_user:
        raise RuntimeError(
            f"{_MAINTENANCE_DSN_ENV} must use the configured dedicated maintenance login"
        )

    try:
        connection = psycopg2.connect(dsn, connect_timeout=3)
    except Exception as exc:
        # Connection diagnostics can include DSN components; expose only the
        # exception class through the CLI error boundary.
        raise RuntimeError(
            f"rate-limit maintenance database unavailable ({type(exc).__name__})"
        ) from exc
    try:
        # Import lazily so help/offline paths do not load application DB
        # environment before the dedicated DSN has been validated.
        from services.common.database import DatabaseConnection

        return DatabaseConnection(connection=connection)
    except Exception:
        connection.close()
        raise


def cleanup_idle_buckets(limit: int = 1000) -> dict[str, int]:
    """Delete a bounded page idle over 24 hours, skipping in-use row locks.

    An idle bucket is already fully refilled under the fixed 100/10 policy.
    This command never resets a recently active caller's budget.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Limit must be an integer between 1 and 1000")
    with _maintenance_connection() as conn:
        conn.execute("SET LOCAL lock_timeout = '2s'")
        conn.execute("SET LOCAL statement_timeout = '3s'")
        row = conn.execute(
            """SELECT kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(:limit)
                      AS deleted""",
            {"limit": limit},
        ).first()
    deleted = row.get("deleted") if row else None
    if isinstance(deleted, bool) or not isinstance(deleted, int) or not 0 <= deleted <= limit:
        raise RuntimeError("rate-limit cleanup returned an invalid row count")
    return {"deleted": deleted, "limit": limit, "idle_hours": 24}


def command(args):
    print_json(cleanup_idle_buckets(args.limit))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", action="store_true", required=True,
                        help="Delete one bounded page of buckets idle for more than 24 hours")
    parser.add_argument("--limit", type=int, default=1000)
    run(command, parser.parse_args())


if __name__ == "__main__":
    main()
