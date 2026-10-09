"""Tests for the Tactical Layer (chess-inspired governance tactics).

Covers fork, discovered double-check, pin, zwischenzug, promotion ladder.
All "propose" helpers must write DRAFT rows only (no autonomous state change).
Uses mocked DB cursors so no live database is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from services.analytics import pin_dependency, promotion_ladder
from services.events import fork_detector
from services.feedback import automation
from services.threatcasting import preempt


def _mock_conn(rows_by_query_fragment: dict):
    """Build a mock conn whose cursor returns rows based on query fragments."""
    cur = MagicMock()
    cur.__enter__ = lambda self: cur
    cur.__exit__ = lambda self, *a: None

    store = {"rows": []}

    def execute(query, params=None):
        store["rows"] = []
        for frag, rows in rows_by_query_fragment.items():
            if frag in query:
                store["rows"] = rows
                break

    cur.execute.side_effect = execute

    def fetchall():
        return store["rows"]

    cur.fetchall.side_effect = fetchall

    def fetchone():
        return {}

    cur.fetchone.side_effect = fetchone

    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


# --- Fork -----------------------------------------------------------------


def test_fork_detection_counts_related():
    rows = [
        {"source_event_id": "e1", "target_count": 3, "transfer_count": 3,
         "target_domains": ["irrigation", "planting", "energy"],
         "transfer_ids": ["t1", "t2", "t3"]},
    ]
    conn, _ = _mock_conn({"FROM insight_transfer": rows})
    result = fork_detector.detect_fork_opportunities(conn, location_id="L")
    assert result["fork_count"] == 1
    assert result["forks"][0]["target_count"] == 3


def test_propose_fork_writes_draft():
    rows = [
        {"source_event_id": "e1", "target_count": 3, "transfer_count": 3,
         "target_domains": ["irrigation", "planting", "energy"],
         "transfer_ids": ["t1", "t2", "t3"]},
    ]
    conn, cur = _mock_conn({"FROM insight_transfer": rows})
    result = fork_detector.propose_fork_opportunities(conn, location_id="L", actor="tester")
    # INSERT executed with status 'draft'
    assert cur.execute.called
    insert_sql = [c.args[0] for c in cur.execute.call_args_list if "INSERT INTO tactical_opportunity" in c.args[0]]
    assert insert_sql, "expected an INSERT into tactical_opportunity"
    assert "draft" in insert_sql[0]
    assert result["proposed_count"] == 1


# --- Discovered double-check -------------------------------------------------


def test_double_check_attaches_companions():
    flags = [
        {"id": "f1", "threat_id": "T1", "flag_name": "Drought",
         "indicator_type": "quantitative", "threshold_warning": 7.0,
         "threshold_critical": 10.0, "threshold_normal": 5.0,
         "comparison_operator": "gte", "unit": "mm", "data_source": "weather",
         "check_frequency_hours": 24, "last_checked_at": None,
         "last_value": 9.0, "threat_name": "Drought", "threat_type": "climate",
         "threat_severity": "high", "threat_probability": 0.7,
         "status": "warning"},
    ]
    companions = [
        {"flag_id": "f1", "source_threat_id": "T1", "target_threat_id": "T2",
         "target_threat_name": "Crop failure", "impact_type": "amplifies",
         "impact_magnitude": 0.7},
    ]
    conn, cur = _mock_conn({
        "FROM threat_flag tf": flags,
        "FROM threat_cross_impact ci": companions,
    })
    result = preempt.plan_preemptive_actions(conn, location_id="L")
    assert result["double_check_count"] == 1
    dc = result["double_checks"][0]
    assert dc["companion_threat_name"] == "Crop failure"
    assert dc["impact_type"] == "amplifies"


# --- Pin --------------------------------------------------------------------


def test_pin_detection_flags_unverified_metric():
    rows = [{"id": "m1", "location_id": "L", "metric_id": "M", "computed_at": "2026-01-01"}]
    conn, _ = _mock_conn({"FROM metric_value": rows})
    result = pin_dependency.detect_pin_blocks(conn, location_id="L")
    assert result["pin_count"] == 1
    assert result["pins"][0]["pinning_upstream"] == "metric_value.verified"
    assert result["pins"][0]["gate"] == "public_metric_view"


def test_propose_pin_writes_draft():
    rows = [{"id": "m1", "location_id": "L", "metric_id": "M", "computed_at": "2026-01-01"}]
    conn, cur = _mock_conn({"FROM metric_value": rows})
    result = pin_dependency.propose_pin_blocks(conn, location_id="L", actor="tester")
    insert_sql = [c.args[0] for c in cur.execute.call_args_list if "INSERT INTO tactical_opportunity" in c.args[0]]
    assert insert_sql
    assert "'pin'" in insert_sql[0] or '"pin"' in insert_sql[0]
    assert "draft" in insert_sql[0]
    assert result["proposed_count"] == 1


# --- Promotion ladder -------------------------------------------------------


def test_promotion_ladder_funnel():
    rows = [{
        "location_id": "L", "location_name": "Adelphi",
        "sensor_readings": 100, "verified_metrics": 10,
        "published_credits": 2, "issued_certificates": 1,
    }]
    conn, _ = _mock_conn({"FROM location l": rows})
    result = promotion_ladder.compute_promotion_ladder(conn, location_id="L")
    loc = result["locations"][0]
    assert loc["full_ladder"] is True
    assert loc["top_rung_reached"] is True
    assert len(loc["rungs"]) == 4


# --- Zwischenzug ------------------------------------------------------------


def test_zwischenzug_detection():
    rows = [{
        "outcome_id": "o1", "location_id": "L", "metric_key": "soil_moisture",
        "measured_value": 30.0, "feedback_applied": False,
    }]
    conn, _ = _mock_conn({"FROM action_outcome ao": rows})
    result = automation.detect_zwischenzug(conn, location_id="L")
    assert result["zwischenzug_count"] == 1
    assert result["signals"][0]["priority"] == "high"


def test_propose_zwischenzug_writes_draft():
    rows = [{
        "outcome_id": "o1", "location_id": "L", "metric_key": "soil_moisture",
        "measured_value": 30.0, "feedback_applied": False,
    }]
    conn, cur = _mock_conn({"FROM action_outcome ao": rows})
    result = automation.propose_zwischenzug(conn, location_id="L", actor="tester")
    insert_sql = [c.args[0] for c in cur.execute.call_args_list if "INSERT INTO tactical_opportunity" in c.args[0]]
    assert insert_sql
    assert "zwischenzug" in insert_sql[0]
    assert "draft" in insert_sql[0]
    assert result["proposed_count"] == 1
