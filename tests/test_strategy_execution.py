"""Tests for strategy execution rollups and snapshots."""

import uuid

import pytest

from services.analytics import strategy_execution, strategy_kernel
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002605"


def test_calculate_variance_zero_planned():
    result = strategy_execution.calculate_variance(0, 10)
    assert result["status"] == "breach"


def test_calculate_variance_negative_values():
    result = strategy_execution.calculate_variance(-100, -105)
    assert result["status"] == "within_tolerance"
    assert result["variance_value"] == -5.0


def test_calculate_variance_negative_planned():
    result = strategy_execution.calculate_variance(-100, -120)
    assert result["status"] == "warning"


def test_complete_review_task_rejects_invalid_decision():
    with pytest.raises(ValueError, match="invalid strategy review decision"):
        strategy_execution.complete_review_task(None, str(uuid.uuid4()), str(uuid.uuid4()), "maybe")


def test_execution_dashboard_can_be_snapshotted():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Execution Test', 'collective') RETURNING id", (f"execution-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Execution Reviewer')", (PARTY_ID,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Execution plan", "2026-01-01", "2026-12-31", PARTY_ID)
        plan_id = str(plan["id"])
        dashboard = strategy_execution.dashboard(conn, strategy_plan_id=plan_id)
        assert dashboard[0]["objective_count"] == 0
        snapshot = strategy_execution.capture_snapshot(conn, plan_id, captured_by_party_id=PARTY_ID, review_note="Initial baseline")
        assert snapshot["strategy_plan_id"] == plan_id
        assert len(strategy_execution.list_snapshots(conn, plan_id)) == 1
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
