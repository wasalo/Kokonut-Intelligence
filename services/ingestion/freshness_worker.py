"""Isolated scheduled data-freshness worker.

The global sweep reads only bounded timestamps and persists check/alert state
through migration 645 functions. It intentionally has no farm tenant context:
some monitored sources are global control-plane sources.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

import psycopg2.extras

from services.common.cli import print_json
from services.common.worker_database import get_worker_db
from services.core.features import require_feature
from services.ingestion.data_freshness import check_freshness


class FreshnessPersistence:
    """Implement the data-freshness repository contract with bounded SQL."""

    def __init__(self, connection):
        self.connection = connection

    def _rows(self, statement: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(statement, parameters)
            return [dict(row) for row in cursor.fetchall()]

    def _one(self, statement: str, parameters: tuple[Any, ...] = ()) -> Any:
        with self.connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("freshness database function returned no result")
        return row[0]

    def list_configs(self, source: str | None) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM kokonut_security.list_freshness_configs(%s)", (source,)
        )

    def list_location_ids(self) -> list[str]:
        return [
            str(row["location_id"])
            for row in self._rows("SELECT * FROM kokonut_security.list_freshness_locations()")
        ]

    def latest_data_at(
        self, source: str, location_scoped: bool, location_id: str | None
    ) -> datetime | None:
        return self._one(
            "SELECT kokonut_security.read_freshness_data_at(%s, %s, %s)",
            (source, location_scoped, location_id),
        )

    def insert_check(
        self,
        config_id: str,
        source: str,
        location_id: str | None,
        last_data_at: datetime | None,
        gap_minutes: int | None,
        status: str,
        alert_sent: bool,
        alert_channel: str | None,
        metadata: dict[str, Any],
    ) -> str:
        return str(self._one(
            "SELECT kokonut_security.create_freshness_check(%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (
                config_id, source, location_id, last_data_at, gap_minutes, status,
                alert_sent, alert_channel, json.dumps(metadata or {}),
            ),
        ))

    def lock_alert_state(self, source: str, location_id: str | None) -> dict[str, Any]:
        rows = self._rows(
            "SELECT * FROM kokonut_security.get_freshness_alert_state(%s, %s)",
            (source, location_id),
        )
        if not rows:
            raise RuntimeError("freshness alert-state function returned no state")
        return rows[0]

    def persist_alert_event(
        self,
        state: dict[str, Any],
        check_id: str,
        source: str,
        location_id: str | None,
        event_type: str,
        previous_status: str | None,
        status: str,
        gap_minutes: int | None,
        happened_at: datetime,
    ) -> str:
        return str(self._one(
            "SELECT kokonut_security.record_freshness_alert_event(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                state["id"], check_id, source, location_id, event_type,
                previous_status, status, gap_minutes, happened_at,
            ),
        ))

    def enqueue_alert_event(
        self,
        alert_id: str,
        source: str,
        status: str,
        gap_minutes: int | None,
        last_data_at: datetime | None,
        event_type: str,
        location_id: str | None,
    ) -> str:
        last_data_value = last_data_at.isoformat() if last_data_at else None
        location_label = location_id or "global"
        message = (
            f"[CRISP] Data freshness {event_type}: {source} ({location_label})\n"
            f"Status: {status}\n"
            f"Gap: {gap_minutes} minutes\n"
            f"Last data: {last_data_value or 'none'}\n"
        )
        payload = {
            "alert_id": alert_id,
            "event_type": event_type,
            "source_system": source,
            "status": status,
            "severity": "info" if event_type == "recovery" else (
                "critical" if status == "critical" else "warning"
            ),
            "gap_minutes": gap_minutes,
            "last_data_at": last_data_value,
            "location_id": location_id,
            "message": message,
        }
        return str(self._one(
            "SELECT kokonut_security.enqueue_freshness_event(%s, %s::jsonb, %s)",
            (alert_id, json.dumps(payload), "high" if status == "critical" else "normal"),
        ))

    def update_alert_state(self, state_id: str, status: str, happened_at: datetime) -> None:
        self._one(
            "SELECT kokonut_security.update_freshness_alert_state(%s, %s, %s)",
            (state_id, status, happened_at),
        )

    def update_check_alert(
        self, check_id: str, alert_sent: bool, alert_channel: str | None
    ) -> None:
        self._one(
            "SELECT kokonut_security.update_freshness_check_alert(%s, %s, %s)",
            (check_id, alert_sent, alert_channel),
        )


def run(source: str | None = None) -> dict[str, Any]:
    """Run an isolated sweep and always close its dedicated connection."""
    require_feature("isolated_freshness_worker")
    connection = get_worker_db("freshness")
    try:
        return check_freshness(connection, source=source, persistence=FreshnessPersistence(connection))
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Isolated data freshness worker")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true", help="Run a bounded freshness sweep")
    parser.add_argument("--source", help="Limit to one configured source")
    args = parser.parse_args(argv)
    print_json(run(source=args.source))


if __name__ == "__main__":
    main()
