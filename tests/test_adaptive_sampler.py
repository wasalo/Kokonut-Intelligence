"""Tests for Adaptive Sensor Sampler."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    """Create a mock connection that returns mock_cursor directly."""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# AdaptiveSampler Tests
# ---------------------------------------------------------------------------

class TestAdaptiveSampler:
    """Unit tests for services.ingestion.adaptive_sampler.AdaptiveSampler."""

    def _make_sampler(self):
        from services.ingestion.adaptive_sampler import AdaptiveSampler
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return AdaptiveSampler(conn=mock_conn), mock_conn, mock_cursor

    def test_register_sensor_returns_config_id(self):
        """register_sensor() returns a config ID."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {"id": str(uuid.uuid4())}

        config_id = sampler.register_sensor(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
            location_id="test-loc",
        )

        assert config_id is not None
        assert isinstance(config_id, str)

    def test_get_interval_returns_default_when_not_registered(self):
        """get_interval() returns 15 (default) when sensor not registered."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = None

        interval = sampler.get_interval(
            sensor_device_id="sensor-unregistered",
            sensor_type="soil_moisture",
        )

        assert interval == 15

    def test_get_interval_returns_configured_value(self):
        """get_interval() returns the configured interval."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {"adaptive_interval_minutes": 5}

        interval = sampler.get_interval(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
        )

        assert interval == 5

    def test_increase_sampling_decreases_interval(self):
        """increase_sampling() decreases the interval (faster polling)."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "adaptive_interval_minutes": 15,
            "min_interval_minutes": 1,
        }

        result = sampler.increase_sampling(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
            factor=0.5,
        )

        assert result.get("adjusted") is True
        assert result["new_interval"] == 7  # 15 * 0.5 = 7.5 -> 7

    def test_increase_sampling_respects_minimum(self):
        """increase_sampling() does not go below minimum interval."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "adaptive_interval_minutes": 1,
            "min_interval_minutes": 1,
        }

        result = sampler.increase_sampling(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
            factor=0.5,
        )

        assert result.get("adjusted") is False
        assert result.get("reason") == "already_at_minimum"

    def test_decrease_sampling_increases_interval(self):
        """decrease_sampling() increases the interval (slower polling)."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "adaptive_interval_minutes": 10,
            "max_interval_minutes": 60,
        }

        result = sampler.decrease_sampling(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
            factor=1.5,
        )

        assert result.get("adjusted") is True
        assert result["new_interval"] == 15  # 10 * 1.5 = 15

    def test_decrease_sampling_respects_maximum(self):
        """decrease_sampling() does not exceed maximum interval."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "adaptive_interval_minutes": 60,
            "max_interval_minutes": 60,
        }

        result = sampler.decrease_sampling(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
            factor=1.5,
        )

        assert result.get("adjusted") is False
        assert result.get("reason") == "already_at_maximum"

    def test_list_configs_returns_empty_when_none(self):
        """list_configs() returns empty list when no configs exist."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchall.return_value = []

        result = sampler.list_configs()
        assert result == []

    def test_check_stability_returns_true_when_no_anomalies(self):
        """check_stability() returns True when no anomalies in threshold period."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {"anomaly_count": 0}

        result = sampler.check_stability(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
            stable_threshold_days=7,
        )

        assert result["stable"] is True
        assert result["anomaly_count"] == 0

    def test_check_stability_returns_false_when_anomalies(self):
        """check_stability() returns False when anomalies detected."""
        sampler, mock_conn, mock_cursor = self._make_sampler()
        mock_cursor.fetchone.return_value = {"anomaly_count": 3}

        result = sampler.check_stability(
            sensor_device_id="sensor-001",
            sensor_type="soil_moisture",
            stable_threshold_days=7,
        )

        assert result["stable"] is False
        assert result["anomaly_count"] == 3
