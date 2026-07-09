"""IoT sensor push tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")


def test_mqtt_subscriber_file_exists() -> None:
    assert Path("services/ingestion/mqtt_subscriber.py").exists()


def test_http_receiver_file_exists() -> None:
    assert Path("services/ingestion/http_sensor_receiver.py").exists()


def test_device_manager_file_exists() -> None:
    assert Path("services/ingestion/device_manager.py").exists()


def test_mosquitto_config_exists() -> None:
    assert Path("config/mosquitto/mosquitto.conf").exists()


def test_mqtt_subscriber_has_cli() -> None:
    content = Path("services/ingestion/mqtt_subscriber.py").read_text()
    assert 'if __name__' in content
    assert "--broker" in content
    assert "--port" in content


def test_http_receiver_has_cli() -> None:
    content = Path("services/ingestion/http_sensor_receiver.py").read_text()
    assert 'if __name__' in content
    assert "--host" in content
    assert "--port" in content


def test_device_manager_has_cli() -> None:
    content = Path("services/ingestion/device_manager.py").read_text()
    assert 'if __name__' in content
    assert "--list" in content
    assert "--register" in content
    assert "--health" in content


def test_mqtt_subscribes_to_topics() -> None:
    content = Path("services/ingestion/mqtt_subscriber.py").read_text()
    assert "sensors/+/+/readings" in content
    assert "sensors/+/+/register" in content


def test_mqtt_handles_registration() -> None:
    content = Path("services/ingestion/mqtt_subscriber.py").read_text()
    assert "_handle_registration" in content
    assert "sensor_device" in content


def test_mqtt_handles_readings() -> None:
    content = Path("services/ingestion/mqtt_subscriber.py").read_text()
    assert "_handle_reading" in content
    assert "sensor_reading" in content


def test_mqtt_dual_writes() -> None:
    content = Path("services/ingestion/mqtt_subscriber.py").read_text()
    assert "_insert_ch" in content
    assert "log_ingestion" in content


def test_http_has_fastapi_endpoints() -> None:
    content = Path("services/ingestion/http_sensor_receiver.py").read_text()
    assert "/api/v1/sensors/" in content
    assert "/readings" in content
    assert "/batch" in content
    assert "/health" in content


def test_http_has_signature_verification() -> None:
    content = Path("services/ingestion/http_sensor_receiver.py").read_text()
    assert "hmac" in content.lower() or "signature" in content.lower()


def test_http_dual_writes() -> None:
    content = Path("services/ingestion/http_sensor_receiver.py").read_text()
    assert "_insert_ch" in content
    assert "log_ingestion" in content


def test_device_manager_registers() -> None:
    content = Path("services/ingestion/device_manager.py").read_text()
    assert "register_device" in content
    assert "sensor_device" in content
    assert "sensor_type" in content


def test_device_manager_lists() -> None:
    content = Path("services/ingestion/device_manager.py").read_text()
    assert "list_devices" in content
    assert "connectivity" in content


def test_device_manager_health() -> None:
    content = Path("services/ingestion/device_manager.py").read_text()
    assert "get_device_health" in content
    assert "sensor_device_health" in content
    assert "battery_pct" in content


def test_device_manager_updates_health() -> None:
    content = Path("services/ingestion/device_manager.py").read_text()
    assert "update_health" in content
    assert "signal_strength_dbm" in content
    assert "firmware_version" in content


def test_mosquitto_config_has_listener() -> None:
    content = Path("config/mosquitto/mosquitto.conf").read_text()
    assert "listener 1883" in content


def test_mosquitto_config_persistence() -> None:
    content = Path("config/mosquitto/mosquitto.conf").read_text()
    assert "persistence true" in content


def test_docker_compose_has_mosquitto() -> None:
    content = Path("docker-compose.yml").read_text()
    assert "mosquitto" in content
    assert "eclipse-mosquitto" in content


def test_docker_compose_has_mosquitto_volume() -> None:
    content = Path("docker-compose.yml").read_text()
    assert "mosquitto-data" in content


def test_requirements_has_mqtt() -> None:
    content = Path("requirements.txt").read_text()
    assert "paho-mqtt" in content


def test_requirements_has_fastapi() -> None:
    content = Path("requirements.txt").read_text()
    assert "fastapi" in content


def test_requirements_has_uvicorn() -> None:
    content = Path("requirements.txt").read_text()
    assert "uvicorn" in content


def test_schema_has_sensor_device_health() -> None:
    content = SCHEMA.read_text()
    assert "sensor_device_health" in content
    assert "battery_pct" in content
    assert "signal_strength_dbm" in content
    assert "reading_rate_per_hour" in content


def test_schema_has_device_health_view() -> None:
    content = SCHEMA.read_text()
    assert "v_sensor_device_health_summary" in content


def test_mqtt_uses_logging() -> None:
    content = Path("services/ingestion/mqtt_subscriber.py").read_text()
    assert "get_logger" in content


def test_http_uses_logging() -> None:
    content = Path("services/ingestion/http_sensor_receiver.py").read_text()
    assert "get_logger" in content


def test_device_manager_uses_logging() -> None:
    content = Path("services/ingestion/device_manager.py").read_text()
    assert "get_logger" in content
