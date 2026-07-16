"""Tests for competitive strategy reporting."""

import uuid

import pytest

from services.analytics import competitive_report
from services.ingestion.base import get_db


def test_competitive_health_separates_external_position_state():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Report Test', 'collective') RETURNING id", (f"report-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO strategy_plan (scope_type, scope_id, name, planning_horizon_start, planning_horizon_end, diagnosis_summary, guiding_policy) VALUES ('organization', %s::uuid, 'Report plan', '2026-01-01', '2026-12-31', 'External state', 'Respond') RETURNING id", (org_id,))
            plan_id = str(cur.fetchone()[0])
        conn.commit()
        result = competitive_report.health(conn, plan_id)
        assert result["strategy_plan_id"] == plan_id
        assert result["landscape_count"] == 0
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
