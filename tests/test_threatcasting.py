"""Tests for Threatcasting service — cross-impact, flags, signals, narratives,
desirability, horizons, backcasting, cascades, intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, date, timedelta
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    # Ensure cursor() returns the same mock regardless of kwargs
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.cursor.return_value = mock_cursor
    # Override __call__ to always return same cursor
    type(mock_conn.cursor).return_value = mock_cursor
    return mock_conn


def _make_real_dict_row(data: dict):
    """Helper to simulate RealDictCursor fetchone."""
    return data


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_gnh_dimensions_loaded(self):
        from services.threatcasting.config import GNH_DIMENSIONS
        assert len(GNH_DIMENSIONS) == 9
        assert all("name" in d and "weight" in d for d in GNH_DIMENSIONS)

    def test_eight_forms_loaded(self):
        from services.threatcasting.config import EIGHT_FORMS_OF_CAPITAL
        assert len(EIGHT_FORMS_OF_CAPITAL) == 8

    def test_sdg_alignment_loaded(self):
        from services.threatcasting.config import SDG_ALIGNMENT
        assert len(SDG_ALIGNMENT) == 15

    def test_threat_type_defaults(self):
        from services.threatcasting.config import THREAT_TYPE_DEFAULTS
        assert "climate" in THREAT_TYPE_DEFAULTS
        assert "policy" in THREAT_TYPE_DEFAULTS
        assert THREAT_TYPE_DEFAULTS["climate"]["velocity"] == "moderate"

    def test_velocity_multipliers(self):
        from services.threatcasting.config import VELOCITY_MULTIPLIERS
        assert VELOCITY_MULTIPLIERS["slow"] < VELOCITY_MULTIPLIERS["rapid"]

    def test_cascade_config(self):
        from services.threatcasting.config import CASCADE_CONFIG
        assert CASCADE_CONFIG["max_chain_length"] == 10


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_threat_model_defaults(self):
        from services.threatcasting.models import Threat
        t = Threat(location_id="loc-1", threat_name="Test", threat_type="climate",
                   severity_potential="medium", velocity="moderate", reversibility="partially")
        assert t.is_active is True
        assert t.time_horizon_years == 5
        assert t.tags == []

    def test_threat_flag_model(self):
        from services.threatcasting.models import ThreatFlag
        f = ThreatFlag(threat_id="t-1", flag_name="Test Flag", indicator_type="quantitative")
        assert f.status == "normal"
        assert f.comparison_operator == "gte"

    def test_cross_impact_model(self):
        from services.threatcasting.models import CrossImpact
        ci = CrossImpact(
            source_threat_id="t-1", target_threat_id="t-2",
            impact_type="amplifies", impact_magnitude=0.7, impact_direction="positive"
        )
        assert ci.is_enabled is True

    def test_signal_model(self):
        from services.threatcasting.models import ThreatSignal
        s = ThreatSignal(signal_source="manual", signal_type="text", content="test",
                         signal_date=datetime.now(timezone.utc))
        assert s.classified is False

    def test_narrative_model(self):
        from services.threatcasting.models import ThreatNarrative
        n = ThreatNarrative(
            threat_id="t-1", narrative_type="undesirable", title="Test",
            summary="s", detailed_story="d", timeline_years=5
        )
        assert n.is_primary is False

    def test_horizon_model(self):
        from services.threatcasting.models import ThreatHorizon
        h = ThreatHorizon(location_id="loc-1", horizon_name="3-Year", horizon_years=3)
        assert h.is_active is True
        assert h.desirability_framework == "gnh_aligned"

    def test_backcast_plan_model(self):
        from services.threatcasting.models import BackcastPlan
        bp = BackcastPlan(
            narrative_id="n-1", location_id="loc-1", plan_name="Test Plan",
            future_state_description="future", current_gap_analysis="gap",
            milestone_order=1, milestone_description="m1"
        )
        assert bp.milestone_status == "pending"

    def test_cascade_model(self):
        from services.threatcasting.models import ThreatCascade
        tc = ThreatCascade(trigger_threat_id="t-1", cascade_name="Test Cascade")
        assert tc.is_enabled is True


# ---------------------------------------------------------------------------
# Cross-Impact Tests
# ---------------------------------------------------------------------------

class TestCrossImpactAnalyzer:
    def _make_analyzer(self):
        from services.threatcasting.cross_impact import CrossImpactAnalyzer
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return CrossImpactAnalyzer(conn=mock_conn), mock_conn, mock_cursor

    def test_analyze_matrix_returns_structure(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.side_effect = [
            [{"id": "t1", "threat_name": "Drought", "threat_type": "climate",
              "severity_potential": "high", "probability": 0.7, "velocity": "fast"}],
            [{"id": "imp1", "source_threat_id": "t1", "target_threat_id": "t1",
              "impact_type": "amplifies", "impact_magnitude": 0.8,
              "impact_direction": "positive", "source_name": "Drought",
              "target_name": "Drought"}],
        ]
        result = analyzer.analyze_cross_impact_matrix("loc-1")
        assert "threats" in result
        assert "impacts" in result
        assert "summary" in result

    def test_simulate_interaction_returns_probabilities(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.side_effect = [
            [{"id": "t1", "threat_name": "Drought", "threat_type": "climate",
              "severity_potential": "high", "probability": 0.7, "velocity": "fast"}],
            [],
        ]
        result = analyzer.simulate_threat_interaction(["t1"])
        assert "combined_probability" in result
        assert "combined_severity" in result

    def test_location_filters_both_cross_impact_endpoints(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []
        analyzer.get_impacts(location_id="loc-1")
        sql, params = mock_cursor.execute.call_args.args
        assert "ts.location_id = %s AND tt.location_id = %s" in sql
        assert params == ["loc-1", "loc-1"]

    def test_amplification_cycles_are_directed_and_deduplicated(self):
        analyzer, _, _ = self._make_analyzer()
        impacts = [
            {"source_threat_id": "a", "target_threat_id": "b", "impact_type": "amplifies"},
            {"source_threat_id": "b", "target_threat_id": "a", "impact_type": "amplifies"},
        ]
        assert analyzer._detect_amplification_chains({"a": "A", "b": "B"}, impacts) == [["a", "b"]]

    def test_unknown_interaction_endpoint_fails_closed(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []
        with pytest.raises(ValueError, match="Unknown or inactive"):
            analyzer.simulate_threat_interaction(["missing"])

    def test_summary_uses_each_hub_name(self):
        analyzer, _, _ = self._make_analyzer()
        analyzer.analyze_cross_impact_matrix = MagicMock(return_value={
            "threats": [{"id": "a", "threat_name": "A"}, {"id": "b", "threat_name": "B"}],
            "impacts": [{"source_threat_id": "a", "target_threat_id": "b", "impact_type": "amplifies", "impact_magnitude": 0.8}],
            "amplification_cycles": [], "amplification_chains": [],
            "summary": {"total_threats": 2, "total_impacts": 1, "amplifications": 1,
                        "attenuations": 0, "triggers": 0, "avg_magnitude": 0.8,
                        "cycle_count": 0, "chain_count": 0},
        })
        result = analyzer.get_cross_impact_summary("loc-1")
        assert {hub["name"] for hub in result["hub_threats"]} == {"A", "B"}
        assert "amplification_cycles" in result


# ---------------------------------------------------------------------------
# Flag Tests
# ---------------------------------------------------------------------------

class TestFlagMonitor:
    def _make_monitor(self):
        from services.threatcasting.flags import FlagMonitor
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return FlagMonitor(conn=mock_conn), mock_conn, mock_cursor

    def test_evaluate_status_quantitative(self):
        monitor, _, _ = self._make_monitor()
        flag = {"threshold_critical": 0.9, "threshold_warning": 0.7, "threshold_normal": 0.5,
                "comparison_operator": "gte"}
        assert monitor._evaluate_status(flag, "0.95") == "critical"
        assert monitor._evaluate_status(flag, "0.75") == "warning"
        assert monitor._evaluate_status(flag, "0.55") == "elevated"
        assert monitor._evaluate_status(flag, "0.3") == "normal"

    def test_evaluate_status_unknown_value(self):
        monitor, _, _ = self._make_monitor()
        flag = {"threshold_critical": 0.9}
        assert monitor._evaluate_status(flag, "not_a_number") == "unknown"

    def test_check_threshold_gte(self):
        monitor, _, _ = self._make_monitor()
        assert monitor._check_threshold(10.0, 5.0, "gte") is True
        assert monitor._check_threshold(3.0, 5.0, "gte") is False

    def test_check_threshold_lt(self):
        monitor, _, _ = self._make_monitor()
        assert monitor._check_threshold(3.0, 5.0, "lt") is True
        assert monitor._check_threshold(7.0, 5.0, "lt") is False

    def test_flag_status_summary_returns_structure(self):
        monitor, _, mock_cursor = self._make_monitor()
        mock_cursor.fetchall.return_value = [
            {"status": "critical", "count": 2}, {"status": "warning", "count": 3},
        ]
        mock_cursor.fetchone.return_value = {"total": 10}
        result = monitor.get_flag_status_summary("loc-1")
        assert "total_flags" in result
        assert "risk_score" in result

    def test_get_flags_returns_list(self):
        monitor, _, mock_cursor = self._make_monitor()
        mock_cursor.fetchall.return_value = []
        result = monitor.get_flags(location_id="loc-1")
        assert result == []


# ---------------------------------------------------------------------------
# Signal Tests
# ---------------------------------------------------------------------------

class TestSignalIngestor:
    def _make_ingestor(self):
        from services.threatcasting.signals import SignalIngestor
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return SignalIngestor(conn=mock_conn), mock_conn, mock_cursor

    def test_aggregate_signals_returns_structure(self):
        ingestor, _, mock_cursor = self._make_ingestor()
        mock_cursor.fetchall.side_effect = [
            [{"signal_source": "manual", "signal_type": "text", "count": 5,
              "avg_confidence": 0.8, "avg_sentiment": 0.2, "earliest": None, "latest": None}],
            [{"total": 5, "avg_confidence": 0.8, "avg_sentiment": 0.2}],
            [{"day": date(2026, 1, 1), "count": 3}],
        ]
        mock_cursor.fetchone.return_value = {"total": 5, "avg_confidence": 0.8, "avg_sentiment": 0.2}
        result = ingestor.aggregate_signals_by_threat("t-1", days=90)
        assert "total_signals" in result
        assert "by_source_and_type" in result

    def test_get_signals_returns_list(self):
        ingestor, _, mock_cursor = self._make_ingestor()
        mock_cursor.fetchall.return_value = []
        result = ingestor.get_signals(location_id="loc-1")
        assert result == []


# ---------------------------------------------------------------------------
# Narrative Tests
# ---------------------------------------------------------------------------

class TestNarrativeEngine:
    def _make_engine(self):
        from services.threatcasting.narratives import NarrativeEngine
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return NarrativeEngine(conn=mock_conn), mock_conn, mock_cursor

    def test_compare_narratives_returns_structure(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.side_effect = [
            {"id": "n1", "threat_id": "t1", "narrative_type": "undesirable",
             "title": "Bad", "summary": "s", "detailed_story": "d",
             "timeline_years": 5, "probability_estimate": 0.8, "desirability_score": -0.5,
             "threat_name": "Drought", "threat_type": "climate"},
            {"id": "n2", "threat_id": "t1", "narrative_type": "desirable",
             "title": "Good", "summary": "s", "detailed_story": "d",
             "timeline_years": 5, "probability_estimate": 0.3, "desirability_score": 0.7,
             "threat_name": "Drought", "threat_type": "climate"},
        ]
        result = engine.compare_narratives(["n1", "n2"])
        assert "narrative_count" in result
        assert "most_probable" in result

    def test_compare_narratives_needs_two(self):
        engine, _, _ = self._make_engine()
        result = engine.compare_narratives(["n1"])
        assert "error" in result

    def test_get_narratives_returns_list(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []
        result = engine.get_narratives(threat_id="t-1")
        assert result == []


# ---------------------------------------------------------------------------
# Desirability Tests
# ---------------------------------------------------------------------------

class TestDesirabilityAssessor:
    def _make_assessor(self):
        from services.threatcasting.desirability import DesirabilityAssessor
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return DesirabilityAssessor(conn=mock_conn), mock_conn, mock_cursor

    def test_compute_overall_score(self):
        assessor, _, _ = self._make_assessor()
        assessments = [
            {"score": 0.5, "weight": 1.0, "dimension": "a"},
            {"score": -0.3, "weight": 0.5, "dimension": "b"},
        ]
        result = assessor._compute_overall_score(assessments)
        assert "overall_score" in result
        assert -1 <= result["overall_score"] <= 1

    def test_compute_overall_score_empty(self):
        assessor, _, _ = self._make_assessor()
        result = assessor._compute_overall_score([])
        assert result["overall_score"] == 0.0

    def test_get_desirability_summary_returns_structure(self):
        assessor, _, mock_cursor = self._make_assessor()
        mock_cursor.fetchall.return_value = [
            {"id": "a1", "narrative_id": "n1", "assessment_framework": "gnh",
             "dimension": "health", "score": 0.5, "weight": 1.0},
        ]
        result = assessor.get_desirability_summary("n1")
        assert "overall_score" in result
        assert "framework_scores" in result


# ---------------------------------------------------------------------------
# Horizon Tests
# ---------------------------------------------------------------------------

class TestHorizonPlanner:
    def _make_planner(self):
        from services.threatcasting.horizons import HorizonPlanner
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return HorizonPlanner(conn=mock_conn), mock_conn, mock_cursor

    def test_get_horizon_overview_returns_structure(self):
        planner, _, mock_cursor = self._make_planner()
        mock_cursor.fetchone.side_effect = [
            {"id": "h1", "location_id": "loc-1", "horizon_name": "3-Year",
             "horizon_years": 3, "is_active": True, "location_name": "Farm"},
            [{"threat_id": "t1", "threat_name": "Drought", "threat_type": "climate",
              "severity_potential": "high", "probability": 0.7, "velocity": "fast",
              "reversibility": "partially", "relevance_score": 0.8,
              "time_to_impact_years": 2.0, "priority_rank": 1, "notes": None}],
            [],
        ]
        result = planner.get_horizon_overview("h1")
        assert "horizon" in result
        assert "threats" in result
        assert "summary" in result

    def test_compare_horizons_returns_structure(self):
        planner, _, mock_cursor = self._make_planner()
        # get_horizon does fetchone, get_horizon_overview does fetchone + 2x fetchall
        mock_cursor.fetchone.side_effect = [
            {"id": "h1", "location_id": "loc-1", "horizon_name": "3-Year",
             "horizon_years": 3, "is_active": True, "location_name": "Farm"},
            {"id": "h2", "location_id": "loc-1", "horizon_name": "5-Year",
             "horizon_years": 5, "is_active": True, "location_name": "Farm"},
        ]
        mock_cursor.fetchall.side_effect = [
            [{"threat_id": "t1", "threat_name": "Drought", "threat_type": "climate",
              "severity_potential": "high", "probability": 0.7, "velocity": "fast",
              "reversibility": "partially", "relevance_score": 0.8,
              "time_to_impact_years": 2.0, "priority_rank": 1, "notes": None}],
            [],  # narratives for h1
            [{"threat_id": "t1", "threat_name": "Drought", "threat_type": "climate",
              "severity_potential": "high", "probability": 0.7, "velocity": "fast",
              "reversibility": "partially", "relevance_score": 0.8,
              "time_to_impact_years": 2.0, "priority_rank": 1, "notes": None}],
            [],  # narratives for h2
        ]
        result = planner.compare_horizons(["h1", "h2"])
        assert "horizon_count" in result
        assert "total_threats" in result


# ---------------------------------------------------------------------------
# Backcasting Tests
# ---------------------------------------------------------------------------

class TestBackcaster:
    def _make_backcaster(self):
        from services.threatcasting.backcasting import Backcaster
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return Backcaster(conn=mock_conn), mock_conn, mock_cursor

    def test_get_progress_returns_structure(self):
        backcaster, _, mock_cursor = self._make_backcaster()
        mock_cursor.fetchall.return_value = [
            {"id": "m1", "milestone_order": 1, "milestone_status": "completed",
             "milestone_target_date": None, "milestone_description": "m1",
             "plan_name": "Test Plan", "resource_requirements": None},
            {"id": "m2", "milestone_order": 2, "milestone_status": "pending",
             "milestone_target_date": None, "milestone_description": "m2",
             "plan_name": "Test Plan", "resource_requirements": None},
        ]
        result = backcaster.get_progress("n-1")
        assert "total" in result
        assert "completed" in result
        assert "progress_pct" in result

    def test_get_progress_empty(self):
        backcaster, _, mock_cursor = self._make_backcaster()
        mock_cursor.fetchall.return_value = []
        result = backcaster.get_progress("n-1")
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# Cascade Tests
# ---------------------------------------------------------------------------

class TestCascadeModeler:
    def _make_modeler(self):
        from services.threatcasting.cascades import CascadeModeler
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return CascadeModeler(conn=mock_conn), mock_conn, mock_cursor

    def test_model_cascade_returns_structure(self):
        modeler, _, mock_cursor = self._make_modeler()
        # fetchone: trigger threat, chain threat, cross-impact
        mock_cursor.fetchone.side_effect = [
            {"id": "t1", "threat_name": "Drought", "threat_type": "climate",
             "location_id": "loc-1", "severity_potential": "high", "probability": 0.7, "velocity": "fast"},
            {"id": "t2", "threat_name": "Crop Failure", "threat_type": "ecological",
             "location_id": "loc-1", "severity_potential": "critical", "probability": 0.5,
             "velocity": "rapid"},
            {"impact_type": "amplifies", "impact_magnitude": 0.8,
             "impact_direction": "positive", "lag_days": 30},
        ]
        result = modeler.model_cascade("t1", ["t2"])
        assert "cumulative_probability" in result
        assert "chain_effects" in result
        assert result["cumulative_probability"] == 0.63
        assert result["total_impact_severity"] == "critical"
        assert result["estimated_time_hours"] == 48 + 30 * 24 + 12
        assert result["advisory_only"] is True

    def test_model_cascade_rejects_repeated_nodes(self):
        modeler, _, _ = self._make_modeler()
        with pytest.raises(ValueError, match="repeated"):
            modeler.model_cascade("t1", ["t2", "t1"])

    def test_model_cascade_enforces_maximum_total_chain_length(self):
        modeler, _, _ = self._make_modeler()
        with pytest.raises(ValueError, match="maximum length"):
            modeler.model_cascade("trigger", [f"t{i}" for i in range(10)])

    def test_model_cascade_rejects_missing_edge(self):
        modeler, _, mock_cursor = self._make_modeler()
        mock_cursor.fetchone.side_effect = [
            {"id": "t1", "location_id": "loc-1", "severity_potential": "high",
             "probability": 0.7, "velocity": "fast"},
            {"id": "t2", "location_id": "loc-1", "severity_potential": "critical",
             "probability": 0.5, "velocity": "rapid"},
            None,
        ]
        with pytest.raises(ValueError, match="Missing enabled cascade edge"):
            modeler.model_cascade("t1", ["t2"])

    def test_model_cascade_rejects_cross_location_node(self):
        modeler, _, mock_cursor = self._make_modeler()
        mock_cursor.fetchone.side_effect = [
            {"id": "t1", "location_id": "loc-1", "probability": 0.7},
            {"id": "t2", "location_id": "loc-2", "probability": 0.5},
        ]
        with pytest.raises(ValueError, match="another location"):
            modeler.model_cascade("t1", ["t2"])

    def test_get_cascade_risk_score_no_cascades(self):
        modeler, _, mock_cursor = self._make_modeler()
        mock_cursor.fetchall.side_effect = [[], []]
        result = modeler.get_cascade_risk_score("loc-1")
        assert result["total_cascades"] == 0
        assert result["risk_score"] == 0.0

    def test_estimate_propagation_time(self):
        modeler, _, _ = self._make_modeler()
        assert modeler._estimate_propagation_time("slow") == 720
        assert modeler._estimate_propagation_time("rapid") == 12


# ---------------------------------------------------------------------------
# Intelligence Tests
# ---------------------------------------------------------------------------

class TestThreatIntelligence:
    def _make_ti(self):
        from services.threatcasting.intelligence import ThreatIntelligence
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return ThreatIntelligence(conn=mock_conn), mock_conn, mock_cursor

    def test_get_threat_landscape_returns_structure(self):
        ti, _, mock_cursor = self._make_ti()
        # Order: 3 fetchall + 4 fetchone
        mock_cursor.fetchall.side_effect = [
            [{"threat_type": "climate", "count": 3}],
            [{"severity_potential": "high", "count": 2}],
            [{"status": "warning", "count": 2}, {"status": "normal", "count": 5}],
        ]
        mock_cursor.fetchone.side_effect = [
            {"total": 5},      # threat count
            {"active": 1},     # cascade count
            {"cnt": 3},        # horizon count
            {"cnt": 4},        # narrative count
            {"cnt": 6},        # cross-impact count
        ]
        result = ti.get_threat_landscape("loc-1")
        assert "threat_count" in result
        assert "overall_risk_score" in result
        assert "overall_risk_level" in result

    def test_generate_threat_briefing_returns_structure(self):
        ti, _, mock_cursor = self._make_ti()
        # First: get_threat_landscape needs 3 fetchall + 5 fetchone
        # Then: get_threat_intelligence needs 4 fetchall
        mock_cursor.fetchall.side_effect = [
            [{"threat_type": "climate", "count": 3}],
            [{"severity_potential": "high", "count": 2}],
            [{"status": "warning", "count": 2}, {"status": "normal", "count": 5}],
            [],  # signal_summary
            [],  # high_risk_flags
            [],  # top_narratives
            [],  # active_cascades
        ]
        mock_cursor.fetchone.side_effect = [
            {"total": 5},      # threat count
            {"active": 1},     # cascade count
            {"cnt": 3},        # horizon count
            {"cnt": 4},        # narrative count
            {"cnt": 6},        # cross-impact count
        ]
        result = ti.generate_threat_briefing("loc-1")
        assert "executive_summary" in result
        assert "detailed_intelligence" in result

    def test_predict_threat_evolution_consumes_one_row(self):
        ti, _, mock_cursor = self._make_ti()
        mock_cursor.fetchone.return_value = {
            "id": "threat-1",
            "threat_name": "Drought",
            "threat_type": "climate",
            "severity_potential": "high",
            "probability": 0.5,
            "velocity": "fast",
            "reversibility": "partially",
            "time_horizon_years": 5,
        }

        result = ti.predict_threat_evolution("threat-1", horizon_years=2)

        assert result["threat"]["threat_name"] == "Drought"
        assert len(result["projections"]) == 2
        assert mock_cursor.fetchone.call_count == 1


# ---------------------------------------------------------------------------
# CLI Tests (basic import test)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_import(self):
        from services.threatcasting.cli import main
        assert callable(main)


# ---------------------------------------------------------------------------
# Integration Tests (unit-level, mock-based)
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_workflow(self):
        """Test a simplified end-to-end workflow."""
        from services.threatcasting.models import (
            Threat, ThreatFlag, CrossImpact, ThreatSignal,
            ThreatNarrative, ThreatHorizon,
        )

        # Create models
        threat = Threat(
            location_id="loc-1", threat_name="Severe Drought",
            threat_type="climate", severity_potential="high",
            probability=0.7, velocity="fast", reversibility="partially"
        )
        flag = ThreatFlag(
            threat_id=threat.id, flag_name="Rainfall Deficit",
            indicator_type="quantitative", threshold_critical=0.9,
            threshold_warning=0.7, threshold_normal=0.5
        )
        impact = CrossImpact(
            source_threat_id="t1", target_threat_id=threat.id,
            impact_type="amplifies", impact_magnitude=0.6, impact_direction="positive"
        )
        signal = ThreatSignal(
            signal_source="weather_api", signal_type="numeric",
            content="Rainfall 40% below normal", confidence=0.85,
            signal_date=datetime.now(timezone.utc)
        )
        narrative = ThreatNarrative(
            threat_id=threat.id, narrative_type="undesirable",
            title="Drought Cascade", summary="Severe drought leads to crop failure",
            detailed_story="Multi-year drought reduces yields by 60%",
            timeline_years=5, probability_estimate=0.7
        )
        horizon = ThreatHorizon(
            location_id="loc-1", horizon_name="5-Year Climate Risk",
            horizon_years=5, focus_areas=["climate", "ecological"]
        )

        assert threat.is_active is True
        assert flag.status == "normal"
        assert impact.impact_magnitude == 0.6
        assert signal.classified is False
        assert narrative.timeline_years == 5
        assert horizon.desirability_framework == "gnh_aligned"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
