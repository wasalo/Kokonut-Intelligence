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


def _query_latest_data_at(conn, source_system: str, location_scoped: bool) -> Optional[datetime]:
    """Get the most recent data timestamp for a source system."""
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

    try:
        cur.execute(f"SELECT MAX({ts_col}) AS last_at FROM {table}")
        row = cur.fetchone()
        return row["last_at"] if row and row["last_at"] else None
    except Exception:
        return None
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
) -> str:
    """Insert a freshness check result. Returns check ID."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO data_freshness_check
            (config_id, source_system, location_id, last_data_at,
             gap_minutes, status, alert_sent, alert_channel)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (config_id, source_system, location_id, last_data_at,
         gap_minutes, status, alert_sent, alert_channel),
    )
    check_id = str(cur.fetchone()[0])
    cur.close()
    return check_id


def _send_alert(
    source_system: str,
    status: str,
    gap_minutes: Optional[int],
    last_data_at: Optional[datetime],
) -> str:
    """Send freshness alert. Returns alert channel used."""
    import os

    alert_msg = (
        f"[CRISP] Data freshness alert: {source_system}\n"
        f"Status: {status}\n"
        f"Gap: {gap_minutes} minutes\n"
        f"Last data: {last_data_at}\n"
    )

    # Webhook alert
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    if webhook_url:
        try:
            import requests
            requests.post(
                webhook_url,
                json={"text": alert_msg, "source": source_system, "status": status},
                timeout=10,
            )
            return "webhook"
        except Exception as e:
            logger.warning("Webhook alert failed: %s", e)

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
            return "email"
        except Exception as e:
            logger.warning("Email alert failed: %s", e)

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

        last_data_at = _query_latest_data_at(conn, source_system, config["location_scoped"])
        if not last_data_at:
            last_data_at = _query_latest_ingestion(conn, source_system)

        now = datetime.now(timezone.utc)
        gap_minutes = None
        if last_data_at:
            if last_data_at.tzinfo is None:
                last_data_at = last_data_at.replace(tzinfo=timezone.utc)
            gap_minutes = int((now - last_data_at).total_seconds() / 60)

        status = _determine_status(gap_minutes, stale_threshold, critical_threshold)

        alert_sent = False
        alert_channel = None
        if status in ("stale", "critical"):
            alert_channel = _send_alert(source_system, status, gap_minutes, last_data_at)
            alert_sent = alert_channel != "none"

        check_id = _insert_check_result(
            conn,
            str(config["id"]),
            source_system,
            None,
            last_data_at,
            gap_minutes,
            status,
            alert_sent,
            alert_channel,
        )

        results.append({
            "source_system": source_system,
            "status": status,
            "gap_minutes": gap_minutes,
            "last_data_at": str(last_data_at) if last_data_at else None,
            "alert_sent": alert_sent,
            "alert_channel": alert_channel,
            "check_id": check_id,
        })

        logger.info(
            "  %s: %s (gap=%s min, alert=%s)",
            source_system, status, gap_minutes, alert_sent,
        )

    conn.commit()

    summary = {
        "checked": len(results),
        "fresh": sum(1 for r in results if r["status"] == "fresh"),
        "stale": sum(1 for r in results if r["status"] == "stale"),
        "critical": sum(1 for r in results if r["status"] == "critical"),
        "no_data": sum(1 for r in results if r["status"] == "no_data"),
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
