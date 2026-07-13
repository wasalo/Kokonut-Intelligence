"""Tests for Backcasting Enhancements — principles, alignment, assumption challenges,
path comparison, gap analysis, and effectiveness scoring."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, date, timedelta
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    type(mock_conn.cursor).return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestBackcastingEnhancementModels:
    def test_backcast_principle_model(self):
        from services.threatcasting.models import BackcastPrinciple
        bp = BackcastPrinciple(
            narrative_id="n-1", location_id="loc-1",
            principle_name="Carbon Negative", description="Net carbon sequestration",
            principle_type="ecological", metric_key="soil_carbon_delta",
            comparison_operator="gte", target_value=0.0
        )
        assert bp.is_active is True
        assert bp.weight == 1.0
        assert bp.source_system == "manual"

    def test_backcast_principle_create_model(self):
        from services.threatcasting.models import BackcastPrincipleCreate
        bp = BackcastPrincipleCreate(
            narrative_id="n-1", location_id="loc-1",
            principle_name="Water Positive", description="Net water recharge",
            principle_type="ecological"
        )
        assert bp.comparison_operator == "gte"
        assert bp.invert_direction is False

    def test_backcast_principle_alignment_model(self):
        from services.threatcasting.models import BackcastPrincipleAlignment
        a = BackcastPrincipleAlignment(
            milestone_id="m-1", principle_id="p-1", alignment_score=0.75
        )
        assert a.alignment_score == 0.75
        assert a.current_value is None

    def test_assumption_challenge_model(self):
        from services.threatcasting.models import BackcastAssumptionChallenge
        ac = BackcastAssumptionChallenge(
            plan_id="plan-1", narrative_id="n-1",
            original_assumption="Rainfall > 800mm",
            challenged_assumption="Rainfall may drop to 600mm"
        )
        assert ac.outcome == "pending"
        assert ac.approved_by is None

    def test_assumption_challenge_create_model(self):
        from services.threatcasting.models import AssumptionChallengeCreate
        ac = AssumptionChallengeCreate(
            plan_id="plan-1", narrative_id="n-1",
            original_assumption="assumption",
            challenged_assumption="challenged"
        )
        assert ac.plan_id == "plan-1"

    def test_path_comparison_model(self):
        from services.threatcasting.models import BackcastPathComparison
        pc = BackcastPathComparison(
            location_id="loc-1", comparison_name="Test",
            narrative_ids=["n-1", "n-2"]
        )
        assert pc.auto_scores == {}
        assert pc.winner_narrative_id is None

    def test_path_comparison_create_model(self):
        from services.threatcasting.models import PathComparisonCreate
        pc = PathComparisonCreate(
            location_id="loc-1", comparison_name="Test",
            narrative_ids=["n-1", "n-2"]
        )
        assert len(pc.narrative_ids) == 2

    def test_path_comparison_scores_model(self):
        from services.threatcasting.models import PathComparisonScores
        pcs = PathComparisonScores(scores={"n-1": {"cost": 0.8, "time": 0.6}})
        assert pcs.scores["n-1"]["cost"] == 0.8


# ---------------------------------------------------------------------------
# PrincipleManager Tests
# ---------------------------------------------------------------------------

class TestPrincipleManager:
    def _make_manager(self):
        from services.threatcasting.principles import PrincipleManager
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return PrincipleManager(conn=mock_conn), mock_conn, mock_cursor

    def test_create_principle(self):
        pm, mock_conn, mock_cursor = self._make_manager()
        mock_cursor.fetchone.return_value = {
            "id": "p-1", "narrative_id": "n-1", "location_id": "loc-1",
            "principle_name": "Carbon Negative", "principle_type": "ecological",
            "is_active": True, "weight": 1.0
        }
        result = pm.create_principle(
            narrative_id="n-1", location_id="loc-1",
            principle_name="Carbon Negative", description="Net carbon",
            principle_type="ecological", metric_key="soil_carbon_delta"
        )
        assert result["principle_name"] == "Carbon Negative"
        mock_conn.commit.assert_called_once()

    def test_list_principles(self):
        pm, _, mock_cursor = self._make_manager()
        mock_cursor.fetchall.return_value = [
            {"id": "p-1", "principle_name": "Test", "narrative_title": "N1", "threat_name": "T1"}
        ]
        results = pm.list_principles(narrative_id="n-1")
        assert len(results) == 1

    def test_delete_principle(self):
        pm, mock_conn, mock_cursor = self._make_manager()
        mock_cursor.rowcount = 1
        result = pm.delete_principle("p-1")
        assert result is True
        mock_conn.commit.assert_called_once()

    def test_align_milestone_with_metric(self):
        pm, mock_conn, mock_cursor = self._make_manager()
        # Set fetchall for _get_principles_for_narrative
        mock_cursor.fetchall.return_value = [
            {"id": "p-1", "narrative_id": "n-1", "source_system": "metric",
             "metric_key": "soil_carbon_delta", "comparison_operator": "gte",
             "target_value": 0.0, "target_value_upper": None,
             "invert_direction": False, "principle_name": "Carbon",
             "principle_type": "ecological"}
        ]
        # fetchone side_effect: _get_milestone, _read_current_metric_value, upsert
        mock_cursor.fetchone.side_effect = [
            {"id": "m-1", "narrative_id": "n-1", "location_id": "loc-1"},
            (0.5,),
            {"id": "a-1", "milestone_id": "m-1", "principle_id": "p-1",
             "alignment_score": 1.0, "current_value": 0.5, "target_value": 0.0},
        ]
        results = pm.align_milestone("m-1")
        assert len(results) == 1
        assert results[0]["alignment_score"] == 1.0

    def test_align_milestone_with_crisp(self):
        pm, mock_conn, mock_cursor = self._make_manager()
        mock_cursor.fetchall.return_value = [
            {"id": "p-1", "narrative_id": "n-1", "source_system": "crisp",
             "crisp_dimension": "carbon_yield", "metric_key": None,
             "comparison_operator": "gte", "target_value": 70.0,
             "target_value_upper": None, "invert_direction": False,
             "principle_name": "CRISP", "principle_type": "sustainability"}
        ]
        mock_cursor.fetchone.side_effect = [
            {"id": "m-1", "narrative_id": "n-1", "location_id": "loc-1"},
            (85.0,),
            {"id": "a-1", "alignment_score": 1.0},
        ]
        results = pm.align_milestone("m-1")
        assert len(results) == 1

    def test_check_direction_toward(self):
        pm, _, mock_cursor = self._make_manager()
        mock_cursor.fetchall.return_value = [
            {"alignment_score": 0.8, "current_value": 0.8, "target_value": 1.0,
             "gap": -0.2, "principle_name": "P1", "invert_direction": False,
             "milestone_order": 1, "milestone_status": "completed"},
            {"alignment_score": 0.6, "current_value": 0.6, "target_value": 1.0,
             "gap": -0.4, "principle_name": "P2", "invert_direction": False,
             "milestone_order": 2, "milestone_status": "in_progress"},
        ]
        result = pm.check_direction("n-1")
        assert result["overall_direction"] == "toward"
        assert result["confidence"] > 0.5

    def test_check_direction_away(self):
        pm, _, mock_cursor = self._make_manager()
        mock_cursor.fetchall.return_value = [
            {"alignment_score": -0.8, "current_value": 0.2, "target_value": 1.0,
             "gap": -0.8, "principle_name": "P1", "invert_direction": False,
             "milestone_order": 1, "milestone_status": "completed"},
            {"alignment_score": -0.5, "current_value": 0.5, "target_value": 1.0,
             "gap": -0.5, "principle_name": "P2", "invert_direction": False,
             "milestone_order": 2, "milestone_status": "in_progress"},
        ]
        result = pm.check_direction("n-1")
        assert result["overall_direction"] == "away"

    def test_check_direction_mixed(self):
        pm, _, mock_cursor = self._make_manager()
        mock_cursor.fetchall.return_value = [
            {"alignment_score": 0.8, "current_value": 0.8, "target_value": 1.0,
             "gap": -0.2, "principle_name": "P1", "invert_direction": False,
             "milestone_order": 1, "milestone_status": "completed"},
            {"alignment_score": -0.5, "current_value": 0.5, "target_value": 1.0,
             "gap": -0.5, "principle_name": "P2", "invert_direction": False,
             "milestone_order": 2, "milestone_status": "in_progress"},
        ]
        result = pm.check_direction("n-1")
        assert result["overall_direction"] == "mixed"

    def test_check_direction_empty(self):
        pm, _, mock_cursor = self._make_manager()
        mock_cursor.fetchall.return_value = []
        result = pm.check_direction("n-1")
        assert result["overall_direction"] == "unknown"

    def test_automated_gap_analysis(self):
        pm, mock_conn, mock_cursor = self._make_manager()
        # fetchone side_effect: narrative/location lookup, then metric value read
        mock_cursor.fetchone.side_effect = [
            {"narrative_id": "n-1", "location_id": "loc-1"},
            (0.3,),
        ]
        # fetchall for principles
        mock_cursor.fetchall.return_value = [
            {"id": "p-1", "narrative_id": "n-1", "source_system": "metric",
             "metric_key": "soil_carbon_delta", "comparison_operator": "gte",
             "target_value": 0.0, "target_value_upper": None,
             "invert_direction": False, "principle_name": "Carbon",
             "principle_type": "ecological", "crisp_dimension": None, "weight": 1.0},
        ]
        result = pm.automated_gap_analysis("n-1")
        assert result["total_principles"] == 1
        assert "gaps" in result

    def test_compute_alignment_gte_met(self):
        pm, _, _ = self._make_manager()
        score = pm._compute_alignment(10.0, 5.0, None, "gte", False)
        assert score == 1.0

    def test_compute_alignment_gte_not_met(self):
        pm, _, _ = self._make_manager()
        score = pm._compute_alignment(3.0, 5.0, None, "gte", False)
        assert 0.0 <= score < 1.0

    def test_compute_alignment_lte_met(self):
        pm, _, _ = self._make_manager()
        score = pm._compute_alignment(3.0, 5.0, None, "lte", False)
        assert score == 1.0

    def test_compute_alignment_between_met(self):
        pm, _, _ = self._make_manager()
        score = pm._compute_alignment(5.0, 3.0, 7.0, "between", False)
        assert score == 1.0

    def test_compute_alignment_between_not_met(self):
        pm, _, _ = self._make_manager()
        score = pm._compute_alignment(10.0, 3.0, 7.0, "between", False)
        assert 0.0 <= score < 1.0

    def test_compute_alignment_invert(self):
        pm, _, _ = self._make_manager()
        # Invert flips the sign: lower current is better when invert=True
        score = pm._compute_alignment(2.0, 5.0, None, "gte", True)
        assert score < 0  # misaligned because invert flips

    def test_compute_alignment_no_data(self):
        pm, _, _ = self._make_manager()
        score = pm._compute_alignment(None, 5.0, None, "gte", False)
        assert score == 0.0

    def test_build_alignment_evidence(self):
        pm, _, _ = self._make_manager()
        evidence = pm._build_alignment_evidence(5.0, 5.0, "gte")
        assert "5.0" in evidence
        assert ">=" in evidence

    def test_build_alignment_evidence_no_data(self):
        pm, _, _ = self._make_manager()
        evidence = pm._build_alignment_evidence(None, 5.0, "gte")
        assert "No current data" in evidence

    def test_metric_read_uses_canonical_contract(self):
        pm, _, cursor = self._make_manager()
        cursor.fetchone.return_value = (12.5,)

        assert pm._read_current_metric_value("soil_carbon", "loc-1") == 12.5
        query = cursor.execute.call_args.args[0]
        assert "SELECT mv.value" in query
        assert "md.id = mv.metric_id" in query
        assert "ORDER BY mv.computed_at DESC" in query
        assert "numeric_value" not in query
        assert "recorded_at" not in query

    @pytest.mark.parametrize(
        ("dimension", "column"),
        [("carbon_yield", "carbon_yield_score"), ("climate", "climate_score"),
         ("policy", "policy_score"), ("financial", "financial_score"),
         ("implementation", "implementation_score"), ("composite", "composite_score")],
    )
    def test_crisp_dimension_maps_to_allowlisted_column(self, dimension, column):
        pm, _, cursor = self._make_manager()
        cursor.fetchone.return_value = (42,)

        assert pm._read_current_crisp_score(dimension, "loc-1") == 42
        query = cursor.execute.call_args.args[0]
        assert f"SELECT {column}" in query
        assert "ORDER BY score_computed_at DESC NULLS LAST" in query
        assert cursor.execute.call_args.args[1] == ("loc-1",)

    def test_crisp_dimension_rejects_unknown_column(self):
        pm, _, cursor = self._make_manager()
        with pytest.raises(ValueError, match="Unsupported CRISP dimension"):
            pm._read_current_crisp_score("rating; DROP TABLE", "loc-1")
        cursor.execute.assert_not_called()

    def test_effectiveness_delta_uses_canonical_metric_contract(self):
        pm, _, cursor = self._make_manager()
        cursor.fetchone.side_effect = [(10,), (12,)]

        assert pm._compute_effectiveness_delta("soil_carbon", "loc-1", date.today()) == 0.2
        queries = [call.args[0] for call in cursor.execute.call_args_list]
        assert all("SELECT mv.value" in query for query in queries)
        assert all("md.id = mv.metric_id" in query for query in queries)
        assert all("mv.computed_at" in query for query in queries)
        assert all("numeric_value" not in query and "recorded_at" not in query for query in queries)


# ---------------------------------------------------------------------------
# Backcaster Challenge Tests
# ---------------------------------------------------------------------------

class TestBackcasterChallenges:
    def _make_backcaster(self):
        from services.threatcasting.backcasting import Backcaster
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return Backcaster(conn=mock_conn), mock_conn, mock_cursor

    def test_challenge_assumption(self):
        bc, mock_conn, mock_cursor = self._make_backcaster()
        mock_cursor.fetchone.return_value = {
            "id": "ac-1", "plan_id": "plan-1", "narrative_id": "n-1",
            "original_assumption": "Original", "challenged_assumption": "Challenged",
            "outcome": "pending"
        }
        result = bc.challenge_assumption(
            plan_id="plan-1", narrative_id="n-1",
            original_assumption="Original", challenged_assumption="Challenged",
            reason="Trend analysis"
        )
        assert result["outcome"] == "pending"
        mock_conn.commit.assert_called_once()

    def test_list_challenges(self):
        bc, _, mock_cursor = self._make_backcaster()
        mock_cursor.fetchall.return_value = [
            {"id": "ac-1", "outcome": "pending", "narrative_title": "N1"}
        ]
        results = bc.list_challenges("plan-1")
        assert len(results) == 1

    def test_resolve_challenge_confirmed(self):
        bc, mock_conn, mock_cursor = self._make_backcaster()
        mock_cursor.fetchone.return_value = {
            "id": "ac-1", "outcome": "confirmed", "approved_by": "admin"
        }
        result = bc.resolve_challenge(
            challenge_id="ac-1", outcome="confirmed", approved_by="admin"
        )
        assert result["outcome"] == "confirmed"
        mock_conn.commit.assert_called_once()

    def test_resolve_challenge_rejected(self):
        bc, mock_conn, mock_cursor = self._make_backcaster()
        mock_cursor.fetchone.return_value = {
            "id": "ac-1", "outcome": "rejected", "approved_by": "admin"
        }
        result = bc.resolve_challenge(
            challenge_id="ac-1", outcome="rejected", approved_by="admin"
        )
        assert result["outcome"] == "rejected"

    def test_resolve_challenge_invalid_outcome(self):
        bc, _, _ = self._make_backcaster()
        with pytest.raises(ValueError, match="Invalid outcome"):
            bc.resolve_challenge(
                challenge_id="ac-1", outcome="invalid", approved_by="admin"
            )

    def test_resolve_challenge_no_approver(self):
        bc, _, _ = self._make_backcaster()
        with pytest.raises(ValueError, match="approved_by is required"):
            bc.resolve_challenge(
                challenge_id="ac-1", outcome="confirmed", approved_by=""
            )

    def test_resolve_challenge_not_found(self):
        bc, _, mock_cursor = self._make_backcaster()
        mock_cursor.fetchone.return_value = None
        with pytest.raises(ValueError, match="not found"):
            bc.resolve_challenge(
                challenge_id="ac-1", outcome="confirmed", approved_by="admin"
            )

    def test_get_challenge(self):
        bc, _, mock_cursor = self._make_backcaster()
        mock_cursor.fetchone.return_value = {"id": "ac-1", "outcome": "pending"}
        result = bc.get_challenge("ac-1")
        assert result is not None

    def test_get_challenge_not_found(self):
        bc, _, mock_cursor = self._make_backcaster()
        mock_cursor.fetchone.return_value = None
        result = bc.get_challenge("ac-1")
        assert result is None


# ---------------------------------------------------------------------------
# PathComparator Tests
# ---------------------------------------------------------------------------

class TestPathComparator:
    def _make_comparator(self):
        from services.threatcasting.path_comparison import PathComparator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return PathComparator(conn=mock_conn), mock_conn, mock_cursor

    def test_create_comparison(self):
        pc, mock_conn, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {
            "id": "cmp-1", "location_id": "loc-1", "comparison_name": "Test",
            "narrative_ids": ["n-1", "n-2"], "comparison_criteria": {}
        }
        result = pc.create_comparison(
            location_id="loc-1", comparison_name="Test",
            narrative_ids=["n-1", "n-2"]
        )
        assert result["comparison_name"] == "Test"
        mock_conn.commit.assert_called_once()

    def test_create_comparison_insufficient_narratives(self):
        pc, _, _ = self._make_comparator()
        with pytest.raises(ValueError, match="At least two"):
            pc.create_comparison(
                location_id="loc-1", comparison_name="Test",
                narrative_ids=["n-1"]
            )

    def test_list_comparisons(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchall.return_value = [
            {"id": "cmp-1", "comparison_name": "Test", "winner_title": None}
        ]
        results = pc.list_comparisons(location_id="loc-1")
        assert len(results) == 1

    def test_delete_comparison(self):
        pc, mock_conn, mock_cursor = self._make_comparator()
        mock_cursor.rowcount = 1
        result = pc.delete_comparison("cmp-1")
        assert result is True
        mock_conn.commit.assert_called_once()

    def test_score_cost_fewer_resources(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchall.return_value = [
            {"resource_requirements": "Tractor"},
        ]
        score = pc._score_cost(mock_cursor, "n-1")
        assert 0.0 <= score <= 1.0

    def test_score_cost_no_resources(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchall.return_value = []
        score = pc._score_cost(mock_cursor, "n-1")
        assert score == 0.5

    def test_score_time_short(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {
            "milestone_target_date": date.today() + timedelta(days=30)
        }
        score = pc._score_time(mock_cursor, "n-1")
        assert score > 0.9  # 30 days ≈ very high score

    def test_score_time_long(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {
            "milestone_target_date": date.today() + timedelta(days=365 * 6)
        }
        score = pc._score_time(mock_cursor, "n-1")
        assert score < 0.1  # 6 years ≈ very low score

    def test_score_risk_low(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {
            "severity_potential": "low", "probability": 0.2
        }
        score = pc._score_risk(mock_cursor, "n-1", "loc-1")
        assert score > 0.8

    def test_score_risk_high(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {
            "severity_potential": "critical", "probability": 0.9
        }
        score = pc._score_risk(mock_cursor, "n-1", "loc-1")
        assert score < 0.2

    def test_score_desirability_high(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {"desirability_score": 0.9}
        score = pc._score_desirability(mock_cursor, "n-1")
        assert score > 0.9

    def test_score_desirability_low(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {"desirability_score": -0.8}
        score = pc._score_desirability(mock_cursor, "n-1")
        assert score < 0.2

    def test_score_principle_alignment_high(self):
        pc, _, mock_cursor = self._make_comparator()
        mock_cursor.fetchone.return_value = {"avg_alignment": 0.8}
        score = pc._score_principle_alignment(mock_cursor, "n-1")
        assert score > 0.8

    def test_compute_final_scores(self):
        pc, _, _ = self._make_comparator()
        scores = {
            "n-1": {"cost": 0.8, "time": 0.6, "risk": 0.7, "desirability": 0.9, "principle_alignment": 0.85},
            "n-2": {"cost": 0.5, "time": 0.9, "risk": 0.4, "desirability": 0.6, "principle_alignment": 0.5},
        }
        criteria = {
            "cost": {"weight": 0.25}, "time": {"weight": 0.20},
            "risk": {"weight": 0.25}, "desirability": {"weight": 0.15},
            "principle_alignment": {"weight": 0.15},
        }
        final = pc._compute_final_scores(scores, criteria)
        assert final["n-1"] > final["n-2"]

    def test_build_rationale(self):
        pc, _, _ = self._make_comparator()
        scores = {"n-1": {"cost": 0.8}, "n-2": {"cost": 0.5}}
        final = {"n-1": 0.75, "n-2": 0.5}
        rationale = pc._build_rationale(["n-1", "n-2"], scores, final, "n-1")
        assert "Winner: n-1" in rationale
        assert "vs n-2" in rationale

    def test_build_rationale_no_winner(self):
        pc, _, _ = self._make_comparator()
        rationale = pc._build_rationale([], {}, {}, None)
        assert "No clear winner" in rationale


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestBackcastingEnhancementIntegration:
    def test_principle_with_metric_key(self):
        """Principle with metric_key should reference metric_definition."""
        from services.threatcasting.models import BackcastPrincipleCreate
        p = BackcastPrincipleCreate(
            narrative_id="n-1", location_id="loc-1",
            principle_name="Soil Carbon", description="Increase SOC",
            principle_type="ecological", metric_key="soil_carbon_delta",
            comparison_operator="gte", target_value=0.0
        )
        assert p.metric_key == "soil_carbon_delta"
        assert p.comparison_operator == "gte"

    def test_principle_with_crisp_dimension(self):
        """Principle with crisp_dimension should reference CRISP scoring."""
        from services.threatcasting.models import BackcastPrincipleCreate
        p = BackcastPrincipleCreate(
            narrative_id="n-1", location_id="loc-1",
            principle_name="Low Risk", description="Low CRISP risk",
            principle_type="sustainability", source_system="crisp",
            crisp_dimension="carbon_yield", target_value=80.0
        )
        assert p.source_system == "crisp"
        assert p.crisp_dimension == "carbon_yield"

    def test_alignment_score_range(self):
        """Alignment scores should be between -1 and 1."""
        from services.threatcasting.principles import PrincipleManager
        pm = PrincipleManager(conn=MagicMock())
        for op in ("gte", "gt", "lte", "lt", "between"):
            score = pm._compute_alignment(5.0, 5.0, 10.0 if op == "between" else None, op, False)
            assert -1.0 <= score <= 1.0

    def test_path_comparison_criteria_weights(self):
        """Criteria weights should affect final scoring."""
        from services.threatcasting.path_comparison import PathComparator
        pc = PathComparator(conn=MagicMock())
        scores = {"n-1": {"cost": 1.0, "time": 0.0}, "n-2": {"cost": 0.0, "time": 1.0}}

        # Cost-heavy criteria
        criteria1 = {"cost": {"weight": 0.8}, "time": {"weight": 0.2}}
        final1 = pc._compute_final_scores(scores, criteria1)

        # Time-heavy criteria
        criteria2 = {"cost": {"weight": 0.2}, "time": {"weight": 0.8}}
        final2 = pc._compute_final_scores(scores, criteria2)

        # n-1 should win with cost-heavy, n-2 with time-heavy
        assert final1["n-1"] > final1["n-2"]
        assert final2["n-2"] > final2["n-1"]

    def test_challenge_requires_human_approval(self):
        """Challenge resolution should require approved_by."""
        from services.threatcasting.backcasting import Backcaster
        bc = Backcaster(conn=MagicMock())
        with pytest.raises(ValueError, match="approved_by is required"):
            bc.resolve_challenge("ac-1", "confirmed", "")

    def test_invert_direction_flips_alignment(self):
        """invert_direction should flip alignment sign for metrics."""
        from services.threatcasting.principles import PrincipleManager
        pm = PrincipleManager(conn=MagicMock())
        # Without invert: current=2, target=5, gte → positive (partially aligned)
        score_normal = pm._compute_alignment(2.0, 5.0, None, "gte", False)
        # With invert: same values → negative (inverted)
        score_inverted = pm._compute_alignment(2.0, 5.0, None, "gte", True)
        assert score_normal > 0
        assert score_inverted < 0

    def test_effectiveness_delta_computation(self):
        """Delta should compare before/after milestone completion."""
        from services.threatcasting.principles import PrincipleManager
        pm = PrincipleManager(conn=MagicMock())
        assert pm._compute_effectiveness_delta(
            "soil_carbon", "loc-1", None
        ) is None  # No target date = None
