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

        with patch("services.ingestion.ml_anomaly_detector.fit_prophet", return_value=None), \
             patch("services.ingestion.ml_anomaly_detector.save_models", return_value={"models_saved": []}):
            result = pipeline.trigger_retrain("yield_forecast", reason="scheduled")

        assert "log_id" in result
        assert result["model_name"] == "yield_forecast"
        assert result["status"] == "completed"
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

    def test_trigger_retrain_invokes_training(self):
        """trigger_retrain() should call fit_prophet / fit_isolation_forest."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        mock_cursor.fetchone.return_value = {"accuracy_threshold": 20.0}

        loc = str(uuid.uuid4())
        with patch("services.systems.ml_retraining.MLRetrainingPipeline._get_conn", return_value=mock_conn), \
             patch("services.ingestion.ml_anomaly_detector.fit_prophet") as mock_fit, \
             patch("services.ingestion.ml_anomaly_detector.save_models") as mock_save:
            mock_fit.return_value = MagicMock(name="prophet_model")
            mock_save.return_value = {"status": "success", "models_saved": ["prophet_air_temperature"]}

            result = pipeline.trigger_retrain(
                "weather_anomaly", location_id=loc, reason="scheduled"
            )

        assert result["status"] == "completed"
        assert "prophet_air_temperature" in result["models_trained"]
        mock_fit.assert_called_once()

    def test_trigger_retrain_persists_model(self):
        """save_models() should be called when models are trained."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        mock_cursor.fetchone.return_value = {"accuracy_threshold": 20.0}

        loc = str(uuid.uuid4())
        with patch("services.systems.ml_retraining.MLRetrainingPipeline._get_conn", return_value=mock_conn), \
             patch("services.ingestion.ml_anomaly_detector.fit_isolation_forest") as mock_fit, \
             patch("services.ingestion.ml_anomaly_detector.save_models") as mock_save:
            mock_fit.return_value = ("model", "scaler")
            mock_save.return_value = {"status": "success", "models_saved": ["isolation_forest"]}

            result = pipeline.trigger_retrain(
                "soil_moisture_forecast", location_id=loc, reason="scheduled"
            )

        assert "isolation_forest" in result["models_trained"]
        assert mock_save.call_count >= 1

    def test_trigger_retrain_updates_last_retrain_at(self):
        """last_retrain_at should be updated on the schedule after retrain."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        mock_cursor.fetchone.return_value = {"accuracy_threshold": 20.0}

        with patch("services.systems.ml_retraining.MLRetrainingPipeline._get_conn", return_value=mock_conn), \
             patch("services.ingestion.ml_anomaly_detector.fit_prophet", return_value=None), \
             patch("services.ingestion.ml_anomaly_detector.save_models", return_value={"models_saved": []}):
            pipeline.trigger_retrain("yield_forecast", reason="manual")

        # Check that UPDATE ml_retrain_schedule was called
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        schedule_updates = [c for c in calls if "ml_retrain_schedule" in c and "last_retrain_at" in c]
        assert len(schedule_updates) > 0

    def test_trigger_retrain_records_accuracy_metrics(self):
        """accuracy_after and improvement_pct should be set on log entry."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        mock_cursor.fetchone.return_value = {"accuracy_threshold": 20.0}

        with patch("services.systems.ml_retraining.MLRetrainingPipeline._get_conn", return_value=mock_conn), \
             patch("services.ingestion.ml_anomaly_detector.fit_prophet", return_value=None), \
             patch("services.ingestion.ml_anomaly_detector.save_models", return_value={"models_saved": []}):
            result = pipeline.trigger_retrain("yield_forecast", reason="manual")

        assert "accuracy_before" in result
        assert "accuracy_after" in result
        assert "improvement_pct" in result
        assert result["accuracy_before"] == 20.0
        assert result["accuracy_after"] < 20.0

    def test_trigger_retrain_logs_error_on_failure(self):
        """Training failure should log error but not crash."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        mock_cursor.fetchone.return_value = {"accuracy_threshold": 20.0}

        loc = str(uuid.uuid4())
        with patch("services.systems.ml_retraining.MLRetrainingPipeline._get_conn", return_value=mock_conn), \
             patch("services.ingestion.ml_anomaly_detector.fit_prophet", side_effect=RuntimeError("boom")), \
             patch("services.ingestion.ml_anomaly_detector.save_models", side_effect=RuntimeError("boom")):
            result = pipeline.trigger_retrain("weather_anomaly", location_id=loc, reason="scheduled")

        assert result["status"] == "completed"
        assert result["improvement_pct"] == 0.0

    def test_auto_retrain_triggered_when_enabled(self):
        """Auto-retrain should fire when auto_retrain=True and retrain is due."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "model_name": "weather_anomaly",
                "location_id": str(uuid.uuid4()),
                "accuracy_threshold": 15.0,
                "last_retrain_at": now - timedelta(days=35),
                "next_retrain_at": now - timedelta(days=5),
                "retrain_interval_days": 30,
                "auto_retrain": True,
            }
        ]

        with patch.object(pipeline, "trigger_retrain") as mock_trigger:
            mock_trigger.return_value = {"log_id": "x", "status": "completed"}
            results = pipeline.check_models()

        mock_trigger.assert_called_once()
        assert results[0]["auto_retrain_result"] is not None

    def test_auto_retrain_not_triggered_when_disabled(self):
        """Auto-retrain should NOT fire when auto_retrain=False."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "model_name": "weather_anomaly",
                "location_id": None,
                "accuracy_threshold": 15.0,
                "last_retrain_at": now - timedelta(days=35),
                "next_retrain_at": now - timedelta(days=5),
                "retrain_interval_days": 30,
                "auto_retrain": False,
            }
        ]

        with patch.object(pipeline, "trigger_retrain") as mock_trigger:
            results = pipeline.check_models()

        mock_trigger.assert_not_called()
        assert results[0]["auto_retrain_result"] is None

    def test_auto_retrain_handles_failure_gracefully(self):
        """Auto-retrain failure should not crash check_models."""
        pipeline, mock_conn, mock_cursor = self._make_pipeline()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "model_name": "weather_anomaly",
                "location_id": str(uuid.uuid4()),
                "accuracy_threshold": 15.0,
                "last_retrain_at": now - timedelta(days=35),
                "next_retrain_at": now - timedelta(days=5),
                "retrain_interval_days": 30,
                "auto_retrain": True,
            }
        ]

        with patch.object(pipeline, "trigger_retrain", side_effect=RuntimeError("db down")):
            results = pipeline.check_models()

        assert len(results) == 1
        assert results[0]["auto_retrain_result"] is None
