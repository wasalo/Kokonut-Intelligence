"""Tests for the persuasive-technology overjustification guardrail.

Covers detect_overjustification_risk (reward-crowding-out diagnostic)
and its surfacing in the reward_calibration report. Advisory-only;
no governed state is written.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from services.analytics.reward_calibration import detect_overjustification_risk


def _mock_conn(query_rows: dict):
    """Build a mock conn whose cursor returns rows keyed by query fragment."""
    cur = MagicMock()
    cur.__enter__ = lambda self: cur
    cur.__exit__ = lambda self, *a: None
    store = {"rows": []}

    def execute(query, params=None):
        store["rows"] = []
        for frag, rows in query_rows.items():
            if frag in query:
                store["rows"] = rows
                break

    cur.execute.side_effect = execute

    def fetchall():
        return store["rows"]

    cur.fetchall.side_effect = fetchall

    def fetchone():
        return store["rows"][0] if store["rows"] else None

    cur.fetchone.side_effect = fetchone

    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


def _corr_row(metric_key, corr, count, method="extrinsic"):
    # (linked_metric_key, avg_metric, avg_tokens, sample_count, correlation)
    return (metric_key, 1.0, 10.0, count, corr, method)


def test_high_risk_when_extrinsic_only_and_high_corr():
    conn = _mock_conn({
        # distinct distribution_method -> extrinsic-only
        "SELECT DISTINCT distribution_method": [("extrinsic",)],
        # correlation query (HAVING COUNT(*) >= 2)
        "CORR(linked_metric_value, token_amount)": [
            _corr_row("soil_carbon_delta", 0.92, 5, "extrinsic"),
        ],
    })
    out = detect_overjustification_risk(conn, "L")
    assert out["risk_level"] == "high"
    assert out["has_merit_framing"] is False
    assert any(s["type"] == "extrinsic_only_framing" for s in out["signals"])
    assert any(s["type"] == "high_extrinsic_correlation" for s in out["signals"])
    assert out["recommendations"]


def test_low_risk_with_merit_framing():
    conn = _mock_conn({
        "SELECT DISTINCT distribution_method": [("merit_based",), ("extrinsic",)],
        "CORR(linked_metric_value, token_amount)": [
            _corr_row("soil_carbon_delta", 0.3, 5, "merit_based"),
        ],
    })
    out = detect_overjustification_risk(conn, "L")
    assert out["risk_level"] == "low"
    assert out["has_merit_framing"] is True
    assert out["signals"] == []
    assert out["recommendations"] == []


def test_unknown_when_no_distributions():
    conn = _mock_conn({
        "SELECT DISTINCT distribution_method": [],
        "CORR(linked_metric_value, token_amount)": [],
    })
    out = detect_overjustification_risk(conn, "L")
    assert out["risk_level"] == "unknown"


def test_medium_risk_extrinsic_only_no_high_corr():
    conn = _mock_conn({
        "SELECT DISTINCT distribution_method": [("extrinsic",)],
        "CORR(linked_metric_value, token_amount)": [
            _corr_row("crop_revenue", 0.4, 5, "extrinsic"),
        ],
    })
    out = detect_overjustification_risk(conn, "L")
    assert out["risk_level"] == "medium"
    assert out["recommendations"]


def test_report_surfaces_overjustification():
    from services.export import report_generator

    conn = _mock_conn({
        "SELECT name FROM location": [{"name": "Adelphi"}],
        "FROM v_public_reward_calibration": [],
        "SELECT reward_type, linked_metric_key": [],
        "SELECT DISTINCT distribution_method": [("extrinsic",)],
        "CORR(linked_metric_value, token_amount)": [
            _corr_row("soil_carbon_delta", 0.9, 5, "extrinsic"),
        ],
    })
    out = report_generator.generate_reward_calibration(conn, "L")
    assert "overjustification_risk" in out
    risk = out["overjustification_risk"]
    assert risk["risk_level"] == "high"


def test_diagnostic_does_not_write():
    written = []

    conn = _mock_conn({
        "SELECT DISTINCT distribution_method": [("extrinsic",)],
        "CORR(linked_metric_value, token_amount)": [
            _corr_row("soil_carbon_delta", 0.9, 5, "extrinsic"),
        ],
    })

    def _track_inserts(query, params=None):
        if str(query).strip().upper().startswith("INSERT"):
            written.append(query)
        return None

    conn.cursor.return_value.execute.side_effect = _track_inserts

    detect_overjustification_risk(conn, "L")
    assert written == [], "guardrail must not write governed state"
