"""Tests for Meta-Learning Engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestMetaLearningEngine:
    def _make_engine(self):
        from services.systems.meta_learning import MetaLearningEngine
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return MetaLearningEngine(conn=mock_conn), mock_conn, mock_cursor

    def test_select_strategy_no_strategies(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.select_strategy("threshold_tuning", {})

        assert result["selected"] is None
        assert result["reason"] == "no_strategies_available"

    def test_select_strategy_with_strategies(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid.uuid4()),
                "strategy_name": "Raise threshold on false positives",
                "strategy_type": "threshold_tuning",
                "domain": None,
                "effectiveness_score": 75.0,
                "applications_count": 10,
            },
            {
                "id": str(uuid.uuid4()),
                "strategy_name": "Lower threshold on false negatives",
                "strategy_type": "threshold_tuning",
                "domain": None,
                "effectiveness_score": 60.0,
                "applications_count": 8,
            },
        ]

        result = engine.select_strategy("threshold_tuning", {})

        assert result["selected"] is not None
        assert result["selected"]["effectiveness_score"] == 75.0
        assert len(result["candidates"]) == 2

    def test_record_application_returns_id(self):
        engine, mock_conn, mock_cursor = self._make_engine()

        result = engine.record_application(
            str(uuid.uuid4()), "test-loc", {"context": "test"}, outcome="success"
        )

        assert "application_id" in result
        assert result["outcome"] == "success"
        mock_conn.commit.assert_called()

    def test_update_effectiveness_no_data(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = {"total": 0, "successes": 0, "partials": 0, "failures": 0}

        result = engine.update_effectiveness(str(uuid.uuid4()))

        assert result["effectiveness_score"] == 0.0
        assert result["applications_count"] == 0

    def test_update_effectiveness_with_outcomes(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = {
            "total": 10,
            "successes": 7,
            "partials": 2,
            "failures": 1,
        }

        result = engine.update_effectiveness(str(uuid.uuid4()))

        assert result["effectiveness_score"] == 80.0  # (7 + 0.5*2) / 10 * 100
        assert result["applications_count"] == 10

    def test_get_strategy_rankings_returns_list(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.get_strategy_rankings()

        assert isinstance(result, list)

    def test_get_learning_summary_empty(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = {
            "total_strategies": 0,
            "tested_strategies": 0,
            "effective_strategies": 0,
            "avg_effectiveness": 0,
            "total_applications": 0,
            "total_successes": 0,
        }
        mock_cursor.fetchall.return_value = []

        result = engine.get_learning_summary()

        assert result["total_strategies"] == 0
        assert result["total_applications"] == 0

    def test_get_learning_summary_with_data(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = {
            "total_strategies": 8,
            "tested_strategies": 5,
            "effective_strategies": 3,
            "avg_effectiveness": 45.5,
            "total_applications": 50,
            "total_successes": 30,
        }
        mock_cursor.fetchall.return_value = [
            {"strategy_type": "threshold_tuning", "strategy_name": "Raise threshold", "effectiveness_score": 75.0},
            {"strategy_type": "sampling_adjustment", "strategy_name": "Increase sampling", "effectiveness_score": 60.0},
        ]

        result = engine.get_learning_summary()

        assert result["total_strategies"] == 8
        assert result["avg_effectiveness"] == 45.5
        assert "threshold_tuning" in result["best_by_type"]

    def test_recommend_strategy_no_match(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.recommend_strategy("nonexistent_type")

        assert result["recommendation"] is None
        assert result["reason"] == "no_matching_strategies"

    def test_recommend_strategy_with_match(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid.uuid4()),
                "strategy_name": "Best strategy",
                "strategy_type": "threshold_tuning",
                "effectiveness_score": 85.0,
                "applications_count": 20,
            }
        ]

        result = engine.recommend_strategy("threshold_tuning", domain="pest")

        assert result["recommendation"] is not None
        assert result["recommendation"]["name"] == "Best strategy"
        assert result["domain"] == "pest"
