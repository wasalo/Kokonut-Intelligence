"""Tests for financial planning / budgeting (FP&A)."""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.planning import budget
from services.workflow_specs.budget import BUDGET
from services.workflow_specs.validator import validate


def test_list_plans_uses_static_sql_and_treats_empty_status_as_unfiltered():
    cur = MagicMock()
    cur.__enter__.return_value = cur
    cur.fetchall.return_value = [{"id": uuid.UUID("10000000-0000-0000-0000-000000000001")}]
    conn = MagicMock()
    conn.cursor.return_value = cur

    result = budget.list_plans(conn, "10000000-0000-0000-0000-000000000002", status="")

    sql, params = cur.execute.call_args.args
    assert result == cur.fetchall.return_value
    assert "organization_id = %s" in sql
    assert "status::text = %s::text" in sql
    assert params == (
        uuid.UUID("10000000-0000-0000-0000-000000000002"),
        None,
        None,
    )


def test_budget_spec_validates():
    validate(BUDGET)
    assert BUDGET.states == frozenset({"draft", "approved", "active", "closed", "cancelled"})


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


@pytest.fixture
def org_id():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO organization (org_key, name) VALUES (%s, %s) RETURNING id",
                (str(uuid.uuid4()), "plan-test"),
            )
            oid = cur.fetchone()[0]
            conn.commit()
        yield str(oid)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM financial_plan WHERE organization_id = %s", (oid,))
            cur.execute("DELETE FROM organization WHERE id = %s", (oid,))
            conn.commit()
    finally:
        conn.close()


def test_plan_lifecycle_and_actuals(org_id):
    conn = _db()
    try:
        start = date.today()
        end = start + timedelta(days=365)
        plan = budget.create_plan(conn, org_id, "2026 Plan", str(start), str(end))
        assert plan["status"] == "draft"
        pid = str(plan["id"])

        budget.add_budget_line(conn, pid, "fertilizer", 1000.0, location_id=None)

        # Cannot activate before approval.
        with pytest.raises(ValueError):
            budget.activate(conn, pid, "planner")

        plan = budget.approve(conn, pid, "human reviewer")
        assert plan["status"] == "approved"
        plan = budget.activate(conn, pid, "planner")
        assert plan["status"] == "active"

        rollup = budget.actuals_rollup(conn, pid)
        assert len(rollup) == 1
        assert rollup[0]["category"] == "fertilizer"
        assert rollup[0]["planned"] == 1000.0

        plan = budget.close(conn, pid, "planner")
        assert plan["status"] == "closed"
    finally:
        conn.close()


def test_invalid_plan_transition_rejected(org_id):
    conn = _db()
    try:
        start = date.today()
        plan = budget.create_plan(conn, org_id, "Plan", str(start), str(start + timedelta(days=30)))
        pid = str(plan["id"])
        with pytest.raises(ValueError):
            budget.close(conn, pid, "planner")  # draft -> closed invalid
    finally:
        conn.close()
