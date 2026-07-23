"""Integration coverage for executable strategic portfolio selections."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.analytics import strategy_kernel
from services.planning import strategy_allocation


PARTY_ID = "b0000000-0000-0000-0000-000000002604"


def test_execute_rejects_unapproved_selection():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only approved"):
        strategy_allocation.execute_portfolio_selection(mock_conn, str(uuid.uuid4()))


def test_approve_rejects_non_recommended_selection():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only recommended"):
        strategy_allocation.approve_portfolio_selection(mock_conn, str(uuid.uuid4()), str(uuid.uuid4()))


def test_approved_portfolio_creates_work_and_capacity_reservation():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = plan_id = investment_id = selection_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Execution Test', 'collective') RETURNING id", (f"execution-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Execution Reviewer')", (PARTY_ID,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Execution plan", "2026-01-01", "2026-12-31", PARTY_ID)
        plan_id = str(plan["id"])
        strategy_allocation.create_policy(conn, plan_id)
        case = strategy_allocation.create_investment_case(conn, plan_id, "Funded field program", created_by_party_id=PARTY_ID, estimated_cost=250, required_capacity_hours=40, financial_score=80, strategic_fit_score=90)
        investment_id = str(case["id"])
        strategy_allocation.score_investment(conn, investment_id)
        portfolio = strategy_allocation.select_feasible_portfolio(conn, plan_id, created_by_party_id=PARTY_ID)
        selection_id = str(portfolio["id"])
        strategy_allocation.approve_portfolio_selection(conn, selection_id, PARTY_ID)
        executions = strategy_allocation.execute_portfolio_selection(conn, selection_id, executed_by_party_id=PARTY_ID)
        assert len(executions) == 1
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM work_item WHERE id = %s::uuid", (executions[0]["work_item_id"],))
            assert cur.fetchone()[0] == "draft"
            cur.execute("SELECT status, required_hours FROM operating_demand_signal WHERE id = %s::uuid", (executions[0]["demand_signal_id"],))
            demand = cur.fetchone()
            assert demand[0] == "submitted"
            assert float(demand[1]) == 40
        assert strategy_allocation.execute_portfolio_selection(conn, selection_id, executed_by_party_id=PARTY_ID) == []
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
