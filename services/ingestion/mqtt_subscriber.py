"""MQTT subscriber for IoT sensor data.

Subscribes to MQTT topics for real-time sensor readings from pre-registered
devices and writes to PostgreSQL + ClickHouse.

Requires:
    - paho-mqtt package
    - MQTT_BROKER_HOST env var (default: localhost)
    - MQTT_BROKER_PORT env var (default: 8883)

Usage:
    python3 -m services.ingestion.mqtt_subscriber
    python3 -m services.ingestion.mqtt_subscriber --broker mqtt.example.com --port 8883
"""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..common.logging import get_logger
from .base import get_db, log_ingestion, hash_payload

logger = get_logger("ingestion.mqtt_subscriber")

# MQTT topic patterns
SENSOR_TOPIC = "sensors/+/+/readings"  # sensors/{location_id}/{sensor_type}/readings

# Default config
DEFAULT_BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "8883"))
DEFAULT_KEEPALIVE = 60
DEFAULT_USERNAME = os.environ.get("MQTT_USERNAME", "")
DEFAULT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
DEFAULT_CA_CERT = os.environ.get("MQTT_CA_CERT", "/mosquitto/certs/ca.crt")
DEFAULT_CLIENT_CERT = os.environ.get("MQTT_CLIENT_CERT", "/mosquitto/certs/subscriber.crt")
DEFAULT_CLIENT_KEY = os.environ.get("MQTT_CLIENT_KEY", "/mosquitto/certs/subscriber.key")


def _verify_reading_signature(
    data: dict,
    signature: str,
    secret: str,
    topic_location_id: str,
    topic_sensor_type: str,
) -> bool:
    """Verify a device HMAC bound to the MQTT topic and payload."""
    if not signature or not secret:
        return False
    signed_data = dict(data)
    signed_data.pop("signature", None)
    canonical = json.dumps(
        {
            "location_id": topic_location_id,
            "sensor_type": topic_sensor_type,
            "payload": signed_data,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    provided = signature.strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


class MQTTSensorSubscriber:
    """MQTT subscriber that receives sensor readings and writes to DB."""

    def __init__(
        self,
        broker: str = DEFAULT_BROKER,
        port: int = DEFAULT_PORT,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        ca_cert: str = DEFAULT_CA_CERT,
        client_cert: str = DEFAULT_CLIENT_CERT,
        client_key: str = DEFAULT_CLIENT_KEY,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key
        self.client = None
        self._running = False
        self._db = None

    def _connect_db(self):
        if self._db is None:
            self._db = get_db()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("Connected to MQTT broker at %s:%d", self.broker, self.port)
            client.subscribe(SENSOR_TOPIC)
            logger.info("Subscribed to topic: %s", SENSOR_TOPIC)
        else:
            logger.error("MQTT connection failed with code %d", rc)

    def _on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) < 4:
                return

            topic_type = topic_parts[3]  # readings or register

            if topic_type == "readings":
                self._handle_reading(msg.payload, topic_parts[1], topic_parts[2])
        except Exception as e:
            logger.error("Error processing MQTT message: %s", e)

    def _handle_registration(self, payload: bytes):
        """Handle device auto-registration."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Invalid registration payload")
            return

        device_id = data.get("device_id")
        if not device_id:
            logger.warning("Registration missing device_id")
            return

        # Registration is controlled through device_manager, not an unauthenticated topic.
        logger.warning("Rejected MQTT registration request for device: %s", device_id)

    def _handle_reading(
        self,
        payload: bytes,
        topic_location_id: str,
        topic_sensor_type: str,
    ):
        """Handle incoming sensor reading."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Invalid reading payload")
            return

        device_id = data.get("device_id")
        value = data.get("value")
        unit = data.get("unit")
        timestamp = data.get("timestamp")
        signature = data.get("signature")

        if not device_id or value is None:
            logger.warning("Reading missing device_id or value")
            return

        self._connect_db()
        cur = self._db.cursor()

        # Look up device
        cur.execute("""
            SELECT sd.id, sd.location_id, sd.plot_id, st.name AS sensor_type
                   , sd.metadata->>'shared_secret' AS shared_secret
            FROM sensor_device sd
            JOIN sensor_type st ON st.id = sd.sensor_type_id
            WHERE sd.slug = %s AND sd.status = 'active'
        """, (device_id,))
        row = cur.fetchone()
        if not row:
            logger.warning("Unknown device: %s (register first)", device_id)
            cur.close()
            return

        device_db_id = str(row[0])
        location_id = str(row[1])
        plot_id = str(row[2]) if row[2] else None
        sensor_type = row[3]
        shared_secret = row[4]

        if str(location_id) != topic_location_id or sensor_type != topic_sensor_type:
            logger.warning("MQTT topic identity mismatch for device: %s", device_id)
            cur.close()
            return

        if not _verify_reading_signature(
            data, signature, shared_secret, topic_location_id, topic_sensor_type
        ):
            logger.warning("Invalid MQTT reading signature for device: %s", device_id)
            cur.close()
            return

        # Parse timestamp
        if timestamp:
            reading_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            reading_time = datetime.now(timezone.utc)

        # Insert reading
        cur.execute("""
            INSERT INTO sensor_reading
                (location_id, plot_id, sensor_id, sensor_type, reading_date, reading_time, value, unit, quality)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'good')
            RETURNING id
        """, (
            location_id, plot_id, device_db_id, sensor_type,
            reading_time.date(), reading_time.time(),
            float(value), unit or "",
        ))
        reading_id = str(cur.fetchone()[0])

        # Update device health
        cur.execute("""
            INSERT INTO sensor_device_health (device_id, last_seen_at, status)
            VALUES (%s, NOW(), 'online')
            ON CONFLICT (device_id) DO UPDATE SET
                last_seen_at = NOW(),
                status = 'online',
                updated_at = NOW()
        """, (device_db_id,))

        self._db.commit()
        cur.close()

        # Dual-write to ClickHouse
        self._insert_ch(reading_id, location_id, plot_id, device_db_id, sensor_type, value, unit, reading_time)

        log_ingestion(
            source_system="mqtt_sensor",
            source_table="sensor_reading",
            source_id=device_id,
            target_table="sensor_reading",
            target_id=reading_id,
            operation="insert",
            payload_hash=hash_payload(data),
            status="success",
            rows_affected=1,
        )

    def _insert_ch(self, reading_id, location_id, plot_id, sensor_id, sensor_type, value, unit, timestamp):
        """Insert reading into ClickHouse."""
        try:
            from .base import post_clickhouse_rows
            post_clickhouse_rows(
                "sensor_readings",
                ["timestamp", "sensor_id", "sensor_type", "location_id", "plot_id",
                 "value", "unit", "quality", "metadata"],
                [[timestamp, str(sensor_id), str(sensor_type), str(location_id),
                  str(plot_id or ""), float(value), str(unit or ""), "good", {}]],
            )
        except Exception as e:
            logger.warning("ClickHouse insert failed: %s", e)

    def start(self):
        """Start the MQTT subscriber."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("paho-mqtt not installed. Run: pip install paho-mqtt")
            sys.exit(1)

        if not self.username or not self.password:
            logger.error("MQTT_USERNAME and MQTT_PASSWORD are required")
            return

        self._running = True
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(self.username, self.password)
        try:
            self.client.tls_set(ca_certs=self.ca_cert, certfile=self.client_cert, keyfile=self.client_key)
        except Exception:
            logger.exception("MQTT TLS configuration failed")
            return
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        logger.info("Connecting to MQTT broker at %s:%d...", self.broker, self.port)
        self.client.connect(self.broker, self.port, DEFAULT_KEEPALIVE)

        # Handle graceful shutdown
        def shutdown(signum, frame):
            logger.info("Shutting down MQTT subscriber...")
            self._running = False
            self.client.disconnect()

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        self.client.loop_forever()

    def stop(self):
        self._running = False
        if self.client:
            self.client.disconnect()
        if self._db:
            self._db.close()


def run(broker: str = DEFAULT_BROKER, port: int = DEFAULT_PORT):
    subscriber = MQTTSensorSubscriber(broker=broker, port=port)
    subscriber.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MQTT sensor subscriber")
    parser.add_argument("--broker", default=DEFAULT_BROKER, help="MQTT broker host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="MQTT broker port")
    args = parser.parse_args()

    run(broker=args.broker, port=args.port)
