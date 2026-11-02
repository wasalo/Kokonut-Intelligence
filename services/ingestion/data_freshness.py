"""Data freshness monitoring service.

Checks each configured data source against staleness thresholds through the
isolated freshness worker, which persists checks and durable alerts.

Usage:
    python3 -m services.ingestion.data_freshness --check
    python3 -m services.ingestion.data_freshness --check --source weather
    python3 -m services.ingestion.data_freshness --summary
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras

from services.common.cli import print_json

from ..common.logging import get_logger

logger = get_logger("ingestion.data_freshness")


def _validate_thresholds(stale_threshold: int, critical_threshold: int) -> None:
    """Reject invalid SLA configuration before it can produce a misleading result."""
    if stale_threshold <= 0 or critical_threshold <= 0 or stale_threshold > critical_threshold:
        raise ValueError("freshness thresholds must be positive and stale <= critical")


def _determine_status(
    gap_minutes: Optional[int],
    stale_threshold: int,
    critical_threshold: int,
) -> str:
    """Determine freshness status from gap duration."""
    if gap_minutes is None:
        return "no_data"
    if gap_minutes <= stale_threshold:
        return "fresh"
    if gap_minutes <= critical_threshold:
        return "stale"
    return "critical"


def _alert_event(
    previous_status: Optional[str],
    status: str,
    last_event_status: Optional[str],
    last_event_at: Optional[datetime],
    now: datetime,
    cooldown_minutes: int,
    escalation_cooldown_minutes: int,
) -> Optional[str]:
    """Return the durable alert event to emit for a status transition."""
    alert_statuses = {"stale", "critical"}
    if status == "fresh" and previous_status in alert_statuses:
        return "recovery"
    if status not in alert_statuses:
        return None
    if previous_status not in alert_statuses:
        return "alert"
    if status == "critical" and previous_status == "stale":
        return "escalation"
    if last_event_status != status or last_event_at is None:
        return "alert"
    elapsed = (now - last_event_at).total_seconds() / 60
    cooldown = escalation_cooldown_minutes if status == "critical" else cooldown_minutes
    return "alert" if elapsed >= cooldown else None


def _safe_evaluation_error(exc: Exception) -> str:
    """Summarize freshness read/evaluation failures without exception details."""
    return f"freshness evaluation failed ({type(exc).__name__})"


def check_freshness(
    conn, source: Optional[str] = None, *, persistence=None
) -> Dict[str, Any]:
    """Evaluate freshness only through the bounded worker persistence contract.

    A persistence adapter is mandatory so this shared domain logic cannot fall
    back to direct table writes under the application/runtime database login.
    """
    if persistence is None:
        raise RuntimeError("freshness checks require the isolated persistence adapter")

    configs = persistence.list_configs(source)
    results = []

    for config in configs:
        source_system = config["source_system"]
        stale_threshold = config["stale_threshold_minutes"]
        critical_threshold = config["critical_threshold_minutes"]
        scoped = bool(config["location_scoped"])
        if scoped:
            scope_ids = persistence.list_location_ids()
        else:
            scope_ids = [None]
        for location_id in scope_ids:
            last_data_at = None
            gap_minutes = None
            metadata = {}
            now = datetime.now(timezone.utc)
            savepoint = "freshness_scope"
            save_cur = conn.cursor()
            try:
                save_cur.execute(f"SAVEPOINT {savepoint}")
            finally:
                save_cur.close()
            try:
                _validate_thresholds(stale_threshold, critical_threshold)
                last_data_at = persistence.latest_data_at(source_system, scoped, location_id)
                if last_data_at:
                    if last_data_at.tzinfo is None:
                        last_data_at = last_data_at.replace(tzinfo=timezone.utc)
                    gap_minutes = max(0, int((now - last_data_at).total_seconds() / 60))
                status = _determine_status(gap_minutes, stale_threshold, critical_threshold)
            except Exception as exc:
                rollback_cur = conn.cursor()
                try:
                    rollback_cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                finally:
                    rollback_cur.close()
                status = "error"
                metadata = {"error": _safe_evaluation_error(exc)}
                logger.error(
                    "Freshness evaluation failed for %s/%s (%s)",
                    source_system,
                    location_id,
                    type(exc).__name__,
                )

            alert_sent = False
            alert_channel = None
            try:
                check_id = persistence.insert_check(
                    str(config["id"]), source_system, location_id, last_data_at,
                    gap_minutes, status, alert_sent, alert_channel, metadata,
                )
                state = persistence.lock_alert_state(source_system, location_id)
                previous_status = state["current_status"]
                last_event_at = state.get("last_event_at")
                if last_event_at and last_event_at.tzinfo is None:
                    last_event_at = last_event_at.replace(tzinfo=timezone.utc)
                event_type = None
                if status != "error":
                    event_type = _alert_event(
                        previous_status,
                        status,
                        state.get("last_event_status"),
                        last_event_at,
                        now,
                        int(config.get("alert_cooldown_minutes", 60)),
                        int(config.get("escalation_cooldown_minutes", 15)),
                    )
                alert_sent = False
                alert_channel = None
                if event_type:
                    alert_id = persistence.persist_alert_event(
                        state, check_id, source_system, location_id, event_type,
                        previous_status, status, gap_minutes, now,
                    )
                    persistence.enqueue_alert_event(
                        alert_id, source_system, status, gap_minutes,
                        last_data_at, event_type, location_id,
                    )
                    # The durable event is committed here; provider delivery is
                    # asynchronous and is tracked by notification_outbox.
                    alert_channel = "event_bus"
                elif status != "error":
                    persistence.update_alert_state(state["id"], status, now)
                persistence.update_check_alert(check_id, alert_sent, alert_channel)
                release_cur = conn.cursor()
                try:
                    release_cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                finally:
                    release_cur.close()
            except Exception:
                conn.rollback()
                raise
            results.append(
                {
                    "source_system": source_system,
                    "location_id": location_id,
                    "status": status,
                    "gap_minutes": gap_minutes,
                    "last_data_at": str(last_data_at) if last_data_at else None,
                    "alert_sent": alert_sent,
                    "alert_channel": alert_channel,
                    "check_id": check_id,
                    "error": metadata.get("error"),
                }
            )
            logger.info(
                "  %s/%s: %s (gap=%s min, alert_sent=%s, dispatch=%s)",
                source_system,
                location_id,
                status,
                gap_minutes,
                alert_sent,
                alert_channel or "none",
            )

    try:
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    summary = {
        "checked": len(results),
        "fresh": sum(1 for r in results if r["status"] == "fresh"),
        "stale": sum(1 for r in results if r["status"] == "stale"),
        "critical": sum(1 for r in results if r["status"] == "critical"),
        "no_data": sum(1 for r in results if r["status"] == "no_data"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
    return summary


def get_freshness_summary(conn) -> List[Dict[str, Any]]:
    """Get current freshness summary from the database view."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT source_system, description, expected_interval_minutes,
                      stale_threshold_minutes, critical_threshold_minutes, is_active,
                      latest_data_at, current_status, current_gap_minutes,
                      critical_alerts_24h
                 FROM v_data_freshness_summary
                ORDER BY source_system"""
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Data freshness monitoring")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="Run freshness check")
    action.add_argument("--summary", action="store_true", help="Show freshness summary")
    parser.add_argument("--source", help="Limit to specific source")
    args = parser.parse_args(argv)

    if args.source and not args.check:
        parser.error("--source requires --check")
    if not args.check and not args.summary:
        parser.print_help()
        return

    if args.check:
        from services.ingestion.freshness_worker import run

        print_json(run(source=args.source))
    elif args.summary:
        conn = get_db()
        try:
            result = get_freshness_summary(conn)
            print_json(result)
        finally:
            conn.close()


def get_db():
    """Load the ingestion database connection only when a DB action is run."""
    from .base import get_db as _get_db

    return _get_db()


if __name__ == "__main__":
    main()
