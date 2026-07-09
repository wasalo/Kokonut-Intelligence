"""MQTT subscriber for IoT sensor data.

Subscribes to MQTT topics for real-time sensor readings,
auto-registers unknown devices, and writes to PostgreSQL + ClickHouse.

Requires:
    - paho-mqtt package
    - MQTT_BROKER_HOST env var (default: localhost)
    - MQTT_BROKER_PORT env var (default: 1883)

Usage:
    python3 -m services.ingestion.mqtt_subscriber
    python3 -m services.ingestion.mqtt_subscriber --broker mqtt.example.com --port 1883
"""

from __future__ import annotations

import json
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
DEVICE_TOPIC = "sensors/+/+/register"  # sensors/{location_id}/{sensor_type}/register

# Default config
DEFAULT_BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
DEFAULT_KEEPALIVE = 60


class MQTTSensorSubscriber:
    """MQTT subscriber that receives sensor readings and writes to DB."""

    def __init__(self, broker: str = DEFAULT_BROKER, port: int = DEFAULT_PORT):
        self.broker = broker
        self.port = port
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
            client.subscribe(DEVICE_TOPIC)
            logger.info("Subscribed to topics: %s, %s", SENSOR_TOPIC, DEVICE_TOPIC)
        else:
            logger.error("MQTT connection failed with code %d", rc)

    def _on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) < 4:
                return

            topic_type = topic_parts[3]  # readings or register

            if topic_type == "readings":
                self._handle_reading(msg.payload)
            elif topic_type == "register":
                self._handle_registration(msg.payload)
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

        self._connect_db()
        cur = self._db.cursor()

        # Check if device exists
        cur.execute("SELECT id FROM sensor_device WHERE slug = %s", (device_id,))
        if cur.fetchone():
            logger.info("Device %s already registered", device_id)
            cur.close()
            return

        # Auto-register device
        sensor_type_name = data.get("sensor_type", "air_temperature")
        location_id = data.get("location_id")

        # Get or create sensor type
        cur.execute("SELECT id FROM sensor_type WHERE name = %s", (sensor_type_name,))
        row = cur.fetchone()
        if not row:
            logger.warning("Unknown sensor type: %s", sensor_type_name)
            cur.close()
            return
        sensor_type_id = str(row[0])

        # Insert device
        cur.execute("""
            INSERT INTO sensor_device (name, slug, sensor_type_id, location_id, protocol, status, metadata)
            VALUES (%s, %s, %s, %s, 'mqtt', 'active', %s)
            ON CONFLICT (slug) DO UPDATE SET status = 'active', updated_at = NOW()
            RETURNING id
        """, (
            data.get("name", f"MQTT Device {device_id}"),
            device_id,
            sensor_type_id,
            location_id,
            json.dumps(data),
        ))
        device_db_id = str(cur.fetchone()[0])
        self._db.commit()
        cur.close()
        logger.info("Auto-registered MQTT device: %s (id=%s)", device_id, device_db_id[:8])

    def _handle_reading(self, payload: bytes):
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

        if not device_id or value is None:
            logger.warning("Reading missing device_id or value")
            return

        self._connect_db()
        cur = self._db.cursor()

        # Look up device
        cur.execute("""
            SELECT sd.id, sd.location_id, sd.plot_id, st.name AS sensor_type
            FROM sensor_device sd
            JOIN sensor_type st ON st.id = sd.sensor_type_id
            WHERE sd.slug = %s
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
        import requests as req
        from .config import CH_HOST, CH_PORT, CH_USER, CH_PASSWORD

        ts = timestamp.strftime("%Y-%m-%d %H:%M:%S.000")
        ch_url = f"http://{CH_HOST}:{CH_PORT}"

        query = f"""INSERT INTO sensor_readings
            (timestamp, sensor_id, sensor_type, location_id, plot_id, value, unit, quality, metadata)
            VALUES (
                '{ts}',
                '{sensor_id}',
                '{sensor_type}',
                '{location_id}',
                '{plot_id or ''}',
                {float(value)},
                '{unit or ''}',
                'good',
                map()
            )"""

        try:
            resp = req.post(
                ch_url, data=query.encode("utf-8"),
                auth=(CH_USER, CH_PASSWORD),
                headers={"Content-Type": "text/plain"},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("ClickHouse insert failed: %s", e)

    def start(self):
        """Start the MQTT subscriber."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("paho-mqtt not installed. Run: pip install paho-mqtt")
            sys.exit(1)

        self._running = True
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
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
