"""Data freshness monitoring service.

Checks each configured data source against staleness thresholds,
writes results to data_freshness_check, and alerts when data is stale.

Usage:
    python3 -m services.ingestion.data_freshness --check
    python3 -m services.ingestion.data_freshness --check --source weather
    python3 -m services.ingestion.data_freshness --summary
"""

from __future__ import annotations

import json
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger
from .base import get_db

logger = get_logger("ingestion.data_freshness")


def _query_freshness_configs(conn, source: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query active freshness configurations."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if source:
        cur.execute(
            "SELECT * FROM data_freshness_config WHERE is_active = TRUE AND source_system = %s",
            (source,),
        )
    else:
        cur.execute("SELECT * FROM data_freshness_config WHERE is_active = TRUE")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def _validate_thresholds(stale_threshold: int, critical_threshold: int) -> None:
    """Reject invalid SLA configuration before it can produce a misleading result."""
    if stale_threshold <= 0 or critical_threshold <= 0 or stale_threshold > critical_threshold:
        raise ValueError("freshness thresholds must be positive and stale <= critical")


def _location_ids(conn) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT id FROM location ORDER BY id")
    rows = [str(row[0]) for row in cur.fetchall()]
    cur.close()
    return rows


def _query_latest_data_at(
    conn, source_system: str, location_scoped: bool, location_id: Optional[str] = None
) -> Optional[datetime]:
    """Get the most recent data timestamp for a source system."""
    if location_scoped and not location_id:
        raise ValueError("location_id is required for a scoped freshness query")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    source_table_map = {
        "weather": "weather_observation",
        "sensors": "sensor_reading",
        "remote_sensing": "remote_sensing_observation",
        "market_data": "price_observation",
        "eas_indexer": "attestation_record",
        "rpc_indexer": "wallet_activity_event",
        "gnosis_indexer": "governance_event",
    }

    table = source_table_map.get(source_system)
    if not table:
        cur.close()
        return None

    # Determine the timestamp column
    ts_column_map = {
        "weather_observation": "observation_date",
        "sensor_reading": "created_at",
        "remote_sensing_observation": "observation_date",
        "price_observation": "observation_date",
        "attestation_record": "attested_at",
        "wallet_activity_event": "block_timestamp",
        "governance_event": "block_timestamp",
    }
    ts_col = ts_column_map.get(table, "created_at")

    query = f"SELECT MAX({ts_col}) AS last_at FROM {table}"
    params = []
    if location_scoped:
        if source_system == "sensors":
            query = (
                "SELECT MAX(sr.created_at) AS last_at FROM sensor_reading sr "
                "JOIN sensor_device sd ON sd.id = sr.sensor_id WHERE sd.location_id = %s"
            )
        else:
            query += " WHERE location_id = %s"
        params.append(location_id)
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        return row["last_at"] if row and row["last_at"] else None
    finally:
        cur.close()


def _query_latest_ingestion(conn, source_system: str) -> Optional[datetime]:
    """Get the most recent ingestion log entry for a source."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT MAX(created_at) AS last_at FROM ingestion_log WHERE source_system = %s AND status = 'success'",
        (source_system,),
    )
    row = cur.fetchone()
    cur.close()
    return row["last_at"] if row and row["last_at"] else None


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


def _alert_state(conn, source_system: str, location_id: Optional[str]) -> Dict[str, Any]:
    """Lock and return the alert state for one source/location scope."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM data_freshness_alert_state
        WHERE source_system = %s AND location_id IS NOT DISTINCT FROM %s
        FOR UPDATE
        """,
        (source_system, location_id),
    )
    state = cur.fetchone()
    cur.close()
    if state:
        return dict(state)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO data_freshness_alert_state (source_system, location_id, current_status)
        VALUES (%s, %s, 'no_data')
        ON CONFLICT DO NOTHING
        """,
        (source_system, location_id),
    )
    cur.close()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM data_freshness_alert_state
        WHERE source_system = %s AND location_id IS NOT DISTINCT FROM %s
        FOR UPDATE
        """,
        (source_system, location_id),
    )
    state = dict(cur.fetchone())
    cur.close()
    return state


def _persist_alert_event(
    conn,
    state: Dict[str, Any],
    check_id: str,
    source_system: str,
    location_id: Optional[str],
    event_type: str,
    previous_status: Optional[str],
    status: str,
    gap_minutes: Optional[int],
    now: datetime,
) -> str:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO data_freshness_alert_history
            (state_id, check_id, source_system, location_id, event_type,
             previous_status, status, gap_minutes, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (state["id"], check_id, source_system, location_id, event_type,
         previous_status, status, gap_minutes, now),
    )
    alert_id = str(cur.fetchone()[0])
    count_column = {
        "alert": "alert_count",
        "escalation": "escalation_count",
        "recovery": "recovery_count",
    }[event_type]
    cur.execute(
        f"""
        UPDATE data_freshness_alert_state
        SET current_status = %s, last_event_type = %s, last_event_status = %s,
            last_event_at = %s, {count_column} = {count_column} + 1, updated_at = %s
        WHERE id = %s
        """,
        (status, event_type, status, now, now, state["id"]),
    )
    cur.close()
    return alert_id


def _persist_delivery_attempt(
    conn, alert_id: str, channel: str, delivered: bool, error_message: Optional[str] = None
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO data_freshness_alert_delivery_attempt
            (alert_id, channel, outcome, error_message)
        VALUES (%s, %s, %s, %s)
        """,
        (alert_id, channel, "delivered" if delivered else "failed", error_message),
    )
    if delivered:
        cur.execute(
            "UPDATE data_freshness_alert_state SET last_delivered_at = NOW(), updated_at = NOW() "
            "WHERE id = (SELECT state_id FROM data_freshness_alert_history WHERE id = %s)",
            (alert_id,),
        )
    cur.close()


def _insert_check_result(
    conn,
    config_id: str,
    source_system: str,
    location_id: Optional[str],
    last_data_at: Optional[datetime],
    gap_minutes: Optional[int],
    status: str,
    alert_sent: bool = False,
    alert_channel: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Insert a freshness check result. Returns check ID."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO data_freshness_check
            (config_id, source_system, location_id, last_data_at,
             gap_minutes, status, alert_sent, alert_channel, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            config_id,
            source_system,
            location_id,
            last_data_at,
            gap_minutes,
            status,
            alert_sent,
            alert_channel,
            json.dumps(metadata or {}),
        ),
    )
    check_id = str(cur.fetchone()[0])
    cur.close()
    return check_id


def _send_alert(
    source_system: str,
    status: str,
    gap_minutes: Optional[int],
    last_data_at: Optional[datetime],
    location_id: Optional[str] = None,
    attempts: Optional[List[Dict[str, Optional[str]]]] = None,
) -> str:
    """Send freshness alert. Returns alert channel used."""
    import os

    alert_msg = (
        f"[CRISP] Data freshness alert: {source_system}"
        f" ({location_id or 'global'})\n"
        f"Status: {status}\n"
        f"Gap: {gap_minutes} minutes\n"
        f"Last data: {last_data_at}\n"
    )

    # Webhook alert
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    if webhook_url:
        try:
            import requests

            response = requests.post(
                webhook_url,
                json={"text": alert_msg, "source": source_system, "status": status},
                timeout=10,
            )
            response.raise_for_status()
            if attempts is not None:
                attempts.append({"channel": "webhook", "error": None})
            return "webhook"
        except Exception as e:
            logger.warning("Webhook alert failed: %s", e)
            if attempts is not None:
                attempts.append({"channel": "webhook", "error": str(e)})

    # Email alert
    smtp_host = os.environ.get("ALERT_SMTP_HOST")
    smtp_to = os.environ.get("ALERT_EMAIL_TO")
    if smtp_host and smtp_to:
        try:
            msg = MIMEText(alert_msg)
            msg["Subject"] = f"[Kokonut] Data freshness alert: {source_system}"
            msg["From"] = os.environ.get("ALERT_EMAIL_FROM", "alerts@kokonut.network")
            msg["To"] = smtp_to
            with smtplib.SMTP(smtp_host, int(os.environ.get("ALERT_SMTP_PORT", 587))) as server:
                server.send_message(msg)
            if attempts is not None:
                attempts.append({"channel": "email", "error": None})
            return "email"
        except Exception as e:
            logger.warning("Email alert failed: %s", e)
            if attempts is not None:
                attempts.append({"channel": "email", "error": str(e)})

    if attempts is not None and not attempts:
        attempts.append({"channel": "none", "error": "no alert channel configured"})
    return "none"


def check_freshness(conn, source: Optional[str] = None) -> Dict[str, Any]:
    """Check freshness for all configured sources (or a specific one).

    Returns:
        Dict with summary of check results.
    """
    configs = _query_freshness_configs(conn, source)
    results = []

    for config in configs:
        source_system = config["source_system"]
        stale_threshold = config["stale_threshold_minutes"]
        critical_threshold = config["critical_threshold_minutes"]
        scoped = bool(config["location_scoped"])
        scope_ids = _location_ids(conn) if scoped else [None]
        for location_id in scope_ids:
            last_data_at = None
            gap_minutes = None
            metadata = {}
            now = datetime.now(timezone.utc)
            savepoint = "freshness_scope"
            save_cur = conn.cursor()
            save_cur.execute(f"SAVEPOINT {savepoint}")
            save_cur.close()
            try:
                _validate_thresholds(stale_threshold, critical_threshold)
                last_data_at = _query_latest_data_at(conn, source_system, scoped, location_id)
                if last_data_at:
                    if last_data_at.tzinfo is None:
                        last_data_at = last_data_at.replace(tzinfo=timezone.utc)
                    gap_minutes = max(0, int((now - last_data_at).total_seconds() / 60))
                status = _determine_status(gap_minutes, stale_threshold, critical_threshold)
            except Exception as exc:
                rollback_cur = conn.cursor()
                rollback_cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                rollback_cur.close()
                status = "error"
                metadata = {"error": str(exc)}
                logger.error("Freshness query failed for %s/%s: %s", source_system, location_id, exc)

            alert_sent = False
            alert_channel = None
            try:
                check_id = _insert_check_result(
                    conn,
                    str(config["id"]),
                    source_system,
                    location_id,
                    last_data_at,
                    gap_minutes,
                    status,
                    alert_sent,
                    alert_channel,
                    metadata,
                )
                state = _alert_state(conn, source_system, location_id)
                previous_status = state["current_status"]
                last_event_at = state.get("last_event_at")
                if last_event_at and last_event_at.tzinfo is None:
                    last_event_at = last_event_at.replace(tzinfo=timezone.utc)
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
                    alert_id = _persist_alert_event(
                        conn,
                        state,
                        check_id,
                        source_system,
                        location_id,
                        event_type,
                        previous_status,
                        status,
                        gap_minutes,
                        now,
                    )
                    delivery_attempts: List[Dict[str, Optional[str]]] = []
                    alert_channel = _send_alert(
                        source_system,
                        status,
                        gap_minutes,
                        last_data_at,
                        location_id,
                        delivery_attempts,
                    )
                    alert_sent = alert_channel != "none"
                    for attempt in delivery_attempts:
                        _persist_delivery_attempt(
                            conn,
                            alert_id,
                            attempt["channel"] or "none",
                            attempt["error"] is None,
                            attempt["error"],
                        )
                else:
                    update_cur = conn.cursor()
                    update_cur.execute(
                        "UPDATE data_freshness_alert_state SET current_status = %s, updated_at = %s WHERE id = %s",
                        (status, now, state["id"]),
                    )
                    update_cur.close()
                update_check_cur = conn.cursor()
                update_check_cur.execute(
                    "UPDATE data_freshness_check SET alert_sent = %s, alert_channel = %s WHERE id = %s",
                    (alert_sent, alert_channel, check_id),
                )
                update_check_cur.close()
                release_cur = conn.cursor()
                release_cur.execute(f"RELEASE SAVEPOINT {savepoint}")
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
                "  %s/%s: %s (gap=%s min, alert=%s)", source_system, location_id, status, gap_minutes, alert_sent
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
    cur.execute("SELECT * FROM v_data_freshness_summary")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Data freshness monitoring")
    parser.add_argument("--check", action="store_true", help="Run freshness check")
    parser.add_argument("--summary", action="store_true", help="Show freshness summary")
    parser.add_argument("--source", help="Limit to specific source")
    args = parser.parse_args()

    conn = get_db()
    try:
        if args.check:
            result = check_freshness(conn, source=args.source)
            print(json.dumps(result, indent=2, default=str))
        elif args.summary:
            result = get_freshness_summary(conn)
            print(json.dumps(result, indent=2, default=str))
        else:
            parser.print_help()
    finally:
        conn.close()
