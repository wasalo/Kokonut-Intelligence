"""Tests for the capital-accounting module (Keynes-inspired, constructive only).

Covers capacity / diversion / capture diagnostics, DRAFT-only credit
enforcement via safety.py, and the composite report. All analytics are
advisory; the credit ledger may only be written as status='draft'.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from services.agents import safety
from services.capital import accounting_report, capacity, capture, credit, diversion


def _conn(fragments: dict):
    """Mock conn: fragments map to (fetchall_rows, fetchone_row)."""
    cur = MagicMock()
    cur.__enter__ = lambda self: cur
    cur.__exit__ = lambda self, *a: None
    store = {"rows": [], "one": None}

    def execute(query, params=None):
        for frag, (rows, one) in fragments.items():
            if frag in query:
                store["rows"] = rows
                store["one"] = one if one is not None else (rows[0] if rows else None)
                return
        store["rows"] = []
        store["one"] = None

    cur.execute.side_effect = execute
    cur.fetchall.side_effect = lambda: store["rows"]
    cur.fetchone.side_effect = lambda: store["one"]
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


# --- capacity -----------------------------------------------------------------

def test_assess_capacity_under_mobilized():
    conn = _conn({
        "FROM form_of_capital": [
            [{"capital_key": "financial", "name": "Financial Capital",
              "stock_estimate": 10, "output_capacity_estimate": 100,
              "mobilization_pct": 0.1}],
            None,
        ],
    })
    out = capacity.assess_capacity(conn, "L")
    assert out["under_mobilized_forms"] == ["financial"]
    assert out["forms"][0]["under_mobilized"] is True


def test_assess_capacity_derives_mobilization():
    conn = _conn({
        "FROM form_of_capital": [
            [{"capital_key": "natural", "name": "Natural Capital",
              "stock_estimate": 60, "output_capacity_estimate": 100,
              "mobilization_pct": None}],
            None,
        ],
    })
    out = capacity.assess_capacity(conn, "L")
    assert out["forms"][0]["mobilization_pct"] == 0.6
    assert out["under_mobilized_forms"] == []


# --- diversion ----------------------------------------------------------------

def test_diversion_index_healthy():
    conn = _conn({
        "COALESCE(SUM(amount),0) FROM expense_event": [
            [],  # fetchall not used; fetchone path
        ],
    })
    # Mock two sequential SUM queries via a sequence on fetchone.
    cur = MagicMock()
    cur.__enter__ = lambda self: cur
    cur.__exit__ = lambda self, *a: None
    seq = iter([(40.0,), (60.0,)])  # consumption, reinvestment
    cur.fetchone.side_effect = lambda: next(seq)
    cur.execute.return_value = None
    conn = MagicMock()
    conn.cursor.return_value = cur

    out = diversion.compute_diversion_index(conn, "L")
    assert out["consumption_value"] == 40.0
    assert out["reinvestment_value"] == 60.0
    assert out["diversion_index"] == 0.6
    assert out["healthy"] is True


# --- capture ------------------------------------------------------------------

def test_capture_risk_high_concentration():
    conn = _conn({
        # specific total-revenue query must precede generic 'FROM revenue_event'
        "COALESCE(SUM(amount),0) FROM revenue_event WHERE location_id": [
            [(100.0,)],
            (100.0,),
        ],
        "FROM revenue_event": [
            [("bigbuyer", 90.0)],  # top counterparty
            ("bigbuyer", 90.0),
        ],
        "FROM anti_capture_governance_policy": [
            [(2,)],  # policy count
            (2,),
        ],
    })
    out = capture.capture_risk(conn, "L")
    assert out["financial_top_counterparty_share"] == 0.9
    assert out["at_risk_forms"] == ["financial"]
    fin = [f for f in out["forms"] if f["capital_key"] == "financial"][0]
    assert fin["capture_risk_level"] == "high"


# --- credit ledger (DRAFT-only) ----------------------------------------------

def test_propose_credit_creates_draft():
    cur = MagicMock()
    cur.__enter__ = lambda self: cur
    cur.__exit__ = lambda self, *a: None
    cur.fetchone.return_value = ("rcl-id-1", "draft")
    cur.execute.return_value = None
    conn = MagicMock()
    conn.cursor.return_value = cur

    out = credit.propose_credit(
        conn, "L", "carbon_credit_surplus", 50.0,
        idempotency_key="idem-1",
    )
    assert out["credit_status"] == "draft"
    # status was forced to draft in the SQL
    args, _ = cur.execute.call_args
    assert "draft" in args[0]


def test_propose_credit_rejects_settled_payload():
    # assert_agent_action_allowed raises for non-draft status
    try:
        safety.assert_agent_action_allowed(
            "create", "regenerative_credit_ledger", {"status": "settled"}
        )
        raised = False
    except ValueError:
        raised = True
    assert raised, "non-draft credit write must be blocked"


def test_credit_invalid_source_type():
    conn = MagicMock()
    raised = False
    try:
        credit.propose_credit(conn, "L", "bogus", 10.0)
    except ValueError:
        raised = True
    assert raised


def test_credit_capacity_read_only():
    cur = MagicMock()
    cur.__enter__ = lambda self: cur
    cur.__exit__ = lambda self, *a: None
    cur.fetchone.return_value = (250.0, 3)
    cur.execute.return_value = None
    conn = MagicMock()
    conn.cursor.return_value = cur

    out = credit.credit_capacity(conn, "L")
    assert out["draft_credit_total"] == 250.0
    assert out["draft_credit_count"] == 3
    assert "human confirmation" in out["note"]


# --- composite report ----------------------------------------------------------

def test_accounting_report_composes_sections():
    conn = _conn({
        "FROM form_of_capital": [
            [{"capital_key": "financial", "name": "Financial Capital",
              "stock_estimate": 10, "output_capacity_estimate": 100,
              "mobilization_pct": 0.1}],
            None,
        ],
        # specific revenue-total query MUST precede generic 'FROM revenue_event'
        "COALESCE(SUM(amount),0) FROM revenue_event WHERE location_id": [
            [(100.0,)],
            (100.0,),
        ],
        "FROM revenue_event": [
            [("bigbuyer", 90.0)],
            ("bigbuyer", 90.0),
        ],
        "FROM anti_capture_governance_policy": [
            [(1,)],
            (1,),
        ],
        "COALESCE(SUM(withheld_amount),0), COUNT(*) FROM regenerative_credit_ledger": [
            [(10.0, 1)],
            (10.0, 1),
        ],
        "SELECT * FROM regenerative_credit_ledger WHERE": [
            [{"id": "x", "credit_status": "draft", "withheld_amount": 10.0}],
            None,
        ],
        "COALESCE(SUM(amount),0) FROM expense_event": [
            [],
            None,
        ],
    })
    out = accounting_report.build_capital_accounting(conn, "L")
    assert out["report_type"] == "capital_accounting"
    assert out["advisory_only"] is True
    assert "capacity" in out["sections"]
    assert "diversion" in out["sections"]
    assert "capture_risk" in out["sections"]
    assert "credit_ledger" in out["sections"]
    assert out["errors"] == []
