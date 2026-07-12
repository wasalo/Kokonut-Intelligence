"""Tests for Stock-and-Flow Simulator and Mental Model Elicitor."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# StockFlowSimulator Tests
# ---------------------------------------------------------------------------

class TestStockFlowSimulator:
    def _make_simulator(self):
        from services.systems.stock_flow import StockFlowSimulator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return StockFlowSimulator(conn=mock_conn), mock_conn, mock_cursor

    def test_list_models_returns_predefined(self):
        simulator, _, mock_cursor = self._make_simulator()
        mock_cursor.fetchall.return_value = []
        result = simulator.list_models()
        assert len(result) >= 4  # At least 4 predefined models

    def test_run_simulation_returns_results(self):
        simulator, _, mock_cursor = self._make_simulator()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        result = simulator.run_simulation("soil_carbon", "loc-001", duration=10)
        assert "trajectory" in result
        assert "summary" in result
        assert len(result["trajectory"]) > 0

    def test_run_simulation_returns_error_for_unknown_model(self):
        simulator, _, mock_cursor = self._make_simulator()
        result = simulator.run_simulation("nonexistent", "loc-001")
        assert "error" in result

    def test_compare_scenarios_returns_multiple(self):
        simulator, _, mock_cursor = self._make_simulator()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        scenarios = [
            {"name": "baseline", "parameters": {}},
            {"name": "cover_crop", "parameters": {"carbon_input": 0.8}},
        ]
        result = simulator.compare_scenarios("soil_carbon", "loc-001", scenarios)
        assert result["scenario_count"] == 2

    def test_eval_rate_returns_float(self):
        simulator, _, mock_cursor = self._make_simulator()
        result = simulator._eval_rate("5.0", {}, {})
        assert result == 5.0

    def test_eval_rate_handles_variable_substitution(self):
        simulator, _, mock_cursor = self._make_simulator()
        result = simulator._eval_rate("soil_carbon * 0.02", {"soil_carbon": 100.0}, {})
        assert result == 2.0

    def test_eval_rate_handles_max(self):
        simulator, _, mock_cursor = self._make_simulator()
        result = simulator._eval_rate("MAX(0, soil_water - 150) * 0.05", {"soil_water": 200.0}, {})
        assert result == 2.5

    def test_compute_summary_returns_stats(self):
        simulator, _, mock_cursor = self._make_simulator()
        trajectory = [{"time": 0, "stock": 50}, {"time": 1, "stock": 55}, {"time": 2, "stock": 60}]
        config = {"stocks": {"stock": {"initial": 50}}}
        result = simulator._compute_summary(trajectory, config)
        assert "stock" in result
        assert result["stock"]["final"] == 60


# ---------------------------------------------------------------------------
# MentalModelElicitor Tests
# ---------------------------------------------------------------------------

class TestMentalModelElicitor:
    def _make_elicitor(self):
        from services.systems.mental_models import MentalModelElicitor
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return MentalModelElicitor(conn=mock_conn), mock_conn, mock_cursor

    def test_list_dimensions_returns_8(self):
        elicitor, _, _ = self._make_elicitor()
        result = elicitor.list_dimensions()
        assert len(result) == 8

    def test_elicit_worldview_returns_id(self):
        elicitor, _, mock_cursor = self._make_elicitor()
        result = elicitor.elicit_worldview(
            "stakeholder-001", "farmer", "regenerative_vs_industrial", 0.7
        )
        assert isinstance(result, str)

    def test_compare_worldviews_returns_empty_when_no_data(self):
        elicitor, _, mock_cursor = self._make_elicitor()
        mock_cursor.fetchall.return_value = []
        result = elicitor.compare_worldviews(["s1", "s2"])
        assert result["dimension_count"] == 0

    def test_suggest_dialogue_returns_empty_when_aligned(self):
        elicitor, _, mock_cursor = self._make_elicitor()
        comparison = {
            "dimensions": [
                {"dimension": "test", "alignment": 0.9, "spread": 0.1, "positions": []}
            ]
        }
        result = elicitor.suggest_dialogue(comparison)
        assert len(result) == 0

    def test_suggest_dialogue_returns_topics_when_divergent(self):
        elicitor, _, mock_cursor = self._make_elicitor()
        comparison = {
            "dimensions": [
                {
                    "dimension": "regenerative_vs_industrial",
                    "alignment": 0.2,
                    "spread": 0.8,
                    "positions": [
                        {"stakeholder_id": "s1", "stakeholder_type": "farmer", "position": 0.1, "position_label": "Industrial"},
                        {"stakeholder_id": "s2", "stakeholder_type": "investor", "position": 0.9, "position_label": "Regenerative"},
                    ],
                }
            ]
        }
        result = elicitor.suggest_dialogue(comparison)
        assert len(result) == 1
        assert result[0]["priority"] == "high"

    def test_get_stakeholder_worldview_returns_empty(self):
        elicitor, _, mock_cursor = self._make_elicitor()
        mock_cursor.fetchall.return_value = []
        result = elicitor.get_stakeholder_worldview("s1")
        assert result == []

    def test_dialogue_question_generated(self):
        elicitor, _, _ = self._make_elicitor()
        result = elicitor._get_dialogue_question("regenerative_vs_industrial")
        assert "practices" in result.lower() or "sustain" in result.lower()
