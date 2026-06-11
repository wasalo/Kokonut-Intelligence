#!/usr/bin/env python3
"""
Anomaly Detector — Sensor Alert Engine

Compares sensor readings against alert rules and environmental baselines.
Triggers sensor_alert records and optionally creates mrv_claim records.

Usage:
    # Check all recent readings for anomalies
    python -m services.ingestion.anomaly_detector

    # Check readings for a specific sensor
    python -m services.ingestion.anomaly_detector --sensor <uuid>

    # Check readings since a specific time
    python -m services.ingestion.anomaly_detector --since "2026-06-11 00:00:00"

    # Create alerts from baseline deviations
    python -m services.ingestion.anomaly_detector --baseline-check
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta

from .base import get_db, log_ingestion, hash_payload

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
]


def ensure_alert_rules(db):
    """Ensure default alert rules exist in the database."""
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM alert_rule")
        count = cur.fetchone()[0]

        if count > 0:
            return

        # Load sensor type IDs
        type_ids = {}
        cur.execute("SELECT id, name FROM sensor_type")
        for row in cur.fetchall():
            type_ids[row[1]] = str(row[0])

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
        print(f"[Anomaly] Created {len(DEFAULT_ALERT_RULES)} default alert rules")


def evaluate_rule(value: float, operator: str, threshold: float, threshold_max: float = None) -> bool:
    """Evaluate a reading against an alert rule. Returns True if alert should fire."""
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

        # Auto-create MRV claim if configured
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
                print(f"    → Auto-created MRV claim: {claim_id}")

        return alert_id


def run_check(sensor_id: str = None, since: str = None):
    """Check recent readings against alert rules."""
    db = get_db()
    ensure_alert_rules(db)

    # Load alert rules
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
        print("[Anomaly] No alert rules configured.")
        db.close()
        return

    # Load recent readings
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
        print(f"[Anomaly] No readings since {since_str}")
        db.close()
        return

    print(f"[Anomaly] Checking {len(readings)} readings against {len(rules)} rules...")

    alerts_triggered = 0
    sensor_device_cache = {}

    for reading in readings:
        reading_id = str(reading[0])
        sensor_id_val = reading[1]
        sensor_type = reading[2]
        value = float(reading[3])

        # Find matching rules
        for rule in rules:
            if rule["sensor_type"] != sensor_type:
                continue

            # Get sensor_device_id for this sensor_id
            if sensor_id_val not in sensor_device_cache:
                with db.cursor() as cur:
                    cur.execute("SELECT id FROM sensor_device WHERE id::text = %s", (sensor_id_val,))
                    row = cur.fetchone()
                    sensor_device_cache[sensor_id_val] = str(row[0]) if row else None

            sensor_device_id = sensor_device_cache.get(sensor_id_val)
            if not sensor_device_id:
                continue

            # Check cooldown
            if check_cooldown(db, rule["id"], sensor_device_id, rule["cooldown_minutes"]):
                continue

            # Evaluate rule
            if evaluate_rule(value, rule["operator"], rule["threshold_value"], rule["threshold_value_max"]):
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

                alerts_triggered += 1
                print(f"  ⚠ {rule['severity'].upper()}: {message}")

    db.commit()
    db.close()
    print(f"\n[Anomaly] Done: {alerts_triggered} alerts triggered")


def run_baseline_check():
    """Check readings against environmental baselines."""
    db = get_db()

    with db.cursor() as cur:
        # Get baselines
        cur.execute("""
            SELECT eb.location_id, eb.plot_id, eb.metric_name, eb.baseline_value, eb.unit
            FROM environmental_baseline eb
            WHERE eb.metric_name IN ('soil_moisture', 'air_temperature', 'humidity')
        """)
        baselines = cur.fetchall()

    if not baselines:
        print("[Anomaly] No environmental baselines found.")
        db.close()
        return

    print(f"[Anomaly] Checking readings against {len(baselines)} baselines...")
    # Baseline comparison would go here — checking if recent readings
    # deviate significantly from established baselines
    # For now, this is a placeholder for future implementation
    print("[Anomaly] Baseline comparison: not yet implemented (placeholder)")

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sensor anomaly detection")
    parser.add_argument("--sensor", help="Check readings for specific sensor UUID")
    parser.add_argument("--since", help="Check readings since datetime (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--baseline-check", action="store_true", help="Check against baselines")
    args = parser.parse_args()

    if args.baseline_check:
        run_baseline_check()
    else:
        run_check(sensor_id=args.sensor, since=args.since)
