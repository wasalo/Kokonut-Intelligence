"""Tests for competitive signal monitoring."""

import uuid

import pytest

from services.analytics import competitive_landscape, strategy_monitoring
from services.ingestion.base import get_db


def test_material_signal_creates_idempotent_review_task():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    landscape_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Monitor Test', 'collective') RETURNING id", (f"monitor-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO strategy_plan (scope_type, scope_id, name, planning_horizon_start, planning_horizon_end, diagnosis_summary, guiding_policy) VALUES ('organization', %s::uuid, 'Monitor plan', '2026-01-01', '2026-12-31', 'Monitor', 'Adapt') RETURNING id", (org_id,))
            plan_id = str(cur.fetchone()[0])
        conn.commit()
        landscape = competitive_landscape.create_landscape(conn, plan_id, "organization", org_id, "2026-01-01", "2026-12-31")
        landscape_id = str(landscape["id"])
        with conn.cursor() as cur:
            cur.execute("UPDATE competitive_landscape SET status = 'submitted' WHERE id = %s::uuid", (landscape_id,))
        conn.commit()
        competitive_landscape.record_signal(conn, landscape_id, "competitor", "test", "Material displacement signal", materiality="critical")
        assert len(strategy_monitoring.process_material_signals(conn)) == 1
        assert len(strategy_monitoring.process_material_signals(conn)) == 0
        assert strategy_monitoring.monitor_summary(conn, plan_id)["open_competitive_review_count"] == 1
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if landscape_id:
                cur.execute("DELETE FROM competitive_landscape WHERE id = %s::uuid", (landscape_id,))
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
