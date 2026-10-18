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

import hashlib
import hmac
import json
import os
import signal
import sys

from ..common.errors import safe_exception_class
from ..common.logging import get_logger
from .base import get_db, hash_payload, log_ingestion
from .field_validation import get_transport_timestamp_mode, parse_transport_timestamp, validate_sensor_reading
from .sensor_ingester import get_sensor_type_ranges
from .sensor_projection import project_sensor_reading

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
    if not isinstance(signature, str) or not signature or not secret:
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
        self._delivery_mode = os.environ.get("MQTT_DELIVERY_MODE", "legacy")
        self._client_id = os.environ.get("MQTT_CLIENT_ID", "")
        self._timestamp_mode = os.environ.get("KOKONUT_SENSOR_TIMESTAMP_MODE", "legacy")
        from services.core.mqtt_state import MQTTState

        self._state = MQTTState(os.environ.get("MQTT_STATE_FILE"))
        self._connected = False
        self._subscribed = False
        self._subscription_mid = None
        self._state_active = False

    def _connect_db(self):
        if self._db is None:
            self._db = get_db()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            self._subscribed = False
            self._state.write(connected=True, subscribed=False)
            logger.info("Connected to MQTT broker at %s:%d", self.broker, self.port)
            result, self._subscription_mid = client.subscribe(SENSOR_TOPIC, qos=1 if self._delivery_mode == "qos1" else 0)
            if result != 0:
                raise RuntimeError("MQTT subscription request failed")
            logger.info("Requested subscription to topic: %s", SENSOR_TOPIC)
        else:
            raise RuntimeError(f"MQTT connection rejected: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            # Configuration errors must not become terminal receipt outcomes.
            get_transport_timestamp_mode(self._timestamp_mode)
            if self._delivery_mode == "qos1" and msg.qos != 1:
                logger.error("Rejected sensor delivery without QoS 1; publisher must select QoS 1 or higher")
                return
            def process():
                topic_parts = msg.topic.split("/")
                if len(topic_parts) == 4 and topic_parts[0] == "sensors" and topic_parts[3] == "readings":
                    return self._handle_reading(msg.payload, topic_parts[1], topic_parts[2])
                logger.warning("Rejected sensor delivery with unsupported topic")
                return "rejected"

            if self._delivery_mode == "qos1":
                from .mqtt_delivery import process_delivery

                outcome = process_delivery(msg.topic, bytes(msg.payload), process)
                if outcome["status"] == "failed":
                    raise RuntimeError("Sensor processing failed; delivery retained for retry")
            else:
                process()
            if self._delivery_mode == "qos1":
                if client.ack(msg.mid, msg.qos) != 0:
                    raise RuntimeError("MQTT acknowledgement failed")
        except Exception as e:
            logger.error("Error processing MQTT message (%s)", type(e).__name__)
            if self._delivery_mode == "qos1":
                # Exit without ACK. Broker session can redeliver after restart.
                raise RuntimeError(
                    f"MQTT message processing failed ({type(e).__name__})"
                ) from None

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties=None):
        if mid != self._subscription_mid:
            return
        if self._delivery_mode == "qos1" and (not reason_codes or any(code != 1 for code in reason_codes)):
            raise RuntimeError("Broker did not grant the required QoS 1 subscription")
        self._subscribed = bool(reason_codes) and all(code == 0 or code == 1 or code == 2 for code in reason_codes)
        self._state.write(connected=self._connected, subscribed=self._subscribed)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        self._connected = False
        self._subscribed = False
        self._subscription_mid = None
        self._state.write(connected=False, subscribed=False)

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
        if len(payload) > 10240:
            logger.warning("Reading payload exceeds the sensor body limit")
            return "rejected"
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Invalid reading payload")
            return "rejected"

        if not isinstance(data, dict):
            logger.warning("Reading payload must be an object")
            return "rejected"

        device_id = data.get("device_id")
        value = data.get("value")
        unit = data.get("unit")
        timestamp = data.get("timestamp")
        signature = data.get("signature")
        payload_quality = data.get("quality", "good")

        if (
            not isinstance(device_id, str) or not 1 <= len(device_id) <= 255
            or (unit is not None and (not isinstance(unit, str) or len(unit) > 64))
            or (timestamp is not None and (not isinstance(timestamp, str) or len(timestamp) > 128))
            or not isinstance(payload_quality, str) or len(payload_quality) > 32
            or (signature is not None and not isinstance(signature, str))
        ):
            logger.warning("Reading payload fields are invalid")
            return "rejected"

        if self._delivery_mode == "qos1" and not timestamp:
            logger.warning("Rejected QoS 1 reading without a stable timestamp")
            return "rejected"

        if not device_id or value is None:
            logger.warning("Reading missing device_id or value")
            return "rejected"

        self._connect_db()
        cur = None
        try:
            cur = self._db.cursor()
            cur.execute("SET LOCAL lock_timeout = '5s'")

            # Look up device
            cur.execute("""
                SELECT sd.id, sd.location_id, sd.plot_id, st.name AS sensor_type
                       , sd.metadata->>'shared_secret' AS shared_secret
                FROM sensor_device sd
                JOIN sensor_type st ON st.id = sd.sensor_type_id
                WHERE sd.slug = %s AND sd.status = 'active'
                FOR SHARE OF sd
            """, (device_id,))
            row = cur.fetchone()
            if not row:
                logger.warning("Unknown device: %s (register first)", device_id)
                return "rejected"

            device_db_id = str(row[0])
            location_id = str(row[1])
            plot_id = str(row[2]) if row[2] else None
            sensor_type = row[3]
            shared_secret = row[4]

            if str(location_id) != topic_location_id or sensor_type != topic_sensor_type:
                logger.warning("MQTT topic identity mismatch for device: %s", device_id)
                return "rejected"

            if not _verify_reading_signature(
                data, signature, shared_secret, topic_location_id, topic_sensor_type
            ):
                logger.warning("Invalid MQTT reading signature for device: %s", device_id)
                return "rejected"

            # Parse timestamp
            try:
                reading_time = parse_transport_timestamp(timestamp, self._timestamp_mode)
            except (AttributeError, TypeError, ValueError):
                logger.warning("Invalid reading timestamp or timestamp mode")
                return "rejected"

            ranges = get_sensor_type_ranges(self._db, strict=True)
            validation = validate_sensor_reading(
                value, sensor_type, unit, reading_time, payload_quality, ranges=ranges, identity=device_id
            )
            if validation.status == "rejected":
                logger.warning("Invalid MQTT reading for device %s: %s", device_id, validation.errors)
                log_ingestion(
                    source_system="mqtt_sensor", source_table="sensor_reading", source_id=device_id,
                    target_table="sensor_reading", target_id=None, operation="insert",
                    payload_hash=hash_payload(data), status="failed", error_message="; ".join(validation.errors),
                    validation_status="rejected", validation_errors=validation.errors,
                    validation_warnings=validation.warnings, dedupe_key=validation.dedupe_key,
                )
                return "rejected"
            quality = "suspect" if validation.status == "suspect" else "good"

            # Insert reading
            cur.execute("""
                INSERT INTO sensor_reading
                    (location_id, plot_id, sensor_id, sensor_type, reading_date, reading_time, value, unit, quality,
                     source_system, source_id, source_raw, schema_version)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'field-ingestion-v1')
                 ON CONFLICT (sensor_id, reading_date, reading_time) DO NOTHING
                 RETURNING id
            """, (
                location_id, plot_id, device_db_id, sensor_type,
                reading_time.date(), reading_time.time(),
                float(value), unit or "", quality, "mqtt_sensor", device_id, json.dumps(data),
            ))
            inserted = cur.fetchone()
            if not inserted:
                self._db.commit()
                log_ingestion(
                    source_system="mqtt_sensor", source_table="sensor_reading", source_id=device_id,
                    target_table="sensor_reading", target_id=None, operation="insert",
                    payload_hash=hash_payload(data), status="partial", error_message="duplicate reading",
                    validation_status="duplicate", dedupe_key=validation.dedupe_key,
                )
                return "duplicate"
            reading_id = str(inserted[0])

            # Update device health
            cur.execute("""
                INSERT INTO sensor_device_health (device_id, last_seen_at, status)
                VALUES (%s, NOW(), 'online')
                ON CONFLICT (device_id) DO UPDATE SET
                    last_seen_at = NOW(),
                    status = 'online',
                    updated_at = NOW()
            """, (device_db_id,))

            # Enqueue before commit so the source row and analytical delivery are atomic.
            self._insert_ch(
                reading_id, location_id, plot_id, device_db_id, sensor_type,
                value, unit, reading_time, quality, self._db,
            )
            self._db.commit()

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
                validation_status=validation.status,
                validation_warnings=validation.warnings,
                dedupe_key=validation.dedupe_key,
            )
            return "accepted"
        finally:
            try:
                if cur is not None:
                    cur.close()
            finally:
                # Clear rejected/read-only transactions and failed writes. A
                # successful source/outbox commit above is already durable.
                try:
                    self._db.rollback()
                except Exception:
                    failed_conn = self._db
                    self._db = None
                    failed_conn.close()
                    raise

    def _insert_ch(self, reading_id, location_id, plot_id, sensor_id, sensor_type, value, unit, timestamp, quality="good", conn=None):
        """Compatibility wrapper over the shared sensor projection."""
        if conn is not None:
            return project_sensor_reading(reading_id, location_id, plot_id, sensor_id, sensor_type,
                                          value, unit, timestamp, quality, conn)
        try:
            project_sensor_reading(reading_id, location_id, plot_id, sensor_id, sensor_type,
                                   value, unit, timestamp, quality)
        except Exception as exc:
            logger.warning("ClickHouse insert failed (%s)", type(exc).__name__)

    def start(self):
        """Start the MQTT subscriber."""
        from services.core.adapters.mqtt import create_client
        from services.core.providers import ProviderSettings

        if not ProviderSettings.from_environment().mqtt:
            logger.info("MQTT provider disabled")
            return

        self._state_active = True
        self._state.write(connected=False, subscribed=False)

        try:
            get_transport_timestamp_mode(self._timestamp_mode)
            if self._delivery_mode not in {"legacy", "qos1"}:
                raise ValueError("MQTT_DELIVERY_MODE must be legacy or qos1")
            if self._delivery_mode == "qos1":
                if not self._client_id.strip():
                    raise ValueError("MQTT_CLIENT_ID is required for QoS 1 delivery")
                self.client = create_client(client_id=self._client_id, clean_session=False, manual_ack=True)
            else:
                self.client = create_client()
        except ImportError:
            logger.error("paho-mqtt not installed. Run: pip install paho-mqtt")
            sys.exit(1)

        if self.client is None:
            logger.info("MQTT provider disabled")
            return

        if not self.username or not self.password:
            raise RuntimeError("MQTT_USERNAME and MQTT_PASSWORD are required")

        self._running = True
        self.client.username_pw_set(self.username, self.password)
        try:
            self.client.tls_set(ca_certs=self.ca_cert, certfile=self.client_cert, keyfile=self.client_key)
        except Exception as exc:
            error_class = safe_exception_class(exc)
            logger.error("MQTT TLS configuration failed (%s)", error_class)
            raise RuntimeError(
                f"MQTT TLS configuration failed ({error_class})"
            ) from None
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe
        self.client.on_disconnect = self._on_disconnect

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
        try:
            try:
                if self._state_active:
                    self._state.write(connected=False, subscribed=False)
            finally:
                if self.client:
                    self.client.disconnect()
        finally:
            if self._db:
                self._db.close()
                self._db = None


def run(broker: str = DEFAULT_BROKER, port: int = DEFAULT_PORT):
    subscriber = MQTTSensorSubscriber(broker=broker, port=port)
    try:
        subscriber.start()
    finally:
        subscriber.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MQTT sensor subscriber")
    parser.add_argument("--broker", default=DEFAULT_BROKER, help="MQTT broker host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="MQTT broker port")
    args = parser.parse_args()

    run(broker=args.broker, port=args.port)
