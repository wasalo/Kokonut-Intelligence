"""Tests for the "good offense" features:

A. Preemptive Intervention Planner (services.threatcasting.preempt)
B. Forward Reserve Deployment / preempt_threshold (services.strategic_reserve.health)
C. Proactive advisory is documented as the existing forecast_based rule layer.

All proposals are DRAFT / human-approved; no autonomous action is asserted.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from services.strategic_reserve import health as srh
from services.threatcasting import preempt as pt

# ----------------------------------------------------------------------
# A. Preemptive Intervention Planner
# ----------------------------------------------------------------------

def test_operator_rising():
    assert pt._operator_rising("gte") is True
    assert pt._operator_rising("gt") is True
    assert pt._operator_rising("lte") is False
    assert pt._operator_rising("lt") is False
    assert pt._operator_rising(None) is False


def test_distance_direction():
    # rising is bad: higher value => larger positive distance
    assert pt._distance(8, 5, True) == 3.0
    assert pt._distance(3, 5, True) == -2.0
    # falling is bad: lower value => larger positive distance
    assert pt._distance(3, 5, False) == 2.0


def test_flag_status_warning_then_critical():
    flag = {"comparison_operator": "gte", "threshold_warning": 5, "threshold_critical": 9}
    assert pt._flag_status(flag, 3) == "normal"
    assert pt._flag_status(flag, 6) == "warning"
    assert pt._flag_status(flag, 10) == "critical"


def test_lead_time_hours_computable():
    flag = {
        "comparison_operator": "gte",
        "threshold_warning": 5.0,
        "threshold_critical": 9.0,
        "check_frequency_hours": 24,
    }
    # value=7 -> warn_dist=2, crit_dist=2 -> cycles_to_critical=1
    lt = pt._lead_time_hours(flag, 7.0, None)
    assert lt["computable"] is True
    assert lt["lead_time_hours"] == 24
    assert lt["margin_consumed_pct"] == 50.0


def test_lead_time_hours_incomplete():
    flag = {"comparison_operator": "gte", "threshold_warning": None, "threshold_critical": 9.0}
    lt = pt._lead_time_hours(flag, 7.0, None)
    assert lt["computable"] is False


def test_plan_preemptive_actions_filters_non_warning():
    flag_rows = [
        {
            "id": "f1", "threat_id": "t1", "flag_name": "Rainfall Deficit",
            "indicator_type": "quantitative", "threshold_critical": 9.0,
            "threshold_warning": 5.0, "threshold_normal": 3.0,
            "comparison_operator": "gte", "unit": "mm", "data_source": "weather",
            "check_frequency_hours": 24, "last_checked_at": None, "last_value": 6.0,
            "threat_name": "Drought", "threat_type": "climate", "threat_severity": "high",
            "threat_probability": 0.7,
        },
        {
            "id": "f2", "threat_id": "t2", "flag_name": "Normal Flag",
            "indicator_type": "quantitative", "threshold_critical": 9.0,
            "threshold_warning": 5.0, "threshold_normal": 3.0,
            "comparison_operator": "gte", "unit": "mm", "data_source": "weather",
            "check_frequency_hours": 24, "last_checked_at": None, "last_value": 2.0,
            "threat_name": "Calm", "threat_type": "climate", "threat_severity": "low",
            "threat_probability": 0.1,
        },
    ]
    conn = MagicMock()
    fake_cur = MagicMock()
    fake_cur.fetchall.return_value = flag_rows
    fake_cur.__enter__ = lambda self: self
    fake_cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = fake_cur

    result = pt.plan_preemptive_actions(conn, location_id=None)
    assert result["proposal_count"] == 1
    p = result["proposals"][0]
    assert p["status"] == "draft"
    assert p["requires_human_approval"] is True
    assert p["lead_time_hours"] == 24
    assert p["severity"] in ("low", "medium", "high")


def test_plan_preemptive_actions_no_writes():
    flag_rows = [{
        "id": "f1", "threat_id": "t1", "flag_name": "Deficit", "indicator_type": "q",
        "threshold_critical": 9.0, "threshold_warning": 5.0, "threshold_normal": 3.0,
        "comparison_operator": "gte", "unit": "mm", "data_source": "w",
        "check_frequency_hours": 24, "last_checked_at": None, "last_value": 6.0,
        "threat_name": "Drought", "threat_type": "climate", "threat_severity": "high",
        "threat_probability": 0.7,
    }]
    conn = MagicMock()
    fake_cur = MagicMock()
    fake_cur.fetchall.return_value = flag_rows
    fake_cur.__enter__ = lambda self: self
    fake_cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = fake_cur

    pt.plan_preemptive_actions(conn)
    # The planner must never commit or write governed state.
    conn.commit.assert_not_called()


# ----------------------------------------------------------------------
# B. Forward Reserve Deployment / preempt_threshold
# ----------------------------------------------------------------------

def test_preempt_value_multiplicative():
    assert srh._preempt_value("gt", 100.0, 0.8) == 80.0
    assert srh._preempt_value("lt", 30.0, 0.8) == 24.0
    assert srh._preempt_value("gt", 100.0, None) is None
    assert srh._preempt_value("eq", 100.0, 0.8) is None


def test_evaluate_trigger_preempt_proposed():
    reserve = {
        "trigger_metric_key": "carbon_reversal_risk",
        "trigger_operator": "gt",
        "trigger_threshold": 5.0,
        "preempt_threshold_pct": 0.8,
        "scope_id": None,
    }
    conn = MagicMock()
    fake_cur = MagicMock()
    # observed 4.0 -> not hard breach (4>5 False) but past preempt band (4>4.0)
    fake_cur.fetchone.return_value = {"value": 4.5, "computed_at": "2026-01-01"}
    fake_cur.__enter__ = lambda self: self
    fake_cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = fake_cur

    t = srh.evaluate_trigger(conn, reserve)
    assert t["breach"] is False
    assert t["preempt_proposed"] is True
    assert t["preempt_value"] == 4.0


def test_evaluate_trigger_preempt_not_proposed_when_breach():
    reserve = {
        "trigger_metric_key": "carbon_reversal_risk",
        "trigger_operator": "gt",
        "trigger_threshold": 5.0,
        "preempt_threshold_pct": 0.8,
        "scope_id": None,
    }
    conn = MagicMock()
    fake_cur = MagicMock()
    fake_cur.fetchone.return_value = {"value": 9.0, "computed_at": "2026-01-01"}
    fake_cur.__enter__ = lambda self: self
    fake_cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = fake_cur

    t = srh.evaluate_trigger(conn, reserve)
    assert t["breach"] is True
    assert t["release_proposed"] is True
    # When already breached, the forward-deployment flag is not separately raised.
    assert t["preempt_proposed"] is False


def test_evaluate_trigger_no_preempt_configured():
    reserve = {
        "trigger_metric_key": "carbon_reversal_risk",
        "trigger_operator": "gt",
        "trigger_threshold": 5.0,
        "preempt_threshold_pct": None,
        "scope_id": None,
    }
    conn = MagicMock()
    fake_cur = MagicMock()
    fake_cur.fetchone.return_value = {"value": 4.0, "computed_at": "2026-01-01"}
    fake_cur.__enter__ = lambda self: self
    fake_cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = fake_cur

    t = srh.evaluate_trigger(conn, reserve)
    assert t["breach"] is False
    assert t["preempt_proposed"] is False
    assert t["preempt_value"] is None
