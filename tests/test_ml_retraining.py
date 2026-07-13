"""Tests for ML Retraining Pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestMLRetrainingPipeline:
    def _make_pipeline(self):
        from services.systems.ml_retraining import MLRetrainingPipeline
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return MLRetrainingPipeline(conn=mock_conn), mock_conn, mock_cursor

    def test_check_models_returns_list(self):
        pipeline, _, mock_cursor = self._make_pipeline()
        mock_cursor.fetchall.return_value = []

        result = pipeline.check_models()

        assert isinstance(result, list)

    def test_check_models_with_schedule(self):
        pipeline, _, mock_cursor = self._make_pipeline()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "model_name": "yield_forecast",
                "location_id": None,
                "accuracy_threshold": 15.0,
                "last_retrain_at": now - timedelta(days=35),
                "next_retrain_at": now - timedelta(days=5),
                "retrain_interval_days": 30,
                "auto_retrain": False,
            }
        ]

        result = pipeline.check_models()

        assert len(result) == 1
        assert result[0]["needs_retrain"] is True
        assert result[0]["reason"] == "scheduled_interval"

    def test_check_models_not_due(self):
        pipeline, _, mock_cursor = self._make_pipeline()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "model_name": "yield_forecast",
                "location_id": None,
                "accuracy_threshold": 15.0,
                "last_retrain_at": now - timedelta(days=5),
                "next_retrain_at": now + timedelta(days=25),
                "retrain_interval_days": 30,
                "auto_retrain": False,
            }
        ]

        result = pipeline.check_models()

        assert result[0]["needs_retrain"] is False

    def test_trigger_retrain_returns_log_id(self):
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        mock_cursor.fetchone.return_value = {"accuracy_threshold": 15.0}

        result = pipeline.trigger_retrain("yield_forecast", reason="scheduled")

        assert "log_id" in result
        assert result["model_name"] == "yield_forecast"
        assert result["status"] == "running"
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_get_retrain_history_returns_list(self):
        pipeline, _, mock_cursor = self._make_pipeline()
        mock_cursor.fetchall.return_value = []

        result = pipeline.get_retrain_history()

        assert isinstance(result, list)

    def test_configure_schedule_persists(self):
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "model_name": "yield_forecast",
            "retrain_interval_days": 30,
            "accuracy_threshold": 15.0,
        }

        result = pipeline.configure_schedule(
            "yield_forecast", interval_days=30, threshold=15.0
        )

        assert result["model_name"] == "yield_forecast"
        mock_conn.commit.assert_called()

    def test_get_model_health_empty(self):
        pipeline, _, mock_cursor = self._make_pipeline()
        mock_cursor.fetchall.return_value = []

        result = pipeline.get_model_health()

        assert isinstance(result, list)

    def test_get_model_health_with_data(self):
        pipeline, _, mock_cursor = self._make_pipeline()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "model_name": "yield_forecast",
                "location_id": None,
                "accuracy_threshold": 15.0,
                "last_retrain_at": now - timedelta(days=10),
                "retrain_interval_days": 30,
                "auto_retrain": False,
                "total_retrains": 3,
                "last_retrain_started": now - timedelta(days=10),
                "last_accuracy_after": 12.5,  # 12.5 < 15.0 threshold = performing well
                "last_improvement_pct": 3.2,
            }
        ]

        result = pipeline.get_model_health()

        assert len(result) == 1
        assert result[0]["health_status"] == "healthy"
        assert result[0]["total_retrains"] == 3

    def test_get_model_health_degraded(self):
        pipeline, _, mock_cursor = self._make_pipeline()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "model_name": "weather_anomaly",
                "location_id": None,
                "accuracy_threshold": 20.0,
                "last_retrain_at": now - timedelta(days=5),
                "retrain_interval_days": 30,
                "auto_retrain": False,
                "total_retrains": 1,
                "last_retrain_started": now - timedelta(days=5),
                "last_accuracy_after": 25.0,  # 25.0 > 20.0 threshold = degraded
                "last_improvement_pct": -2.0,
            }
        ]

        result = pipeline.get_model_health()

        assert result[0]["health_status"] == "degraded"
