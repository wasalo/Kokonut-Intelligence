"""Tests for driver registry, feature flags, and core health."""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Driver Protocol Tests
# ---------------------------------------------------------------------------

class TestDataSourceDriverProtocol:
    """Verify the DataSourceDriver protocol is properly defined."""

    def test_protocol_is_runtime_checkable(self):
        from services.drivers.protocol import DataSourceDriver
        # runtime_checkable protocols have __protocol_attrs__ or __subclasshook__
        assert hasattr(DataSourceDriver, "__subclasshook__") or hasattr(DataSourceDriver, "__protocol_attrs__")

    def test_base_driver_implements_protocol(self):
        from services.drivers.base import BaseDriver
        # BaseDriver is abstract but has the right attributes
        assert hasattr(BaseDriver, "name")
        assert hasattr(BaseDriver, "version")
        assert hasattr(BaseDriver, "driver_type")
        assert hasattr(BaseDriver, "validate_config")
        assert hasattr(BaseDriver, "discover")
        assert hasattr(BaseDriver, "fetch")
        assert hasattr(BaseDriver, "transform")
        assert hasattr(BaseDriver, "health_check")

    def test_concrete_driver_satisfies_protocol(self):
        from services.drivers.protocol import DataSourceDriver

        class MockDriver:
            name = "test"
            version = "1.0.0"
            driver_type = "sensor"
            def validate_config(self, config): return True
            def discover(self, config): return []
            def fetch(self, source): return {"data": []}
            def transform(self, raw): return []
            def health_check(self, config): return True

        driver = MockDriver()
        assert isinstance(driver, DataSourceDriver)


# ---------------------------------------------------------------------------
# Base Driver Tests
# ---------------------------------------------------------------------------

class TestBaseDriver:
    """Unit tests for services.drivers.base.BaseDriver."""

    def test_hash_payload_deterministic(self):
        from services.drivers.base import BaseDriver

        h1 = BaseDriver.hash_payload({"key": "value", "num": 42})
        h2 = BaseDriver.hash_payload({"key": "value", "num": 42})
        assert h1 == h2

    def test_hash_payload_varies(self):
        from services.drivers.base import BaseDriver

        h1 = BaseDriver.hash_payload({"a": 1})
        h2 = BaseDriver.hash_payload({"a": 2})
        assert h1 != h2

    def test_now_utc(self):
        from services.drivers.base import BaseDriver
        from datetime import datetime, timezone

        now = BaseDriver.now_utc()
        assert isinstance(now, datetime)
        assert now.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Driver Registry Tests
# ---------------------------------------------------------------------------

class TestDriverRegistry:
    """Unit tests for services.drivers.registry.DriverRegistry."""

    def test_register_driver(self):
        from services.drivers.registry import DriverRegistry

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (str(uuid.uuid4()),)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        registry = DriverRegistry(conn=mock_conn)
        driver_id = registry.register(
            driver_name="test_driver",
            driver_version="1.0.0",
            driver_type="sensor",
            module_path="services.ingestion.drivers.sensor_csv",
            class_name="Driver",
        )
        assert driver_id is not None

    def test_list_drivers(self):
        from services.drivers.registry import DriverRegistry

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("weather_openweathermap", "1.0.0", "weather", "services.ingestion.drivers.weather_openweathermap", "Driver", True, "Kokonut", "Weather driver", None),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        registry = DriverRegistry(conn=mock_conn)
        drivers = registry.list_drivers()
        assert len(drivers) == 1
        assert drivers[0]["driver_name"] == "weather_openweathermap"

    def test_list_drivers_by_type(self):
        from services.drivers.registry import DriverRegistry

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        registry = DriverRegistry(conn=mock_conn)
        drivers = registry.list_drivers(driver_type="nonexistent")
        assert drivers == []

    def test_list_instances(self):
        from services.drivers.registry import DriverRegistry

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (str(uuid.uuid4()), "adelphi_weather", "weather_openweathermap", {}, None, True, None, "success", 10, 0),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        registry = DriverRegistry(conn=mock_conn)
        instances = registry.list_instances()
        assert len(instances) == 1
        assert instances[0]["instance_name"] == "adelphi_weather"

    def test_create_instance(self):
        from services.drivers.registry import DriverRegistry

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # First call: get driver_id. Second call: insert instance.
        mock_cursor.fetchone.side_effect = [
            (str(uuid.uuid4()),),
            (str(uuid.uuid4()),),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        registry = DriverRegistry(conn=mock_conn)
        instance_id = registry.create_instance(
            driver_name="weather_openweathermap",
            instance_name="test_instance",
            config={"test": True},
        )
        assert instance_id is not None

    def test_create_instance_unknown_driver(self):
        from services.drivers.registry import DriverRegistry

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        registry = DriverRegistry(conn=mock_conn)
        with pytest.raises(ValueError, match="Driver not found"):
            registry.create_instance("nonexistent", "test", {})

    def test_test_driver(self):
        from services.drivers.registry import DriverRegistry

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Driver not in DB
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        registry = DriverRegistry(conn=mock_conn)
        result = registry.test_driver("nonexistent_driver")
        assert result["healthy"] is False
        assert "not found" in result["message"].lower() or "failed" in result["message"].lower()


# ---------------------------------------------------------------------------
# Feature Flags Tests
# ---------------------------------------------------------------------------

class TestFeatureFlags:
    """Unit tests for services.core.features."""

    def test_core_features_always_enabled(self):
        from services.core.features import is_enabled

        assert is_enabled("database") is True
        assert is_enabled("directus") is True

    def test_unknown_feature_disabled(self):
        from services.core.features import is_enabled

        assert is_enabled("nonexistent_feature") is False

    def test_get_feature(self):
        from services.core.features import get_feature

        db_feature = get_feature("database")
        assert db_feature is not None
        assert db_feature["critical"] is True
        assert db_feature["category"] == "core"

    def test_list_features_all(self):
        from services.core.features import list_features

        features = list_features()
        assert len(features) >= 10
        names = [f["name"] for f in features]
        assert "database" in names
        assert "grpc" in names

    def test_list_features_by_category(self):
        from services.core.features import list_features

        core = list_features(category="core")
        assert all(f["category"] == "core" for f in core)
        assert len(core) >= 2

    def test_enabled_features(self):
        from services.core.features import enabled_features

        enabled = enabled_features()
        assert "database" in enabled
        assert "directus" in enabled

    def test_critical_features(self):
        from services.core.features import critical_features

        critical = critical_features()
        assert "database" in critical
        assert "directus" in critical

    def test_require_feature_raises(self):
        from services.core.features import require_feature

        # database is enabled, should not raise
        require_feature("database")

        # nonexistent should raise
        with pytest.raises(RuntimeError, match="not enabled"):
            require_feature("nonexistent_feature")


# ---------------------------------------------------------------------------
# Core Health Tests
# ---------------------------------------------------------------------------

class TestCoreHealth:
    """Unit tests for services.core.health."""

    def test_health_status_to_dict(self):
        from services.core.health import HealthStatus

        status = HealthStatus("test", True, False, "OK", 50)
        d = status.to_dict()
        assert d["service"] == "test"
        assert d["healthy"] is True
        assert d["critical"] is False
        assert d["message"] == "OK"
        assert d["latency_ms"] == 50

    def test_check_health_returns_list(self):
        from services.core.health import check_health

        results = check_health(services=["database"])
        assert len(results) == 1
        assert results[0].service == "database"

    def test_overall_health_structure(self):
        from services.core.health import overall_health

        result = overall_health(services=[])
        assert "healthy" in result
        assert "critical_failures" in result
        assert "services" in result
        assert isinstance(result["services"], list)

    def test_unknown_service_health(self):
        from services.core.health import check_health

        results = check_health(services=["unknown_service"])
        assert len(results) == 1
        assert results[0].healthy is False


# ---------------------------------------------------------------------------
# Driver CLI Tests
# ---------------------------------------------------------------------------

class TestDriverCLI:
    """Verify driver CLI module loads and has correct parser."""

    def test_cli_importable(self):
        from services.drivers.cli import main
        assert callable(main)

    def test_cli_list(self):
        from services.drivers.cli import cmd_list
        assert callable(cmd_list)
