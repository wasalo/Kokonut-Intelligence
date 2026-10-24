"""Signed, bounded database path for event-driven sensor anomaly handling."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from types import MappingProxyType
from typing import Any

from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.events.notification_outbox import _notification_payloads

SOURCE_SQL = """
SELECT * FROM kokonut_security.read_sensor_anomaly_source(
    %s::uuid, %s::uuid, %s
)
"""
RULES_SQL = """
SELECT * FROM kokonut_security.list_sensor_anomaly_rules(%s::uuid, %s::uuid)
"""
RESERVE_SQL = """
SELECT kokonut_security.reserve_sensor_anomaly_effect(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
COOLDOWN_SQL = """
SELECT kokonut_security.sensor_anomaly_in_cooldown(
    %s::uuid, %s::uuid, %s::uuid
)
"""
EVALUATE_SQL = """
SELECT kokonut_security.evaluate_sensor_anomaly_rule(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
OUTCOME_SQL = """
SELECT kokonut_security.record_sensor_anomaly_effect_outcome(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, NULL
)
"""
CREATE_ALERT_SQL = """
SELECT sensor_alert_id::text, triggered_at
  FROM kokonut_security.create_sensor_anomaly_alert(
      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s
  )
"""
CREATE_CLAIM_SQL = """
SELECT kokonut_security.create_sensor_alert_draft_claim(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
PUBLISH_ALERT_SQL = """
SELECT kokonut_security.publish_sensor_alert_event(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
ENQUEUE_NOTIFICATION_SQL = """
SELECT kokonut_security.enqueue_sensor_alert_notification_intent(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid,
    %s, %s, %s::jsonb
)
"""
HAS_ACTUATOR_SQL = """
SELECT kokonut_security.sensor_alert_actuation_enabled(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
CREATE_ACTUATION_SQL = """
SELECT kokonut_security.create_sensor_alert_actuation_intent(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""


class SensorAnomalyWorkerError(RuntimeError):
    """Raised when a bounded anomaly operation returns an invalid result."""


_QUERY_SQL = MappingProxyType(
    {
        "read_source": SOURCE_SQL,
        "list_rules": RULES_SQL,
        "reserve_effect": RESERVE_SQL,
        "check_cooldown": COOLDOWN_SQL,
        "evaluate_rule": EVALUATE_SQL,
        "record_outcome": OUTCOME_SQL,
        "create_alert": CREATE_ALERT_SQL,
        "create_claim": CREATE_CLAIM_SQL,
        "publish_alert": PUBLISH_ALERT_SQL,
        "enqueue_notification": ENQUEUE_NOTIFICATION_SQL,
        "check_actuator": HAS_ACTUATOR_SQL,
        "create_actuation": CREATE_ACTUATION_SQL,
    }
)


def _statement_for(operation: str) -> str:
    try:
        return _QUERY_SQL[operation]
    except (KeyError, TypeError) as exc:
        raise SensorAnomalyWorkerError("unsupported sensor anomaly query operation") from exc


def _one(connection: Any, operation: str, params: tuple[Any, ...]):
    statement = _statement_for(operation)
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()


def _many(connection: Any, operation: str, params: tuple[Any, ...]):
    statement = _statement_for(operation)
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall()


def _payload_hash(reading_id: str, rule_name: str) -> str:
    serialized = json.dumps(
        {"reading_id": reading_id, "rule": rule_name}, sort_keys=True, default=str
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def _rule(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "name": row[1],
        "sensor_type_id": str(row[2]),
        "sensor_type": row[3],
        "metric": row[4],
        "operator": row[5],
        "threshold_value": float(row[6]),
        "threshold_value_max": float(row[7]) if row[7] is not None else None,
        "severity": row[8],
        "cooldown_minutes": row[9],
        "auto_create_claim": bool(row[10]),
        "claim_type": row[11],
    }


def _record_outcome(
    connection: Any,
    *,
    event_id: str,
    reading_id: str,
    rule_id: str,
    location_id: str,
    outcome: str,
) -> None:
    row = _one(
        connection,
        "record_outcome",
        (event_id, reading_id, rule_id, location_id, outcome),
    )
    if row is None or row[0] is not True:
        raise SensorAnomalyWorkerError("anomaly receipt outcome was not recorded")


def _alert_payload(
    *,
    alert_id: str,
    alert_event_id: str,
    source: dict[str, Any],
    rule: dict[str, Any],
    message: str,
    value: float,
    threshold: float,
    triggered_at: Any,
    claim_id: str | None,
) -> dict[str, Any]:
    if hasattr(triggered_at, "isoformat"):
        triggered_at = triggered_at.isoformat()
    return {
        "alert_id": alert_id,
        "alert_event_id": alert_event_id,
        "alert_rule_id": rule["id"],
        "sensor_device_id": str(source[8]),
        "sensor_id": str(source[1]),
        "severity": rule["severity"],
        "rule_name": rule["name"],
        "message": message,
        "reading_value": value,
        "threshold_value": threshold,
        "triggered_at": str(triggered_at),
        "claim_id": claim_id,
        "sensor_name": source[9] or "Unknown",
        "sensor_type": source[11] or "unknown",
        "location_id": str(source[6]),
        "location_name": source[12] or "Unknown",
    }


def _enqueue_notifications(
    connection: Any,
    *,
    alert_event_id: str,
    event_id: str,
    reading_id: str,
    rule_id: str,
    alert_id: str,
    location_id: str,
    payload: dict[str, Any],
) -> int:
    destinations = _notification_payloads(
        "sensor_alert", payload, environment=dict(os.environ)
    )
    inserted = 0
    for channel, destination_key, message in destinations:
        encoded = json.dumps(
            message, sort_keys=True, separators=(",", ":"), default=str
        )
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("notification payload exceeds the 16 KiB limit")
        result = _one(
            connection,
            "enqueue_notification",
            (
                alert_event_id,
                event_id,
                reading_id,
                rule_id,
                alert_id,
                location_id,
                channel,
                destination_key,
                encoded,
            ),
        )
        if result is None:
            raise SensorAnomalyWorkerError("notification intent returned no result")
        inserted += int(result[0] is True)
    return inserted


def process_sensor_reading(
    *, sensor_id: str, location_id: str, event_id: str
) -> dict[str, int]:
    """Evaluate one event-linked source reading using only signed DB functions."""
    stable_event_id = str(uuid.UUID(str(event_id)))
    stable_location_id = str(uuid.UUID(str(location_id)))
    if not isinstance(sensor_id, str) or not sensor_id.strip():
        raise ValueError("sensor_id must be a non-empty string")

    credential = get_worker_credential("sensor_anomaly")
    connection = get_worker_db("sensor_anomaly")
    stats = {"rules": 0, "reserved": 0, "alerts": 0, "claims": 0,
             "notifications": 0, "actuation_intents": 0, "skipped": 0}
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=stable_location_id,
            resource="sensor_reading",
            action="process",
        )
        source_row = _one(
            connection, "read_source", (stable_event_id, stable_location_id, sensor_id)
        )
        if source_row is None:
            raise SensorAnomalyWorkerError("sensor-reading source was not found")
        source = dict(enumerate(source_row))
        rules = [_rule(row) for row in _many(
            connection,
            "list_rules",
            (source[8], stable_location_id),
        )]
        stats["rules"] = len(rules)

        for rule in rules:
            reserved = _one(
                connection,
                "reserve_effect",
                (stable_event_id, source[0], rule["id"], stable_location_id),
            )
            if reserved is None:
                raise SensorAnomalyWorkerError("anomaly receipt reservation returned no result")
            if reserved[0] is not True:
                stats["skipped"] += 1
                continue
            stats["reserved"] += 1

            cooling = _one(
                connection,
                "check_cooldown",
                (source[8], rule["id"], stable_location_id),
            )
            if cooling is None:
                raise SensorAnomalyWorkerError("anomaly cooldown read returned no result")
            if cooling[0] is True:
                _record_outcome(
                    connection,
                    event_id=stable_event_id,
                    reading_id=str(source[0]),
                    rule_id=rule["id"],
                    location_id=stable_location_id,
                    outcome="cooldown",
                )
                continue

            matches = _one(
                connection,
                "evaluate_rule",
                (stable_event_id, source[0], rule["id"], stable_location_id),
            )
            if matches is None:
                raise SensorAnomalyWorkerError("anomaly rule evaluation returned no result")
            if matches[0] is not True:
                continue

            value = float(source[3])
            message = (
                f"{rule['name']}: {value} "
                f"({rule['operator']} {rule['threshold_value']})"
            )
            alert_result = _one(
                connection,
                "create_alert",
                (
                    stable_event_id,
                    source[0],
                    rule["id"],
                    stable_location_id,
                    message,
                    _payload_hash(str(source[0]), str(rule["name"])),
                ),
            )
            if alert_result is None:
                raise SensorAnomalyWorkerError("sensor alert creation returned no result")
            alert_id, triggered_at = str(alert_result[0]), alert_result[1]

            claim_id = None
            if rule["auto_create_claim"] and rule["claim_type"]:
                claim_result = _one(
                    connection,
                    "create_claim",
                    (
                        stable_event_id,
                        source[0],
                        rule["id"],
                        alert_id,
                        stable_location_id,
                    ),
                )
                if claim_result is None or claim_result[0] is None:
                    raise SensorAnomalyWorkerError("sensor alert draft claim was not created")
                claim_id = str(claim_result[0])
                stats["claims"] += 1

            alert_event_id = str(uuid.uuid4())
            publish_result = _one(
                connection,
                "publish_alert",
                (
                    alert_event_id,
                    stable_event_id,
                    source[0],
                    rule["id"],
                    alert_id,
                    stable_location_id,
                ),
            )
            if publish_result is None or publish_result[0] is not True:
                raise SensorAnomalyWorkerError("sensor alert event was not published")

            payload = _alert_payload(
                alert_id=alert_id,
                alert_event_id=alert_event_id,
                source=source,
                rule=rule,
                message=message,
                value=value,
                threshold=rule["threshold_value"],
                triggered_at=triggered_at,
                claim_id=claim_id,
            )
            stats["notifications"] += _enqueue_notifications(
                connection,
                alert_event_id=alert_event_id,
                event_id=stable_event_id,
                reading_id=str(source[0]),
                rule_id=rule["id"],
                alert_id=alert_id,
                location_id=stable_location_id,
                payload=payload,
            )

            actuator = _one(
                connection,
                "check_actuator",
                (
                    alert_event_id,
                    stable_event_id,
                    source[0],
                    rule["id"],
                    alert_id,
                    stable_location_id,
                ),
            )
            if actuator is None:
                raise SensorAnomalyWorkerError("actuator configuration read returned no result")
            if actuator[0] is True:
                intent = _one(
                    connection,
                    "create_actuation",
                    (
                        alert_event_id,
                        stable_event_id,
                        source[0],
                        rule["id"],
                        alert_id,
                        stable_location_id,
                    ),
                )
                if intent is None or intent[0] is None:
                    raise SensorAnomalyWorkerError("sensor alert actuation intent was not recorded")
                stats["actuation_intents"] += 1
            stats["alerts"] += 1

        connection.commit()
        return stats
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
