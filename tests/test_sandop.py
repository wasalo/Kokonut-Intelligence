"""Tests for the S&OP cockpit (read-only)."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.planning import sandop


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
                (str(uuid.uuid4()), "sandop-test"),
            )
            oid = cur.fetchone()[0]
            conn.commit()
        yield str(oid)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM organization WHERE id = %s", (oid,))
            conn.commit()
    finally:
        conn.close()


def test_cockpit_returns_structure(org_id):
    conn = _db()
    try:
        result = sandop.cockpit(conn, org_id)
        assert result["organization_id"] == org_id
        assert "summary" in result
        assert isinstance(result["demand"], list)
        assert isinstance(result["capacity"], list)
        assert isinstance(result["financial_plans"], list)
        assert isinstance(result["budget_lines"], list)
    finally:
        conn.close()


def test_cockpit_uses_canonical_budget_line_amounts(org_id):
    conn = _db()
    plan_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO financial_plan
                   (organization_id, name, period_start, period_end)
                   VALUES (%s, 'S&OP budget contract', '2026-01-01', '2026-12-31')
                   RETURNING id""",
                (org_id,),
            )
            plan_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO budget_line (plan_id, category, amount)
                   VALUES (%s, 'training', 1250)""",
                (plan_id,),
            )
            conn.commit()
        result = sandop.cockpit(conn, org_id)
        assert result["budget_lines"][0]["planned_amount"] == 1250
        assert result["budget_lines"][0]["actual_amount"] == 0
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM financial_plan WHERE id = %s", (plan_id,))
        conn.commit()
        conn.close()
