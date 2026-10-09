"""MQTT sensor driver — wraps services.ingestion.mqtt_subscriber."""

from __future__ import annotations

from services.drivers.base import BaseDriver


class Driver(BaseDriver):
    name = "sensor_mqtt"
    version = "1.0.0"
    driver_type = "sensor"

    def validate_config(self, config: dict) -> bool:
        return "broker" in config or "MQTT_BROKER" in __import__("os").environ

    def discover(self, config: dict) -> list[dict]:
        return [{"source_id": "mqtt_all", "display_name": "MQTT sensor stream"}]

    def fetch(self, source: dict) -> dict:
        return {"data": [], "note": "MQTT is event-driven; fetch is a no-op"}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        import os
        broker = config.get("broker") or os.environ.get("MQTT_BROKER", "localhost")
        port = int(config.get("port", os.environ.get("MQTT_PORT", "1883")))
        try:
            import socket
            sock = socket.create_connection((broker, port), timeout=3)
            sock.close()
            return True
        except Exception:
            return False
