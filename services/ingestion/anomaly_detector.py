#!/usr/bin/env python3
"""
Anomaly Detector — Sensor Alert Engine

Compares sensor readings against alert rules and environmental baselines.
Triggers sensor_alert records and optionally creates mrv_claim records.
Sends email and Directus real-time notifications for triggered alerts.

Usage:
    # Check all recent readings for anomalies (explicit aggregate operation)
    python3 -m services.ingestion.anomaly_detector --all-locations

    # Check readings for a specific sensor at a location
    python3 -m services.ingestion.anomaly_detector --location-id <uuid> --sensor <uuid>

    # Check readings since a specific time across all locations
    python3 -m services.ingestion.anomaly_detector --all-locations --since "2026-06-11 00:00:00"

    # Create alerts from baseline deviations
    python3 -m services.ingestion.anomaly_detector --baseline-check --all-locations

    # List active alert rules
    python3 -m services.ingestion.anomaly_detector --list-rules
"""

import argparse
import os
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import psycopg2
import psycopg2.extras

from services.common.cli import print_json
from services.common.smtp import send_message

from ..common.logging import get_logger
from .base import get_db

# Lazy event bus
_event_bus = None


def _get_event_bus(conn=None):
    global _event_bus
    if _event_bus is None:
        from services.events.bus import EventBus
        _event_bus = EventBus(conn=conn)
    return _event_bus


def handle_sensor_reading(
    event_type: str, payload: dict, *, event_id: str | None = None
) -> None:
    """Run anomaly checks for a sensor-reading event."""
    if event_type != "sensor_reading":
        raise ValueError("anomaly handler only accepts sensor_reading events")
    sensor_id = payload.get("sensor_id") or payload.get("sensor_device_id")
    if not sensor_id:
        raise ValueError("sensor-reading events require sensor_id")
    location_id = payload.get("location_id")
    if not location_id:
        raise ValueError("sensor-reading events require location_id")
    if not event_id:
        raise ValueError("sensor-reading event ID is required for idempotent processing")
    try:
        canonical_location_id = str(uuid.UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("sensor-reading event location_id must be a UUID") from exc
    from .sensor_anomaly_worker import process_sensor_reading

    process_sensor_reading(
        sensor_id=str(sensor_id),
        location_id=canonical_location_id,
        event_id=str(event_id),
    )

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
    """Install static defaults only when the shared catalog is still empty.

    The bounded migration-739 function owns the insert so the runtime identity
    can keep listing rules without retaining direct catalog DML.
    """
    with db.cursor() as cur:
        cur.execute("SELECT kokonut_security.ensure_default_alert_rules()")
        inserted = cur.fetchone()[0]
    if inserted:
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
        rate = compute_rate_of_change(db, sensor_id, sensor_type, value)
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


def check_cooldown(
    db,
    alert_rule_id: str,
    sensor_device_id: str,
    cooldown_minutes: int,
    location_id: str | None = None,
) -> bool:
    """Retired direct reader; cooldown is enforced inside signed SQL functions."""
    raise RuntimeError(
        "direct sensor-alert cooldown reads are retired; use the signed anomaly worker"
    )


def create_alert(
    db,
    sensor_device_id: str,
    alert_rule_id: str,
    reading_id: str,
    severity: str,
    message: str,
    reading_value: float,
    threshold_value: float,
    auto_create_claim: bool = False,
    claim_type: str = None,
    location_id: str | None = None,
) -> str:
    """Retired direct writer; alert creation requires a signed worker scope."""
    raise RuntimeError(
        "direct sensor-alert writes are retired; use the signed anomaly worker"
    )


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

        send_message(
            msg,
            host=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            tls_mode=os.environ.get("ALERT_SMTP_TLS_MODE", "starttls").strip().lower(),
        )

        logger.info("Email notification sent for alert %s", alert_data["alert_id"])
        return True

    except Exception as e:
        logger.warning("Failed to send email notification (%s)", type(e).__name__)
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
        from services.common.http import http
        notification_payload = {
            "subject": f"Sensor Alert: {alert_data['sensor_name']}",
            "message": alert_data["message"],
            "type": alert_data["severity"],
            "recipient": "role:00000000-0000-0000-0000-000000000006",  # Field Worker role
            "status": "unread",
        }

        resp = http.post(
            f"{DIRECTUS_URL}/notifications",
            json=notification_payload,
            headers={"Authorization": f"Bearer {DIRECTUS_TOKEN}"},
            timeout=10,
        )
        resp.raise_for_status()

        logger.info("Directus notification sent for alert %s", alert_data["alert_id"])
        return True

    except Exception as e:
        logger.warning("Failed to send Directus notification (%s)", type(e).__name__)
        return False


def send_notifications(alert_data: dict) -> None:
    """Send all configured notifications for a sensor alert."""
    send_email_notification(alert_data)
    send_directus_notification(alert_data)
    send_actuation_commands(alert_data)


def send_actuation_commands(alert_data: dict, db=None) -> None:
    """Dispatch actuation commands if configured on the alert rule.

    Safety: Only dispatches for info/warning severity without approval.
    Critical severity requires human approval (logged as 'requires_approval').
    """
    owns_db = db is None
    try:
        from .mqtt_actuator import send_actuation_command

        if owns_db:
            db = get_db()
        alert_rule_id = alert_data.get("alert_rule_id")
        if not alert_rule_id:
            return

        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT actuator_enabled, actuator_type, actuator_command, actuator_topic,
                   human_approval_required
            FROM alert_rule WHERE id = %s
        """, (alert_rule_id,))
        rule = cur.fetchone()
        cur.close()

        if not rule or not rule.get("actuator_enabled"):
            return

        severity = alert_data.get("severity", "info")
        approval_required = rule.get("human_approval_required", True)

        # Critical always requires a human approval record before any execution.
        if severity == "critical":
            approval_required = True

        command = {
            "device_id": alert_data.get("sensor_device_id"),
            "actuator_type": rule["actuator_type"],
            "command": rule["actuator_command"],
            "parameters": {"alert_id": alert_data.get("alert_id")},
            "trigger_source": "anomaly_detector",
            "alert_id": alert_data.get("alert_id"),
            "alert_severity": severity,
        }

        location_id = alert_data.get("location_id", "")
        result = send_actuation_command(
            db, location_id, command,
            human_approval_required=approval_required,
            alert_id=alert_data.get("alert_id"),
            commit=owns_db,
        )

        logger.info("Actuation logged: %s (status=%s)", rule["actuator_type"], result.get("status"))
    except Exception as e:
        if not owns_db:
            raise
        logger.warning("Actuation dispatch failed (%s)", type(e).__name__)
    finally:
        if owns_db and db is not None:
            db.close()


def get_sensor_device_info(
    db, sensor_device_id: str, location_id: str | None = None
) -> dict:
    """Get sensor device details for notification context."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT sd.name, st.name as sensor_type, l.name as location_name,
                   sd.location_id
            FROM sensor_device sd
            JOIN sensor_type st ON sd.sensor_type_id = st.id
            LEFT JOIN location l ON sd.location_id = l.id
            WHERE sd.id = %s
              AND (%s::uuid IS NULL OR sd.location_id = %s::uuid)
            """,
            (sensor_device_id, location_id, location_id),
        )
        row = cur.fetchone()
        if row:
            return {
                "sensor_name": row[0],
                "sensor_type": row[1],
                "location_name": row[2] or "Unknown",
                "location_id": str(row[3]) if row[3] else None,
            }
    return {
        "sensor_name": "Unknown", "sensor_type": "unknown",
        "location_name": "Unknown", "location_id": None,
    }


def _target_locations(location_id: str | None, *, all_locations: bool) -> list[str]:
    """Resolve explicit targets; the aggregate path is limited to Kokonut Network."""
    if location_id is not None:
        try:
            return [str(uuid.UUID(str(location_id)))]
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("location_id must be a valid UUID") from exc
    if not all_locations:
        raise ValueError("anomaly checks require --location-id or --all-locations")
    from services.core.jobs import kokonut_network_location_ids

    return kokonut_network_location_ids()


def _replay_since(value: str | None) -> datetime:
    """Parse the legacy CLI value and preserve its historical UTC assumption."""
    if value is None:
        return datetime.now(timezone.utc) - timedelta(hours=1)
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("since must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    stable = parsed.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if stable < now - timedelta(hours=24) or stable > now:
        raise ValueError("since must be within the previous 24 hours")
    return stable


def run_check(
    sensor_id: str = None,
    since: str = None,
    *,
    event_id: str = None,
    location_id: str = None,
    all_locations: bool = False,
):
    """Replay durable reading events through the signed anomaly worker only."""
    if event_id is not None:
        raise ValueError(
            "event-driven sensor readings must use handle_sensor_reading"
        )
    stable_sensor_id = None
    if sensor_id is not None:
        try:
            stable_sensor_id = str(uuid.UUID(str(sensor_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("sensor_id must be a valid UUID") from exc
    replay_since = _replay_since(since)
    targets = _target_locations(location_id, all_locations=all_locations)
    if not targets:
        return {"status": "skipped", "reason": "No active Kokonut Network locations are assigned"}

    from .sensor_anomaly_worker import replay_recent_sensor_reading_events

    combined = {
        "events_found": 0,
        "events_processed": 0,
        "rules": 0,
        "reserved": 0,
        "alerts": 0,
        "claims": 0,
        "notifications": 0,
        "actuation_intents": 0,
        "skipped": 0,
    }
    results = []
    for target in targets:
        result = replay_recent_sensor_reading_events(
            location_id=target,
            since=replay_since,
            batch_size=100,
            sensor_id=stable_sensor_id,
        )
        results.append({"location_id": target, **result})
        for key in combined:
            combined[key] += int(result[key])
    return {
        "status": "success",
        "locations_processed": len(results),
        **combined,
        "results": results,
    }


def run_baseline_check(
    location_id: str | None = None, *, all_locations: bool = False
):
    """Evaluate environmental baselines through the signed location worker."""
    targets = _target_locations(location_id, all_locations=all_locations)
    if not targets:
        return {"status": "skipped", "reason": "No active Kokonut Network locations are assigned"}

    from .sensor_baseline_worker import run_baseline_check as run_scoped_baseline_check

    combined = {
        "baselines_checked": 0,
        "alerts_triggered": 0,
        "alerts_replayed": 0,
        "notifications_enqueued": 0,
    }
    results = []
    for target in targets:
        result = run_scoped_baseline_check(target)
        results.append({"location_id": target, **result})
        for key in combined:
            combined[key] += int(result[key])
    return {
        "status": "success",
        "locations_processed": len(results),
        **combined,
        "results": results,
    }


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
            claim = " [auto-claim]" if r[8] else ""
            logger.info(
                "  %s | %s | %s %s %s | cooldown:%dm | %s%s",
                r[1], r[2], r[3], r[4], r[5], r[9], r[6], claim,
            )
    finally:
        db.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sensor anomaly detection")
    parser.add_argument("--sensor", help="Check readings for specific sensor UUID")
    parser.add_argument(
        "--since",
        help="Check events since an ISO-8601 UTC datetime within the last 24 hours",
    )
    parser.add_argument("--baseline-check", action="store_true", help="Check against baselines")
    parser.add_argument("--list-rules", action="store_true", help="List configured alert rules")
    parser.add_argument("--ml-check", action="store_true", help="Run ML anomaly detection")
    parser.add_argument("--ml-train", action="store_true", help="Train and save ML models")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--location-id", help="Limit this operation to one location UUID")
    scope.add_argument(
        "--all-locations",
        action="store_true",
        help="Explicitly fan out across active Kokonut Network locations",
    )
    args = parser.parse_args(argv)

    if args.location_id is not None:
        try:
            args.location_id = str(uuid.UUID(str(args.location_id)))
        except (TypeError, ValueError, AttributeError):
            parser.error("--location-id must be a valid UUID")

    if args.list_rules:
        if args.location_id is not None or args.all_locations:
            parser.error("--list-rules does not accept a location selector")
        list_rules()
    elif args.baseline_check:
        if args.location_id is None and not args.all_locations:
            parser.error("--baseline-check requires --location-id or --all-locations")
        try:
            print_json(
                run_baseline_check(
                    location_id=args.location_id,
                    all_locations=args.all_locations,
                )
            )
        except ValueError as exc:
            parser.error(str(exc))
    elif args.ml_check or args.ml_train:
        if args.ml_train and (args.location_id is None or args.all_locations):
            parser.error("--ml-train requires --location-id and cannot use --all-locations")
        if args.ml_train and args.sensor is not None:
            parser.error("--ml-train saves location/type models and does not accept --sensor")
        if args.ml_check and args.location_id is None and not args.all_locations:
            parser.error("--ml-check requires --location-id or --all-locations")
        if args.ml_check and args.sensor is not None:
            try:
                args.sensor = str(uuid.UUID(str(args.sensor)))
            except (TypeError, ValueError, AttributeError):
                parser.error("--sensor must be a valid UUID for ML checks")

        from services.core.features import is_enabled

        if is_enabled("isolated_sensor_anomaly_ml_worker"):
            if args.location_id is None or args.all_locations:
                parser.error(
                    "isolated ML analysis requires one --location-id; "
                    "--all-locations is not available to the source-only worker"
                )
            from .sensor_anomaly_ml_worker import run_sensor_anomaly_ml

            result = run_sensor_anomaly_ml(
                args.location_id,
                sensor_id=args.sensor,
                train=args.ml_train,
            )
            print_json(result)
            return

        from .base import get_db
        from .ml_anomaly_detector import run_ml_check, save_models

        conn = get_db()
        try:
            if args.ml_check:
                result = run_ml_check(conn, location_id=args.location_id, sensor_id=args.sensor)
                print_json(result)
            elif args.ml_train:
                if not args.location_id:
                    parser.error("--ml-train requires --location-id")
                result = save_models(conn, args.location_id)
                print_json(result)
        finally:
            conn.close()
    else:
        if args.location_id is None and not args.all_locations:
            if args.sensor or args.since:
                parser.error("anomaly checks require --location-id or --all-locations")
            parser.print_help()
            return
        try:
            print_json(
                run_check(
                    sensor_id=args.sensor,
                    since=args.since,
                    location_id=args.location_id,
                    all_locations=args.all_locations,
                )
            )
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
