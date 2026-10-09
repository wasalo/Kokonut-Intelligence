"""Tests for Systems Thinking suite — Causal Loops, Leverage, Archetypes, Delays."""

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
# CausalLoopEngine Tests
# ---------------------------------------------------------------------------

class TestCausalLoopEngine:
    def _make_engine(self):
        from services.systems.causal_loops import CausalLoopEngine
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return CausalLoopEngine(conn=mock_conn), mock_conn, mock_cursor

    def test_load_loop_returns_none_when_not_found(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = None
        result = engine.load_loop("nonexistent")
        assert result is None

    def test_list_loops_returns_list(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []
        result = engine.list_loops()
        assert result == []

    def test_get_loop_variables_returns_sorted(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "loop_name": "test",
            "loop_type": "reinforcing",
            "domain": "farm",
            "description": "test",
            "is_enabled": True,
        }
        mock_cursor.fetchall.return_value = [
            {"source_variable": "b_var", "target_variable": "a_var", "polarity": "+"},
            {"source_variable": "a_var", "target_variable": "c_var", "polarity": "+"},
        ]
        result = engine.get_loop_variables("test")
        assert result == ["a_var", "b_var", "c_var"]

    def test_evaluate_loop_returns_error_when_not_found(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = None
        result = engine.evaluate_loop("nonexistent", "loc-001")
        assert "error" in result

    def test_list_active_loops_returns_empty_when_no_loops(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []
        result = engine.list_active_loops("loc-001")
        assert result == []

    def test_compute_loop_strength_returns_zero_for_empty(self):
        engine, _, mock_cursor = self._make_engine()
        result = engine._compute_loop_strength({"links": []}, {})
        assert result == 0.0

    def test_compute_loop_strength_with_data(self):
        engine, _, mock_cursor = self._make_engine()
        loop = {"links": [{"polarity": "+"}, {"polarity": "+"}, {"polarity": "+"}]}
        variables = {"a": 1.0, "b": 2.0, "c": 3.0}
        result = engine._compute_loop_strength(loop, variables)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# LeverageAnalyzer Tests
# ---------------------------------------------------------------------------

class TestLeverageAnalyzer:
    def _make_analyzer(self):
        from services.systems.leverage import LeverageAnalyzer
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return LeverageAnalyzer(conn=mock_conn), mock_conn, mock_cursor

    def test_assess_returns_12_points(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchone.return_value = {"cnt": 0}
        mock_cursor.fetchall.return_value = []
        result = analyzer.assess("loc-001")
        assert len(result) == 12

    def test_rank_by_impact_returns_empty_when_no_data(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []
        result = analyzer.rank_by_impact("loc-001")
        assert result == []

    def test_get_point_details_returns_none_when_not_found(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchone.return_value = None
        result = analyzer.get_point_details("loc-001", 12)
        assert result is None

    def test_leverage_point_12_always_low_impact(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchone.return_value = {"cnt": 5}
        result = analyzer._assess_parameters(mock_cursor, "loc-001", {"point": 12, "name": "Parameters"})
        assert result["impact_score"] == 0.2

    def test_leverage_points_sorted_by_impact(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchone.return_value = {"cnt": 0}
        result = analyzer.assess("loc-001")
        scores = [r["impact_score"] for r in result]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# ArchetypeDetector Tests
# ---------------------------------------------------------------------------

class TestArchetypeDetector:
    def _make_detector(self):
        from services.systems.archetypes import ArchetypeDetector
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return ArchetypeDetector(conn=mock_conn), mock_conn, mock_cursor

    def test_detect_returns_list(self):
        detector, _, mock_cursor = self._make_detector()
        mock_cursor.fetchall.return_value = []
        result = detector.detect("loc-001")
        assert isinstance(result, list)

    def test_list_active_returns_empty(self):
        detector, _, mock_cursor = self._make_detector()
        mock_cursor.fetchall.return_value = []
        result = detector.list_active("loc-001")
        assert result == []

    def test_dismiss_returns_false_when_not_found(self):
        detector, _, mock_cursor = self._make_detector()
        mock_cursor.rowcount = 0
        result = detector.dismiss(str(uuid.uuid4()))
        assert result is False

    def test_resolve_returns_false_when_not_found(self):
        detector, _, mock_cursor = self._make_detector()
        mock_cursor.rowcount = 0
        result = detector.resolve(str(uuid.uuid4()))
        assert result is False

    def test_detect_fixes_that_fail_returns_none_when_insufficient_data(self):
        detector, _, mock_cursor = self._make_detector()
        mock_cursor.fetchall.return_value = [{"practice_type": "tillage", "practice_date": datetime.now(), "yield_kg": 100}] * 2
        result = detector._detect_fixes_that_fail(mock_cursor, "loc-001")
        assert result is None  # Less than 3 rows

    def test_detect_erosion_of_goals_returns_none_when_insufficient_data(self):
        detector, _, mock_cursor = self._make_detector()
        mock_cursor.fetchall.return_value = [{"rating": "A", "composite_score": 70, "assessed_at": datetime.now()}] * 2
        result = detector._detect_erosion_of_goals(mock_cursor, "loc-001")
        assert result is None  # Less than 3 ratings


# ---------------------------------------------------------------------------
# DelayMapper Tests
# ---------------------------------------------------------------------------

class TestDelayMapper:
    def _make_mapper(self):
        from services.systems.delays import DelayMapper
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return DelayMapper(conn=mock_conn), mock_conn, mock_cursor

    def test_get_delay_returns_none_when_not_found(self):
        mapper, _, mock_cursor = self._make_mapper()
        mock_cursor.fetchone.return_value = None
        result = mapper.get_delay("nonexistent", "nonexistent")
        assert result is None

    def test_adjust_for_delay_returns_unknown_when_no_data(self):
        mapper, _, mock_cursor = self._make_mapper()
        mock_cursor.fetchone.return_value = None
        result = mapper.adjust_for_delay("2026-01-01T00:00:00", "test", "test")
        assert result["confidence"] == "unknown"

    def test_list_delays_returns_empty(self):
        mapper, _, mock_cursor = self._make_mapper()
        mock_cursor.fetchall.return_value = []
        result = mapper.list_delays()
        assert result == []

    def test_list_domains_returns_empty(self):
        mapper, _, mock_cursor = self._make_mapper()
        mock_cursor.fetchall.return_value = []
        result = mapper.list_domains()
        assert result == []


# ---------------------------------------------------------------------------
# DoubleLoopController Tests
# ---------------------------------------------------------------------------

class TestDoubleLoopController:
    def _make_controller(self):
        from services.systems.double_loop import DoubleLoopController
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return DoubleLoopController(conn=mock_conn), mock_conn, mock_cursor

    def test_evaluate_structural_questions_returns_list(self):
        controller, _, mock_cursor = self._make_controller()
        mock_cursor.fetchone.return_value = {"cnt": 0}
        mock_cursor.fetchall.return_value = []
        result = controller.evaluate_structural_questions("loc-001")
        assert isinstance(result, list)

    def test_challenge_assumption_returns_id(self):
        controller, _, mock_cursor = self._make_controller()
        result = controller.challenge_assumption(
            str(uuid.uuid4()), "Test challenge", "metric_trend"
        )
        assert isinstance(result, str)

    def test_get_structural_health_returns_zeros(self):
        controller, _, mock_cursor = self._make_controller()
        # First call: assumption stats, second: question stats, third: paradigm shifts
        mock_cursor.fetchone.side_effect = [
            {"total": 0, "active": 0, "challenged": 0, "validated": 0, "deprecated": 0},
            {"total": 0, "open_q": 0, "investigating": 0, "answered": 0},
            {"cnt": 0},
        ]
        result = controller.get_structural_health("loc-001")
        assert result["health_score"] == 0.0

    def test_list_assumptions_returns_empty(self):
        controller, _, mock_cursor = self._make_controller()
        mock_cursor.fetchall.return_value = []
        result = controller.list_assumptions()
        assert result == []

    def test_list_challenges_returns_empty(self):
        controller, _, mock_cursor = self._make_controller()
        mock_cursor.fetchall.return_value = []
        result = controller.list_challenges()
        assert result == []

    def test_health_recommendation_when_no_assumptions(self):
        controller, _, mock_cursor = self._make_controller()
        result = controller._health_recommendation(0, 0, 0)
        assert "No structural assumptions" in result

    def test_health_recommendation_when_no_challenges(self):
        controller, _, mock_cursor = self._make_controller()
        result = controller._health_recommendation(5, 0, 0)
        assert "challenged" in result.lower()

    def test_health_recommendation_when_many_open_questions(self):
        controller, _, mock_cursor = self._make_controller()
        result = controller._health_recommendation(5, 3, 10)
        assert "open" in result.lower()
