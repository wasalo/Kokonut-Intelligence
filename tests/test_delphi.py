"""Tests for the Real-time Delphi service: consensus math, panel management,
facilitator orchestration, agent integration, and CLI smoke."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    type(mock_conn.cursor).return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestDelphiModels:
    def test_study_defaults(self):
        from services.delphi.models import DelphiStudy
        s = DelphiStudy(title="Test")
        assert s.variation == "real_time"
        assert s.status == "draft"
        assert s.facilitator_type == "agent"
        assert "iqr_threshold" in s.stopping_criteria

    def test_study_create_defaults(self):
        from services.delphi.models import DelphiStudyCreate
        s = DelphiStudyCreate(title="Test")
        assert s.stopping_criteria["min_participants"] == 3

    def test_panel_member_defaults(self):
        from services.delphi.models import DelphiPanelMember
        m = DelphiPanelMember(study_id="s1", display_token="P-ABC")
        assert m.is_anonymous is True
        assert m.expert_weight == 1.0
        assert m.role == "expert"

    def test_item_defaults(self):
        from services.delphi.models import DelphiItem
        i = DelphiItem(study_id="s1", label="Q1")
        assert i.item_type == "option"
        assert i.scale == "desirability"
        assert i.min_value == -1.0

    def test_contribution_defaults(self):
        from services.delphi.models import DelphiContribution
        c = DelphiContribution(study_id="s1", item_id="i1", panel_member_id="m1", score=0.5)
        assert c.score == 0.5

    def test_recommendation_defaults(self):
        from services.delphi.models import DelphiRecommendation
        r = DelphiRecommendation(study_id="s1", recommendation_text="Do X")
        assert r.status == "draft"


# ---------------------------------------------------------------------------
# Consensus math tests
# ---------------------------------------------------------------------------

class TestConsensusMath:
    def test_median_odd(self):
        from services.delphi.consensus import median
        assert median([1, 2, 3]) == 2.0

    def test_median_even(self):
        from services.delphi.consensus import median
        assert median([1, 2, 3, 4]) == 2.5

    def test_median_empty(self):
        from services.delphi.consensus import median
        assert median([]) is None

    def test_weighted_median(self):
        from services.delphi.consensus import weighted_median
        # Higher weight pulls median toward that value region
        assert weighted_median([1.0, 2.0, 3.0], [1, 1, 5]) == 3.0

    def test_weighted_median_empty(self):
        from services.delphi.consensus import weighted_median
        assert weighted_median([], []) is None

    def test_weighted_median_rejects_invalid_weights(self):
        from services.delphi.consensus import weighted_median
        with pytest.raises(ValueError):
            weighted_median([0.2, 0.8], [1.0])
        with pytest.raises(ValueError):
            weighted_median([0.2], [-1.0])

    def test_mean(self):
        from services.delphi.consensus import mean
        assert mean([2.0, 4.0]) == 3.0

    def test_stddev(self):
        from services.delphi.consensus import stddev
        assert stddev([2.0, 4.0]) == 1.0

    def test_stddev_single(self):
        from services.delphi.consensus import stddev
        assert stddev([5.0]) == 0.0

    def test_coefficient_of_variation(self):
        from services.delphi.consensus import coefficient_of_variation
        cv = coefficient_of_variation([2.0, 4.0])
        assert cv == 0.3333

    def test_cv_zero_mean(self):
        from services.delphi.consensus import coefficient_of_variation
        assert coefficient_of_variation([0.0, 0.0]) is None

    def test_iqr(self):
        from services.delphi.consensus import interquartile_range
        iqr = interquartile_range([1, 2, 3, 4, 5, 6, 7, 8, 9])
        # Q1=3, Q3=7 -> 4
        assert iqr == 4.0

    def test_iqr_small(self):
        from services.delphi.consensus import interquartile_range
        assert interquartile_range([1.0]) is None

    def test_stability_pct(self):
        from services.delphi.consensus import stability_pct
        stab = stability_pct(0.8, 2.0, 0.9, 2.1)
        assert stab is not None
        assert stab > 0

    def test_stability_pct_none(self):
        from services.delphi.consensus import stability_pct
        assert stability_pct(0.8, None, 0.9, 2.1) is None

    def test_consensus_reached_true(self):
        from services.delphi.consensus import consensus_reached
        assert consensus_reached(0.5, 5, 3, 1.0) is True

    def test_consensus_reached_false_iqr(self):
        from services.delphi.consensus import consensus_reached
        assert consensus_reached(2.0, 5, 3, 1.0) is False

    def test_consensus_reached_false_participants(self):
        from services.delphi.consensus import consensus_reached
        assert consensus_reached(0.5, 2, 3, 1.0) is False

    def test_calculator_compute(self):
        from services.delphi.consensus import ConsensusCalculator
        calc = ConsensusCalculator()
        result = calc.compute([0.2, 0.5, 0.8])
        assert result["participant_count"] == 3
        assert result["median"] == 0.5
        assert result["iqr"] is not None

    def test_calculator_compute_empty(self):
        from services.delphi.consensus import ConsensusCalculator
        calc = ConsensusCalculator()
        result = calc.compute([])
        assert result["participant_count"] == 0
        assert result["median"] is None

    def test_evaluate_stopping_consensus(self):
        from services.delphi.consensus import ConsensusCalculator
        calc = ConsensusCalculator()
        criteria = {"min_participants": 3, "iqr_threshold": 1.0, "stability_pct": 5.0, "max_duration_hours": 720}
        item = {"iqr": 0.5, "participant_count": 5, "median": 0.7}
        should_stop, detail = calc.evaluate_stopping(criteria, item, None)
        assert should_stop is True
        assert "consensus_reached" in detail["reasons"]
        assert detail["outcome"] == "consensus_reached"

    def test_evaluate_stopping_not_yet(self):
        from services.delphi.consensus import ConsensusCalculator
        calc = ConsensusCalculator()
        criteria = {"min_participants": 3, "iqr_threshold": 1.0, "stability_pct": 5.0, "max_duration_hours": 720}
        item = {"iqr": 3.0, "participant_count": 5, "median": 0.7}
        should_stop, detail = calc.evaluate_stopping(criteria, item, None)
        assert should_stop is False
        assert detail["outcome"] == "insufficient_stability_history"


# ---------------------------------------------------------------------------
# Facilitator flow tests
# ---------------------------------------------------------------------------

class TestFacilitatorFlow:
    def _make(self):
        from services.delphi.facilitator import Facilitator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return Facilitator(conn=mock_conn), mock_conn, mock_cursor

    def _seed_study(self, cur):
        cur.fetchone.side_effect = [
            {"id": "study-1", "location_id": "loc-1", "title": "Drought",
             "description": None, "variation": "real_time", "status": "open",
             "facilitator_type": "agent",
             "stopping_criteria": json.dumps({
                 "max_duration_hours": 720, "stability_pct": 5.0,
                 "min_participants": 3, "iqr_threshold": 1.0}),
             "created_by": None, "opened_at": None, "closed_at": None,
             "metadata": {}, "created_at": "2026-01-01", "updated_at": "2026-01-01"},
        ]

    def test_create_study(self):
        f, mock_conn, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {"id": "study-1", "status": "draft"}
        study = f.create_study(title="Test")
        assert study["status"] == "draft"
        mock_conn.commit.assert_called_once()

    def test_open_study(self):
        f, mock_conn, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {"id": "study-1", "status": "open"}
        study = f.open_study("study-1")
        assert study["status"] == "open"

    def test_submit_contribution_recomputes(self):
        f, mock_conn, mock_cursor = self._make()
        # item exists check, member exists check, contrib insert,
        # get_study inside recompute, snapshot upsert
        mock_cursor.fetchone.side_effect = [
            {"id": "item-1", "min_value": -1.0, "max_value": 1.0, "status": "open"},
            {"id": "member-1"},  # member belongs to study
            {"id": "contrib-1"},  # inserted contribution
            {"id": "study-1", "stopping_criteria": {
                "max_duration_hours": 720, "stability_pct": 5.0,
                "min_participants": 3, "iqr_threshold": 1.0}},
            {"id": "cons-1", "median": 0.5, "iqr": 0.0, "consensus_reached": False},
        ]
        mock_cursor.fetchall.side_effect = [
            [{"score": 0.5, "expert_weight": 1.0}],  # scores+weights
        ]
        result = f.submit_contribution("study-1", "item-1", "member-1", 0.5, "reason")
        assert "consensus" in result
        assert result["consensus"]["median"] == 0.5

    def test_submit_rejects_unknown_item(self):
        f, _, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = None  # item not found
        with pytest.raises(ValueError, match="does not belong to study"):
            f.submit_contribution("study-1", "item-x", "member-1", 0.5)

    def test_submit_rejects_closed_study(self):
        f, _, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {
            "id": "item-1", "min_value": -1.0, "max_value": 1.0, "status": "closed"
        }
        with pytest.raises(ValueError, match="not open"):
            f.submit_contribution("study-1", "item-1", "member-1", 0.5)

    def test_submit_rejects_score_outside_range(self):
        f, _, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {
            "id": "item-1", "min_value": 0.0, "max_value": 1.0, "status": "open"
        }
        with pytest.raises(ValueError, match="outside"):
            f.submit_contribution("study-1", "item-1", "member-1", 2.0)

    def test_live_summary(self):
        f, _, mock_cursor = self._make()
        # get_study returns study; items query; panel size; conflicting query
        study_dict = {"id": "study-1", "title": "Drought", "status": "open"}
        item_dict = {"item_id": "item-1", "label": "Q1", "scale": "desirability", "item_type": "option",
                     "median": 0.5, "iqr": 0.2, "stddev": 0.1, "cv": 0.2,
                     "participant_count": 3, "weighted_median": 0.5, "consensus_reached": True}
        conflicting_rows = [
            {"display_token": "P-AAA", "score": 0.2, "reasoning": "low"},
            {"display_token": "P-BBB", "score": 0.8, "reasoning": "high"},
        ]
        mock_cursor.fetchone.side_effect = [
            study_dict,       # get_study
            {"n": 2},         # panel_size
        ]
        mock_cursor.fetchall.side_effect = [
            [item_dict],      # items list
            conflicting_rows,  # conflicting contributions
        ]
        summary = f.get_live_summary("study-1")
        assert summary["title"] == "Drought"
        assert len(summary["items"]) == 1
        assert "conflicting_viewpoints" in summary

    def test_check_stopping(self):
        f, _, mock_cursor = self._make()
        study_dict = {"id": "study-1", "title": "D", "status": "open",
                      "stopping_criteria": json.dumps({
                          "max_duration_hours": 720, "stability_pct": 5.0,
                          "min_participants": 3, "iqr_threshold": 1.0}),
                      "opened_at": None}
        snap = {"item_id": "item-1", "median": 0.7, "iqr": 0.3, "participant_count": 5}
        mock_cursor.fetchone.side_effect = [
            study_dict,  # get_study
            None,        # previous history per item
        ]
        mock_cursor.fetchall.side_effect = [
            [snap],  # snapshots
        ]
        result = f.check_stopping("study-1")
        assert "should_stop" in result
        assert result["items"]

    def test_draft_recommendation(self):
        f, mock_conn, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {"id": "rec-1", "status": "draft"}
        rec = f.draft_recommendation("study-1", "Adopt median positions")
        assert rec["status"] == "draft"
        mock_conn.commit.assert_called_once()

    def test_approve_recommendation(self):
        f, mock_conn, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {"id": "rec-1", "status": "approved"}
        rec = f.approve_recommendation("rec-1", "human-1")
        assert rec["status"] == "approved"

    def test_approve_requires_human(self):
        f, _, _ = self._make()
        with pytest.raises(ValueError, match="approved_by is required"):
            f.approve_recommendation("rec-1", "")


# ---------------------------------------------------------------------------
# Panel manager tests
# ---------------------------------------------------------------------------

class TestPanelManager:
    def _make(self):
        from services.delphi.panel import PanelManager
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return PanelManager(conn=mock_conn), mock_conn, mock_cursor

    def test_add_member_generates_token(self):
        pm, mock_conn, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {"id": "m-1", "display_token": "P-XXXX"}
        member = pm.add_member("study-1", role="expert")
        assert member["display_token"].startswith("P-")
        mock_conn.commit.assert_called_once()

    def test_add_member_explicit_weight(self):
        pm, mock_conn, mock_cursor = self._make()
        mock_cursor.fetchone.return_value = {"id": "m-1", "display_token": "P-XXXX", "expert_weight": 2.0}
        member = pm.add_member("study-1", role="expert", expert_weight=2.0)
        assert member["expert_weight"] == 2.0

    def test_list_members(self):
        pm, _, mock_cursor = self._make()
        mock_cursor.fetchall.return_value = [
            {"id": "m-1", "display_token": "P-A", "is_anonymous": True,
             "expert_weight": 1.5, "role": "expert", "joined_at": "2026-01-01"},
        ]
        members = pm.list_members("study-1")
        assert len(members) == 1

    def test_remove_member(self):
        pm, mock_conn, mock_cursor = self._make()
        mock_cursor.rowcount = 1
        assert pm.remove_member("m-1") is True


# ---------------------------------------------------------------------------
# Agent integration tests
# ---------------------------------------------------------------------------

class TestDelphiAgent:
    def test_task_registered(self):
        from services.agents.tasks import get_task
        task = get_task("delphi_facilitation")
        assert "delphi_recommendation:draft" in task["writes"]
        assert task["high_risk"] is False

    def test_summarize_study(self):
        from services.agents.delphi_facilitator_agent import summarize_study
        from services.delphi.facilitator import Facilitator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        fac = Facilitator(conn=mock_conn)
        study_dict = {"id": "study-1", "title": "Drought", "status": "open"}
        item_dict = {"item_id": "item-1", "label": "Q1", "scale": "desirability", "item_type": "option",
                     "median": 0.5, "iqr": 0.2, "stddev": 0.1, "cv": 0.2,
                     "participant_count": 3, "weighted_median": 0.5, "consensus_reached": True}
        mock_cursor.fetchone.side_effect = [
            study_dict,
            {"n": 2},
        ]
        mock_cursor.fetchall.side_effect = [
            [item_dict],
            [],
        ]
        summary = summarize_study("study-1", fac)
        assert summary["title"] == "Drought"
        assert "synthesis" in summary

    def test_draft_recommendation_draft_only(self):
        from services.agents.delphi_facilitator_agent import draft_recommendation
        from services.delphi.facilitator import Facilitator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        fac = Facilitator(conn=mock_conn)
        mock_cursor.fetchone.return_value = {"id": "rec-1", "status": "draft"}
        rec = draft_recommendation("study-1", "Adopt medians", facilitator=fac)
        assert rec["status"] == "draft"

    def test_run_facilitation(self):
        from services.agents.delphi_facilitator_agent import run_delphi_facilitation
        from services.delphi.facilitator import Facilitator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        fac = Facilitator(conn=mock_conn)
        study_dict = {"id": "study-1", "title": "Drought", "status": "open"}
        item_dict = {"item_id": "item-1", "label": "Q1", "scale": "desirability", "item_type": "option",
                     "median": 0.5, "iqr": 0.2, "stddev": 0.1, "cv": 0.2,
                     "participant_count": 3, "weighted_median": 0.5, "consensus_reached": True}
        mock_cursor.fetchone.side_effect = [
            study_dict,
            {"n": 2},
            {"id": "rec-1", "status": "draft"},  # draft_recommendation insert
        ]
        mock_cursor.fetchall.side_effect = [
            [item_dict],
            [],
        ]
        output = run_delphi_facilitation("study-1", draft=True, facilitator=fac)
        assert "summary" in output
        assert "recommendation_draft" in output


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

class TestDelphiCLI:
    def test_cli_imports(self):
        import services.delphi.cli as cli
        assert hasattr(cli, "main")

    def test_package_import(self):
        import services.delphi
        assert hasattr(services.delphi, "Facilitator")
        assert hasattr(services.delphi, "PanelManager")
        assert hasattr(services.delphi, "ConsensusCalculator")
