#!/usr/bin/env python3
"""
Anomaly Detector — Sensor Alert Engine

Compares sensor readings against alert rules and environmental baselines.
Triggers sensor_alert records and optionally creates mrv_claim records.
Sends email and Directus real-time notifications for triggered alerts.

Usage:
    # Check all recent readings for anomalies
    python3 -m services.ingestion.anomaly_detector

    # Check readings for a specific sensor
    python3 -m services.ingestion.anomaly_detector --sensor <uuid>

    # Check readings since a specific time
    python3 -m services.ingestion.anomaly_detector --since "2026-06-11 00:00:00"

    # Create alerts from baseline deviations
    python3 -m services.ingestion.anomaly_detector --baseline-check

    # List active alert rules
    python3 -m services.ingestion.anomaly_detector --list-rules
"""

import argparse
import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from ..common.logging import get_logger
from .base import get_db, log_ingestion, hash_payload

logger = get_logger("ingestion.anomaly")

# Email notification config
SMTP_HOST = os.environ.get("ALERT_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("ALERT_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("ALERT_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("ALERT_SMTP_PASSWORD", "")
ALERT_EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM", "alerts@kokonut.network")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")

# Directus real-time notification config
DIRECTUS_URL = os.environ.get("DIRECTUS_URL", "http://localhost:8055")
DIRECTUS_TOKEN = os.environ.get("DIRECTUS_ADMIN_TOKEN", "")

# Default alert rules if none configured in database
DEFAULT_ALERT_RULES = [
    {
        "name": "Soil Moisture Low",
        "sensor_type_name": "soil_moisture",
        "metric": "value",
        "operator": "lt",
        "threshold_value": 15.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
    {
        "name": "Soil Moisture Critical",
        "sensor_type_name": "soil_moisture",
        "metric": "value",
        "operator": "lt",
        "threshold_value": 8.0,
        "severity": "critical",
        "auto_create_claim": True,
        "claim_type": "sensor_anomaly",
    },
    {
        "name": "Soil Moisture High",
        "sensor_type_name": "soil_moisture",
        "metric": "value",
        "operator": "gt",
        "threshold_value": 85.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
    {
        "name": "Air Temperature High",
        "sensor_type_name": "air_temperature",
        "metric": "value",
        "operator": "gt",
        "threshold_value": 40.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
    {
        "name": "Air Temperature Critical High",
        "sensor_type_name": "air_temperature",
        "metric": "value",
        "operator": "gt",
        "threshold_value": 45.0,
        "severity": "critical",
        "auto_create_claim": True,
        "claim_type": "sensor_anomaly",
    },
    {
        "name": "Air Temperature Low",
        "sensor_type_name": "air_temperature",
        "metric": "value",
        "operator": "lt",
        "threshold_value": 5.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
    {
        "name": "Humidity High",
        "sensor_type_name": "humidity",
        "metric": "value",
        "operator": "gt",
        "threshold_value": 90.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
    {
        "name": "Rainfall Heavy",
        "sensor_type_name": "rainfall",
        "metric": "value",
        "operator": "gt",
        "threshold_value": 50.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
    {
        "name": "Soil Moisture Rapid Drop",
        "sensor_type_name": "soil_moisture",
        "metric": "rate_of_change",
        "operator": "lt",
        "threshold_value": -5.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
    {
        "name": "Temperature Rapid Rise",
        "sensor_type_name": "air_temperature",
        "metric": "rate_of_change",
        "operator": "gt",
        "threshold_value": 10.0,
        "severity": "warning",
        "auto_create_claim": False,
    },
]


def ensure_alert_rules(db):
    """Ensure default alert rules exist in the database."""
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM alert_rule")
        count = cur.fetchone()[0]

        if count > 0:
            return

        type_ids = {}
        cur.execute("SELECT id, name FROM sensor_type")
        for row in cur.fetchall():
            type_ids[row[1]] = str(row[0])

        inserted = 0
        for rule in DEFAULT_ALERT_RULES:
            st_id = type_ids.get(rule["sensor_type_name"])
            if not st_id:
                continue

            cur.execute(
                """
                INSERT INTO alert_rule
                    (name, sensor_type_id, metric, operator, threshold_value,
                     severity, enabled, auto_create_claim, claim_type)
                VALUES (%s, %s, %s, %s, %s, %s, true, %s, %s)
                """,
                (
                    rule["name"], st_id, rule["metric"], rule["operator"],
                    rule["threshold_value"], rule["severity"],
                    rule.get("auto_create_claim", False),
                    rule.get("claim_type"),
                ),
            )
            inserted += 1
        logger.info("Created %d default alert rules", inserted)


def evaluate_rule(value: float, operator: str, threshold: float, threshold_max: float = None) -> bool:
    """Evaluate a reading value against an alert rule operator. Returns True if alert should fire."""
    ops = {
        "gt": lambda v, t: v > t,
        "lt": lambda v, t: v < t,
        "gte": lambda v, t: v >= t,
        "lte": lambda v, t: v <= t,
        "eq": lambda v, t: abs(v - t) < 0.001,
        "neq": lambda v, t: abs(v - t) >= 0.001,
    }

    if operator == "outside_range" and threshold_max is not None:
        return value < threshold or value > threshold_max

    op_func = ops.get(operator)
    if op_func:
        return op_func(value, threshold)
    return False


def compute_rate_of_change(db, sensor_id: str, sensor_type: str, current_value: float,
                           lookback_hours: int = 24) -> Optional[float]:
    """Compute rate of change (value per hour) for a sensor over the lookback window.

    Returns the change rate, or None if insufficient history.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT value, reading_date, reading_time
            FROM sensor_reading
            WHERE sensor_id = %s AND sensor_type = %s
              AND created_at >= NOW() - INTERVAL '%s hours'
            ORDER BY created_at ASC
            LIMIT 2
            """,
            (str(sensor_id), sensor_type, lookback_hours),
        )
        rows = cur.fetchall()

    if len(rows) < 2:
        return None

    old_value = float(rows[0][0])
    new_value = float(rows[-1][0])

    old_date = rows[0][1]
    old_time = rows[0][2]
    new_date = rows[-1][1]
    new_time = rows[-1][2]

    if old_date and new_date:
        try:
            old_dt = datetime.combine(old_date, old_time or datetime.min.time())
            new_dt = datetime.combine(new_date, new_time or datetime.min.time())
            delta_hours = (new_dt - old_dt).total_seconds() / 3600.0
            if delta_hours > 0:
                return (new_value - old_value) / delta_hours
        except Exception:
            pass

    return None


def compute_gap_hours(db, sensor_id: str, sensor_type: str) -> Optional[float]:
    """Compute hours since the last reading for a sensor.

    Returns gap in hours, or None if no readings exist.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT created_at FROM sensor_reading
            WHERE sensor_id = %s AND sensor_type = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (str(sensor_id), sensor_type),
        )
        row = cur.fetchone()

    if not row:
        return None

    last_reading = row[0]
    if last_reading.tzinfo is None:
        last_reading = last_reading.replace(tzinfo=timezone.utc)

    return (datetime.now(timezone.utc) - last_reading).total_seconds() / 3600.0


def compute_window_stats(db, sensor_id: str, sensor_type: str, window_hours: int = 24) -> Optional[dict]:
    """Compute min, max, avg over a time window for a sensor.

    Returns dict with min_value, max_value, avg_value, count, or None.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT MIN(value), MAX(value), AVG(value), COUNT(*)
            FROM sensor_reading
            WHERE sensor_id = %s AND sensor_type = %s
              AND created_at >= NOW() - INTERVAL '%s hours'
            """,
            (str(sensor_id), sensor_type, window_hours),
        )
        row = cur.fetchone()

    if not row or row[3] == 0:
        return None

    return {
        "min_value": float(row[0]),
        "max_value": float(row[1]),
        "avg_value": float(row[2]),
        "count": row[3],
    }


def evaluate_metric(metric: str, value: float, rule: dict, db, sensor_id: str,
                    sensor_type: str) -> bool:
    """Evaluate a specific metric type against a rule. Returns True if alert should fire."""
    if metric == "value":
        return evaluate_rule(value, rule["operator"], rule["threshold_value"], rule.get("threshold_value_max"))

    elif metric == "rate_of_change":
        rate = compute_rate_of_change(db, sensor_id, sensor_type)
        if rate is None:
            return False
        return evaluate_rule(rate, rule["operator"], rule["threshold_value"], rule.get("threshold_value_max"))

    elif metric == "gap":
        gap_hours = compute_gap_hours(db, sensor_id, sensor_type)
        if gap_hours is None:
            return False
        return evaluate_rule(gap_hours, rule["operator"], rule["threshold_value"], rule.get("threshold_value_max"))

    elif metric == "min":
        stats = compute_window_stats(db, sensor_id, sensor_type)
        if stats is None:
            return False
        return evaluate_rule(stats["min_value"], rule["operator"], rule["threshold_value"], rule.get("threshold_value_max"))

    elif metric == "max":
        stats = compute_window_stats(db, sensor_id, sensor_type)
        if stats is None:
            return False
        return evaluate_rule(stats["max_value"], rule["operator"], rule["threshold_value"], rule.get("threshold_value_max"))

    return False


def check_cooldown(db, alert_rule_id: str, sensor_device_id: str, cooldown_minutes: int) -> bool:
    """Check if alert is in cooldown period. Returns True if still cooling down."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT triggered_at FROM sensor_alert
            WHERE alert_rule_id = %s AND sensor_device_id = %s
            ORDER BY triggered_at DESC LIMIT 1
            """,
            (alert_rule_id, sensor_device_id),
        )
        row = cur.fetchone()
        if not row:
            return False

        last_triggered = row[0]
        if last_triggered.tzinfo is None:
            last_triggered = last_triggered.replace(tzinfo=timezone.utc)

        elapsed = datetime.now(timezone.utc) - last_triggered
        return elapsed.total_seconds() < cooldown_minutes * 60


def create_alert(db, sensor_device_id: str, alert_rule_id: str, reading_id: str,
                 severity: str, message: str, reading_value: float, threshold_value: float,
                 auto_create_claim: bool = False, claim_type: str = None) -> str:
    """Create a sensor alert record. Returns alert ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sensor_alert
                (sensor_device_id, alert_rule_id, reading_id, severity, status,
                 message, reading_value, threshold_value, triggered_at)
            VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, NOW())
            RETURNING id
            """,
            (sensor_device_id, alert_rule_id, reading_id, severity,
             message, reading_value, threshold_value),
        )
        alert_id = str(cur.fetchone()[0])

        if auto_create_claim and claim_type:
            cur.execute(
                """
                INSERT INTO mrv_claim
                    (location_id, claim_type, claim_data, status, sensor_device_id, sensor_alert_id)
                SELECT sd.location_id, %s, %s, 'draft', %s, %s
                FROM sensor_device sd WHERE sd.id = %s
                RETURNING id
                """,
                (
                    claim_type,
                    json.dumps({
                        "sensor_device_id": str(sensor_device_id),
                        "alert_id": alert_id,
                        "reading_value": reading_value,
                        "threshold_value": threshold_value,
                        "severity": severity,
                    }),
                    sensor_device_id, alert_id, sensor_device_id,
                ),
            )
            claim_row = cur.fetchone()
            if claim_row:
                claim_id = str(claim_row[0])
                cur.execute(
                    "UPDATE sensor_alert SET claim_id = %s WHERE id = %s",
                    (claim_id, alert_id),
                )
                logger.info("Auto-created MRV claim: %s", claim_id)

        return alert_id


def send_email_notification(alert_data: dict) -> bool:
    """Send email notification for a sensor alert.

    Returns True if sent successfully, False otherwise.
    """
    if not SMTP_HOST or not ALERT_EMAIL_TO:
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = ALERT_EMAIL_FROM
        msg["To"] = ALERT_EMAIL_TO
        msg["Subject"] = f"[{alert_data['severity'].upper()}] Sensor Alert: {alert_data['sensor_name']}"

        body = f"""
Sensor Alert Triggered

Severity: {alert_data['severity'].upper()}
Sensor: {alert_data['sensor_name']} ({alert_data['sensor_type']})
Location: {alert_data.get('location_name', 'Unknown')}
Message: {alert_data['message']}

Reading Value: {alert_data['reading_value']}
Threshold: {alert_data['threshold_value']}
Time: {alert_data['triggered_at']}

Alert ID: {alert_data['alert_id']}
{f"Claim ID: {alert_data['claim_id']}" if alert_data.get('claim_id') else ""}

---
Kokonut Intelligence Alert System
"""
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            if SMTP_PORT != 25:
                server.starttls()
                server.ehlo()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("Email notification sent for alert %s", alert_data["alert_id"])
        return True

    except Exception as e:
        logger.warning("Failed to send email notification: %s", e)
        return False


def send_directus_notification(alert_data: dict) -> bool:
    """Send Directus real-time notification for a sensor alert.

    Creates a notification item in Directus that appears in the admin UI
    and can trigger webhooks/subscriptions.

    Returns True if sent successfully, False otherwise.
    """
    if not DIRECTUS_URL or not DIRECTUS_TOKEN:
        return False

    try:
        import requests
        notification_payload = {
            "subject": f"Sensor Alert: {alert_data['sensor_name']}",
            "message": alert_data["message"],
            "type": alert_data["severity"],
            "recipient": "role:00000000-0000-0000-0000-000000000006",  # Field Worker role
            "status": "unread",
        }

        resp = requests.post(
            f"{DIRECTUS_URL}/notifications",
            json=notification_payload,
            headers={"Authorization": f"Bearer {DIRECTUS_TOKEN}"},
            timeout=10,
        )
        resp.raise_for_status()

        logger.info("Directus notification sent for alert %s", alert_data["alert_id"])
        return True

    except Exception as e:
        logger.warning("Failed to send Directus notification: %s", e)
        return False


def send_notifications(alert_data: dict) -> None:
    """Send all configured notifications for a sensor alert."""
    send_email_notification(alert_data)
    send_directus_notification(alert_data)


def get_sensor_device_info(db, sensor_device_id: str) -> dict:
    """Get sensor device details for notification context."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT sd.name, st.name as sensor_type, l.name as location_name
            FROM sensor_device sd
            JOIN sensor_type st ON sd.sensor_type_id = st.id
            LEFT JOIN location l ON sd.location_id = l.id
            WHERE sd.id = %s
            """,
            (sensor_device_id,),
        )
        row = cur.fetchone()
        if row:
            return {
                "sensor_name": row[0],
                "sensor_type": row[1],
                "location_name": row[2] or "Unknown",
            }
    return {"sensor_name": "Unknown", "sensor_type": "unknown", "location_name": "Unknown"}


def run_check(sensor_id: str = None, since: str = None):
    """Check recent readings against alert rules."""
    db = get_db()
    try:
        ensure_alert_rules(db)

        rules = []
        with db.cursor() as cur:
            cur.execute("""
                SELECT ar.id, ar.name, ar.sensor_type_id, st.name as sensor_type,
                       ar.metric, ar.operator, ar.threshold_value, ar.threshold_value_max,
                       ar.severity, ar.cooldown_minutes, ar.auto_create_claim, ar.claim_type
                FROM alert_rule ar
                JOIN sensor_type st ON ar.sensor_type_id = st.id
                WHERE ar.enabled = true
            """)
            for row in cur.fetchall():
                rules.append({
                    "id": str(row[0]), "name": row[1], "sensor_type_id": str(row[2]),
                    "sensor_type": row[3], "metric": row[4], "operator": row[5],
                    "threshold_value": float(row[6]),
                    "threshold_value_max": float(row[7]) if row[7] else None,
                    "severity": row[8], "cooldown_minutes": row[9],
                    "auto_create_claim": row[10], "claim_type": row[11],
                })

        if not rules:
            logger.info("No alert rules configured.")
            return

        since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(hours=1)
        since_str = since_dt.strftime("%Y-%m-%d %H:%M:%S")

        with db.cursor() as cur:
            if sensor_id:
                cur.execute(
                    """
                    SELECT sr.id, sr.sensor_id, sr.sensor_type, sr.value, sr.reading_date,
                           sr.reading_time, sr.location_id, sr.plot_id
                    FROM sensor_reading sr
                    WHERE sr.sensor_id = %s AND sr.created_at >= %s
                    ORDER BY sr.created_at DESC
                    """,
                    (sensor_id, since_str),
                )
            else:
                cur.execute(
                    """
                    SELECT sr.id, sr.sensor_id, sr.sensor_type, sr.value, sr.reading_date,
                           sr.reading_time, sr.location_id, sr.plot_id
                    FROM sensor_reading sr
                    WHERE sr.created_at >= %s
                    ORDER BY sr.created_at DESC
                    """,
                    (since_str,),
                )
            readings = cur.fetchall()

        if not readings:
            logger.info("No readings since %s", since_str)
            return

        logger.info("Checking %d readings against %d rules...", len(readings), len(rules))

        alerts_triggered = 0
        sensor_device_cache = {}

        for reading in readings:
            reading_id = str(reading[0])
            sensor_id_val = reading[1]
            sensor_type = reading[2]
            value = float(reading[3])

            for rule in rules:
                if rule["sensor_type"] != sensor_type:
                    continue

                if sensor_id_val not in sensor_device_cache:
                    with db.cursor() as cur:
                        cur.execute("SELECT id FROM sensor_device WHERE id::text = %s", (sensor_id_val,))
                        row = cur.fetchone()
                        sensor_device_cache[sensor_id_val] = str(row[0]) if row else None

                sensor_device_id = sensor_device_cache.get(sensor_id_val)
                if not sensor_device_id:
                    continue

                if check_cooldown(db, rule["id"], sensor_device_id, rule["cooldown_minutes"]):
                    continue

                if evaluate_metric(rule["metric"], value, rule, db, sensor_id_val, sensor_type):
                    message = f"{rule['name']}: {value} ({rule['operator']} {rule['threshold_value']})"

                    alert_id = create_alert(
                        db, sensor_device_id, rule["id"], reading_id,
                        rule["severity"], message, value, rule["threshold_value"],
                        rule["auto_create_claim"], rule["claim_type"],
                    )

                    log_ingestion(
                        source_system="anomaly_detector",
                        source_table="sensor_reading",
                        source_id=reading_id,
                        target_table="sensor_alert",
                        target_id=alert_id,
                        operation="insert",
                        payload_hash=hash_payload({"reading_id": reading_id, "rule": rule["name"]}),
                        status="success",
                        rows_affected=1,
                    )

                    device_info = get_sensor_device_info(db, sensor_device_id)
                    alert_data = {
                        "alert_id": alert_id,
                        "severity": rule["severity"],
                        "message": message,
                        "reading_value": value,
                        "threshold_value": rule["threshold_value"],
                        "triggered_at": datetime.now(timezone.utc).isoformat(),
                        "claim_id": None,
                        **device_info,
                    }
                    send_notifications(alert_data)

                    alerts_triggered += 1
                    logger.info("  %s: %s", rule["severity"].upper(), message)

        logger.info("Done: %d alerts triggered", alerts_triggered)
    finally:
        db.close()


def run_baseline_check():
    """Check readings against environmental baselines.

    Compares recent sensor readings to established baselines and creates
    alerts when readings deviate beyond configurable thresholds.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT eb.id, eb.location_id, eb.plot_id, eb.metric_name,
                       eb.baseline_value, eb.unit, eb.sample_count
                FROM environmental_baseline eb
                WHERE eb.metric_name IN ('soil_moisture', 'air_temperature', 'humidity',
                                          'soil_temperature', 'rainfall')
            """)
            baselines = cur.fetchall()

        if not baselines:
            logger.info("No environmental baselines found.")
            return

        logger.info("Checking readings against %d baselines...", len(baselines))

        alerts_triggered = 0
        DEVIATION_THRESHOLD = 0.30  # 30% deviation triggers alert

        for baseline in baselines:
            baseline_id = str(baseline[0])
            location_id = str(baseline[1])
            plot_id = str(baseline[2]) if baseline[2] else None
            metric_name = baseline[3]
            baseline_value = float(baseline[4])
            unit = baseline[5]

            if baseline_value == 0:
                continue

            with db.cursor() as cur:
                cur.execute(
                    """
                    SELECT sr.id, sr.sensor_id, sr.value, sr.created_at
                    FROM sensor_reading sr
                    WHERE sr.sensor_type = %s AND sr.location_id = %s
                      AND sr.created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY sr.created_at DESC
                    LIMIT 10
                    """,
                    (metric_name, location_id),
                )
                recent_readings = cur.fetchall()

            if not recent_readings:
                continue

            values = [float(r[1]) for r in recent_readings]
            avg_value = sum(values) / len(values)
            deviation = abs(avg_value - baseline_value) / abs(baseline_value)

            if deviation > DEVIATION_THRESHOLD:
                sensor_id = str(recent_readings[0][0])
                direction = "above" if avg_value > baseline_value else "below"

                with db.cursor() as cur:
                    cur.execute("SELECT id FROM sensor_device WHERE id::text = %s", (sensor_id,))
                    row = cur.fetchone()
                    sensor_device_id = str(row[0]) if row else None

                if not sensor_device_id:
                    continue

                message = (
                    f"Baseline deviation: {metric_name} {avg_value:.2f}{unit} "
                    f"is {direction} baseline {baseline_value:.2f}{unit} "
                    f"({deviation:.0%} deviation)"
                )

                with db.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id FROM alert_rule
                        WHERE sensor_type_id = (
                            SELECT id FROM sensor_type WHERE name = %s LIMIT 1
                        ) AND metric = 'value' AND enabled = true
                        LIMIT 1
                        """,
                        (metric_name,),
                    )
                    rule_row = cur.fetchone()

                if not rule_row:
                    continue

                rule_id = str(rule_row[0])

                if check_cooldown(db, rule_id, sensor_device_id, 120):
                    continue

                alert_id = create_alert(
                    db, sensor_device_id, rule_id, sensor_id,
                    "warning", message, avg_value, baseline_value,
                )

                device_info = get_sensor_device_info(db, sensor_device_id)
                alert_data = {
                    "alert_id": alert_id,
                    "severity": "warning",
                    "message": message,
                    "reading_value": avg_value,
                    "threshold_value": baseline_value,
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    **device_info,
                }
                send_notifications(alert_data)

                alerts_triggered += 1
                logger.info("  Baseline deviation: %s", message)

        logger.info("Baseline check done: %d alerts triggered", alerts_triggered)
    finally:
        db.close()


def list_rules():
    """List all configured alert rules."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT ar.id, ar.name, st.name as sensor_type, ar.metric,
                       ar.operator, ar.threshold_value, ar.severity, ar.enabled,
                       ar.auto_create_claim, ar.cooldown_minutes
                FROM alert_rule ar
                JOIN sensor_type st ON ar.sensor_type_id = st.id
                ORDER BY ar.severity, ar.name
            """)
            rules = cur.fetchall()

        if not rules:
            logger.info("No alert rules configured.")
            return

        logger.info("%d alert rules:", len(rules))
        for r in rules:
            status = "enabled" if r[7] else "disabled"
            claim = " [auto-claim]" if r[8] else ""
            logger.info(
                "  %s | %s | %s %s %s | cooldown:%dm | %s%s",
                r[1], r[2], r[3], r[4], r[5], r[9], r[6], claim,
            )
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sensor anomaly detection")
    parser.add_argument("--sensor", help="Check readings for specific sensor UUID")
    parser.add_argument("--since", help="Check readings since datetime (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--baseline-check", action="store_true", help="Check against baselines")
    parser.add_argument("--list-rules", action="store_true", help="List configured alert rules")
    args = parser.parse_args()

    if args.list_rules:
        list_rules()
    elif args.baseline_check:
        run_baseline_check()
    else:
        run_check(sensor_id=args.sensor, since=args.since)
