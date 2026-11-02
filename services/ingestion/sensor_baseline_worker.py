"""Signed, bounded worker path for environmental-baseline sensor alerts."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.events.notification_outbox import _notification_payloads

EVALUATE_SQL = """
SELECT * FROM kokonut_security.evaluate_sensor_baselines(%s::uuid)
"""
ENQUEUE_NOTIFICATION_SQL = """
SELECT kokonut_security.enqueue_sensor_baseline_notification_intent(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb
)
"""

_RESULT_COLUMNS = (
    "baseline_id",
    "outcome",
    "sensor_alert_id",
    "alert_event_id",
    "reading_id",
    "alert_rule_id",
    "sensor_device_id",
    "severity",
    "message",
    "reading_value",
    "threshold_value",
    "sample_count",
    "triggered_at",
    "sensor_name",
    "sensor_type",
    "location_name",
    "location_id",
)
_OUTCOMES = frozenset(
    {
        "baseline_zero",
        "baseline_unavailable",
        "no_readings",
        "missing_device",
        "missing_rule",
        "below_threshold",
        "cooldown",
        "alert_created",
        "alert_replayed",
    }
)


class SensorBaselineWorkerError(RuntimeError):
    """Raised when a bounded baseline operation returns an invalid result."""


def _stable_uuid(value: Any, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be a valid UUID") from exc


def _dict_row(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        result = row
    else:
        try:
            if len(row) != len(_RESULT_COLUMNS):
                raise SensorBaselineWorkerError(
                    "baseline evaluator returned an invalid row shape"
                )
            result = dict(zip(_RESULT_COLUMNS, row, strict=True))
        except TypeError as exc:
            raise SensorBaselineWorkerError(
                "baseline evaluator returned an invalid row shape"
            ) from exc

    if set(result) != set(_RESULT_COLUMNS):
        raise SensorBaselineWorkerError(
            "baseline evaluator returned an invalid row shape"
        )
    if result["outcome"] not in _OUTCOMES:
        raise SensorBaselineWorkerError(
            "baseline evaluator returned an unsupported outcome"
        )
    return result


def _notification_payload(
    row: dict[str, Any], *, location_id: str
) -> dict[str, Any]:
    required_ids = (
        "baseline_id",
        "alert_event_id",
        "sensor_alert_id",
        "reading_id",
        "alert_rule_id",
        "sensor_device_id",
    )
    stable: dict[str, str] = {}
    for field in required_ids:
        stable[field] = _stable_uuid(row[field], field)
    if _stable_uuid(row["location_id"], "location_id") != location_id:
        raise SensorBaselineWorkerError(
            "baseline evaluator returned a cross-location alert"
        )
    if row["severity"] != "warning" or not isinstance(row["message"], str):
        raise SensorBaselineWorkerError(
            "baseline evaluator returned an invalid alert"
        )
    triggered_at = row["triggered_at"]
    if not isinstance(triggered_at, datetime) or triggered_at.tzinfo is None:
        raise SensorBaselineWorkerError(
            "baseline evaluator returned an invalid alert timestamp"
        )
    if row["reading_value"] is None or row["threshold_value"] is None:
        raise SensorBaselineWorkerError(
            "baseline evaluator returned incomplete alert values"
        )
    if isinstance(row["sample_count"], bool) or not isinstance(
        row["sample_count"], int
    ) or not 1 <= row["sample_count"] <= 10:
        raise SensorBaselineWorkerError(
            "baseline evaluator returned an invalid sample count"
        )

    return {
        "alert_id": stable["sensor_alert_id"],
        "severity": "warning",
        "message": row["message"],
        "reading_value": row["reading_value"],
        "threshold_value": row["threshold_value"],
        "triggered_at": triggered_at.isoformat(),
        "sensor_device_id": stable["sensor_device_id"],
        "sensor_name": row["sensor_name"],
        "sensor_type": row["sensor_type"],
        "location_id": location_id,
        "location_name": row["location_name"],
        "claim_id": None,
    }


def _enqueue_notifications(
    connection: Any, *, row: dict[str, Any], location_id: str
) -> int:
    payload = _notification_payload(row, location_id=location_id)
    destinations = _notification_payloads(
        "sensor_alert", payload, environment=dict(os.environ)
    )
    inserted = 0
    for channel, destination_key, message in destinations:
        if channel not in {"webhook", "directus", "email"}:
            raise SensorBaselineWorkerError(
                "notification channel is not allowlisted"
            )
        if destination_key != "primary" or not isinstance(message, dict):
            raise SensorBaselineWorkerError("notification destination is invalid")
        encoded = json.dumps(
            message, sort_keys=True, separators=(",", ":"), default=str
        )
        if len(encoded.encode("utf-8")) > 16_384:
            raise SensorBaselineWorkerError(
                "notification payload exceeds the 16 KiB limit"
            )
        with connection.cursor() as cursor:
            cursor.execute(
                ENQUEUE_NOTIFICATION_SQL,
                (
                    _stable_uuid(row["alert_event_id"], "alert_event_id"),
                    _stable_uuid(row["baseline_id"], "baseline_id"),
                    _stable_uuid(row["sensor_alert_id"], "sensor_alert_id"),
                    location_id,
                    channel,
                    destination_key,
                    encoded,
                ),
            )
            result = cursor.fetchone()
        if result is None or not isinstance(result[0], bool):
            raise SensorBaselineWorkerError(
                "baseline notification function returned an invalid result"
            )
        inserted += int(result[0])
    # No configured destinations is a valid no-op, matching the legacy
    # send_notifications behavior while preserving the durable alert event.
    return inserted


def run_baseline_check(location_id: str) -> dict[str, int]:
    """Evaluate one location using the isolated sensor-anomaly worker identity.

    The location is mandatory: baseline reads and all durable writes run only
    after installing signed ``sensor_reading/process`` scope on the same
    connection. There is deliberately no shared-runtime fallback.
    """
    stable_location_id = _stable_uuid(location_id, "location_id")
    credential = get_worker_credential("sensor_anomaly")
    connection = get_worker_db("sensor_anomaly")
    stats = {
        "baselines_checked": 0,
        "alerts_triggered": 0,
        "alerts_replayed": 0,
        "notifications_enqueued": 0,
    }
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=stable_location_id,
            resource="sensor_reading",
            action="process",
        )
        with connection.cursor() as cursor:
            cursor.execute(EVALUATE_SQL, (stable_location_id,))
            rows = cursor.fetchall()

        parsed_rows = [_dict_row(row) for row in rows]
        stats["baselines_checked"] = len(parsed_rows)
        for row in parsed_rows:
            _stable_uuid(row["baseline_id"], "baseline_id")
            if _stable_uuid(row["location_id"], "location_id") != stable_location_id:
                raise SensorBaselineWorkerError(
                    "baseline evaluator returned a cross-location result"
                )
            if row["outcome"] == "alert_created":
                stats["notifications_enqueued"] += _enqueue_notifications(
                    connection,
                    row=row,
                    location_id=stable_location_id,
                )
                stats["alerts_triggered"] += 1
            elif row["outcome"] == "alert_replayed":
                _notification_payload(row, location_id=stable_location_id)
                # Alert/event/intents committed atomically on the first pass.
                # A response-loss retry returns the original IDs and must not
                # create any additional notification rows.
                stats["alerts_replayed"] += 1

        connection.commit()
        return stats
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
