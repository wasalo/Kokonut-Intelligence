"""Isolated ClickHouse projection delivery through bounded PostgreSQL functions."""

from __future__ import annotations

import argparse
import re
from typing import Any

import psycopg2.extras

from services.common.cli import print_json
from services.common.worker_database import get_worker_db
from services.core.features import require_feature
from services.core.providers import ProviderSettings
from services.ingestion.clickhouse_outbox import deliver_claimed_batch


def _claim(connection, worker_id: str, limit: int) -> list[dict[str, Any]]:
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM kokonut_security.claim_clickhouse_outbox_batch(%s, %s)",
                (worker_id, limit),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        connection.commit()
        return rows
    except Exception:
        connection.rollback()
        raise


def _finish(connection, worker_id: str, row: dict[str, Any], **kwargs: Any) -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.finish_clickhouse_outbox_delivery(
                       %s, %s, %s, %s, %s, %s, %s
                   )""",
                (
                    row["id"], worker_id, row["lease_token"],
                    kwargs["success"], kwargs.get("error"),
                    kwargs.get("retry_delay_seconds", 60),
                    kwargs.get("permanent_failure", False),
                ),
            )
            result = cursor.fetchone()
        if result is None:
            raise RuntimeError("ClickHouse outbox completion returned no result")
        connection.commit()
        return bool(result[0])
    except Exception:
        connection.rollback()
        raise


def run_once(worker_id: str = "clickhouse-outbox-worker", limit: int = 100) -> dict[str, int]:
    """Deliver a bounded batch with its dedicated login, if the sink is enabled."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("ClickHouse outbox batch limit must be between 1 and 100")
    if not isinstance(worker_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}", worker_id
    ):
        raise ValueError("ClickHouse outbox worker ID has an invalid format")
    require_feature("isolated_clickhouse_outbox_worker")
    if not ProviderSettings.from_environment().clickhouse:
        return {"claimed": 0, "delivered": 0, "failed": 0}

    connection = get_worker_db("clickhouse_outbox")
    try:
        rows = _claim(connection, worker_id, limit)
        return deliver_claimed_batch(
            rows,
            worker_id,
            lambda row, **kwargs: _finish(connection, worker_id, row, **kwargs),
        )
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Isolated ClickHouse outbox delivery worker")
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--worker-id", default="clickhouse-outbox-worker")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    result = run_once(args.worker_id, args.limit)
    print_json(result)
    if result.get("failed", 0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
