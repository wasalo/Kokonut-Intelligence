"""MQTT actuator command publisher.

Sends commands to actuators (irrigation valves, pest control systems)
via MQTT when triggered by anomaly detection alerts.

Usage:
    from services.ingestion.mqtt_actuator import send_actuation_command
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..common.logging import get_logger

logger = get_logger("ingestion.mqtt_actuator")

DEFAULT_BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))

# Topic patterns for actuator commands
ACTUATOR_TOPIC = "actuators/{location_id}/{actuator_type}/commands"


def build_actuation_command(
    device_id: str,
    actuator_type: str,
    command: str,
    parameters: Dict[str, Any] = None,
    trigger_source: str = "",
    alert_id: str = None,
    alert_severity: str = "",
) -> Dict[str, Any]:
    """Build an actuation command payload.

    Args:
        device_id: Target actuator device ID.
        actuator_type: Type of actuator (irrigation, pest_control, fertilization, notification).
        command: Specific command to execute.
        parameters: Command-specific parameters.
        trigger_source: What triggered this command (anomaly_detector, manual, schedule).
        alert_id: Related sensor_alert ID.
        alert_severity: Severity of the triggering alert.

    Returns:
        Command payload dict.
    """
    return {
        "device_id": device_id,
        "actuator_type": actuator_type,
        "command": command,
        "parameters": parameters or {},
        "trigger_source": trigger_source,
        "alert_id": alert_id,
        "alert_severity": alert_severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def send_actuation_command(
    conn,
    location_id: str,
    command: Dict[str, Any],
    human_approval_required: bool = True,
    alert_id: str = None,
) -> Dict[str, Any]:
    """Send an actuation command and log it.

    Safety: All actuations are logged in actuation_log. Critical severity
    requires human approval before execution.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.
        command: Command payload from build_actuation_command.
        human_approval_required: Whether human approval is needed.
        alert_id: Related sensor_alert ID.

    Returns:
        Actuation log entry details.
    """
    actuator_type = command.get("actuator_type", "notification")
    alert_severity = command.get("alert_severity", "")

    # Determine if approval is needed
    # info/warning can auto-execute; critical always requires approval
    if alert_severity == "critical":
        human_approval_required = True

    initial_status = "requires_approval" if human_approval_required else "pending"

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO actuation_log (
            location_id, sensor_alert_id, actuator_type, actuator_command,
            actuator_topic, command_payload, trigger_source,
            trigger_alert_severity, human_approval_required, status
        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
        RETURNING id
    """, (
        location_id, alert_id, actuator_type, command.get("command", ""),
        ACTUATOR_TOPIC.format(location_id=location_id, actuator_type=actuator_type),
        json.dumps(command), command.get("trigger_source", ""),
        alert_severity, human_approval_required, initial_status,
    ))
    log_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info(
        "Actuation command logged: %s/%s (status=%s, approval=%s)",
        actuator_type, command.get("command"), initial_status, human_approval_required,
    )

    return {
        "actuation_log_id": log_id,
        "actuator_type": actuator_type,
        "command": command.get("command"),
        "status": initial_status,
        "human_approval_required": human_approval_required,
    }


def approve_actuation(conn, actuation_log_id: str, approved_by: str) -> Dict[str, Any]:
    """Approve a pending actuation command.

    Args:
        conn: PostgreSQL connection.
        actuation_log_id: Actuation log UUID.
        approved_by: User ID who approved.

    Returns:
        Updated actuation status.
    """
    cur = conn.cursor()
    cur.execute("""
        UPDATE actuation_log
        SET status = 'approved', approved_by = %s, approved_at = NOW()
        WHERE id = %s AND status = 'requires_approval'
        RETURNING id, actuator_type, actuator_command
    """, (approved_by, actuation_log_id))
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"status": "error", "message": "Actuation not found or not pending approval"}

    logger.info("Actuation %s approved by %s", actuation_log_id[:8], approved_by)
    return {
        "status": "approved",
        "actuation_log_id": actuation_log_id,
        "actuator_type": row[1],
        "command": row[2],
    }


def publish_to_mqtt(
    location_id: str,
    actuator_type: str,
    command: Dict[str, Any],
    broker: str = DEFAULT_BROKER,
    port: int = DEFAULT_PORT,
) -> bool:
    """Publish actuation command to MQTT broker.

    Returns True if published successfully.
    """
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logger.error("paho-mqtt not installed")
        return False

    topic = ACTUATOR_TOPIC.format(location_id=location_id, actuator_type=actuator_type)
    payload = json.dumps(command)

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(broker, port, 60)
        result = client.publish(topic, payload, qos=1)
        client.disconnect()

        if result.rc == 0:
            logger.info("Published actuation to %s", topic)
            return True
        else:
            logger.error("MQTT publish failed with rc=%d", result.rc)
            return False
    except Exception as e:
        logger.error("MQTT publish error: %s", e)
        return False
