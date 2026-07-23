"""Tests for verified strategy KPI refresh."""

import uuid

import pytest

from services.analytics import strategy_kpi_refresh
from services.analytics import strategy_kernel
from services.ingestion.base import get_db


def test_refresh_uses_verified_metric_value():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    objective_id = None
    metric_id = None
    kpi_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO objective (objective_name, target_value, status) VALUES ('KPI refresh test', 100, 'proposed') RETURNING id", )
            objective_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO metric_definition (metric_key, display_name, data_type) VALUES (%s, 'KPI refresh metric', 'numeric') RETURNING id", (f"kpi-refresh-{uuid.uuid4().hex[:8]}",))
            metric_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO objective_kpi (objective_id, metric_definition_id, target_value, direction) VALUES (%s::uuid, %s::uuid, 100, 'gte') RETURNING id", (objective_id, metric_id))
            kpi_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO metric_value (metric_id, value, verified, verified_by, verified_at, computed_at) VALUES (%s::uuid, 120, TRUE, %s::uuid, NOW(), NOW())", (metric_id, str(uuid.uuid4())))
        conn.commit()
        refreshed = strategy_kpi_refresh.refresh_objective_kpis(conn, objective_id)
        assert refreshed[0]["source_status"] == "verified"
        assert refreshed[0]["variance_status"] == "on_track"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if objective_id:
                cur.execute("DELETE FROM objective WHERE id = %s::uuid", (objective_id,))
            if metric_id:
                cur.execute("DELETE FROM metric_value WHERE metric_id = %s::uuid", (metric_id,))
                cur.execute("DELETE FROM metric_definition WHERE id = %s::uuid", (metric_id,))
        conn.commit()
        conn.close()


def test_variance_gte_at_risk():
    assert strategy_kpi_refresh._variance(80, 100, "gte") == "at_risk"
    assert strategy_kpi_refresh._variance(100, 100, "gte") == "on_track"
    assert strategy_kpi_refresh._variance(50, 100, "gte") == "breach"


def test_variance_lte_inverts_direction():
    assert strategy_kpi_refresh._variance(120, 100, "lte") == "at_risk"
    assert strategy_kpi_refresh._variance(100, 100, "lte") == "on_track"
    assert strategy_kpi_refresh._variance(100, 50, "lte") == "breach"


def test_variance_unknown_direction():
    assert strategy_kpi_refresh._variance(100, 100, "eq") == "on_track"
    assert strategy_kpi_refresh._variance(100, 200, "eq") == "breach"


def test_variance_none_values():
    assert strategy_kpi_refresh._variance(None, 100, "gte") == "not_measurable"
    assert strategy_kpi_refresh._variance(100, None, "gte") == "not_measurable"
    assert strategy_kpi_refresh._variance(None, None, "gte") == "not_measurable"


def test_refresh_creates_one_kpi_breach_review_task():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    objective_id = metric_id = org_id = plan_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'KPI Breach Test', 'collective') RETURNING id", (f"kpi-breach-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO objective (objective_name, target_value, status) VALUES ('KPI breach test', 200, 'proposed') RETURNING id")
            objective_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO metric_definition (metric_key, display_name, data_type) VALUES (%s, 'KPI breach metric', 'numeric') RETURNING id", (f"kpi-breach-{uuid.uuid4().hex[:8]}",))
            metric_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO objective_kpi (objective_id, metric_definition_id, target_value, direction) VALUES (%s::uuid, %s::uuid, 200, 'gte')", (objective_id, metric_id))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "KPI breach plan", "2026-01-01", "2026-12-31")
        plan_id = str(plan["id"])
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO strategy_map
                (entity_type, entity_id, perspective, strategy_plan_id, objective_id, statement)
                VALUES ('organization', %s::uuid, 'internal_process', %s::uuid, %s::uuid, 'Monitor KPI')""", (org_id, plan_id, objective_id))
            cur.execute("INSERT INTO metric_value (metric_id, value, verified, verified_by, verified_at, computed_at) VALUES (%s::uuid, 120, TRUE, %s::uuid, NOW(), NOW())", (metric_id, str(uuid.uuid4())))
        conn.commit()
        refreshed = strategy_kpi_refresh.refresh_objective_kpis(conn, objective_id)
        assert refreshed[0]["variance_status"] == "breach"
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), review_task_id FROM strategy_kpi_refresh_log WHERE objective_kpi_id = %s::uuid GROUP BY review_task_id", (refreshed[0]["id"],))
            count, task_id = cur.fetchone()
            assert count == 1 and task_id is not None
            cur.execute("SELECT review_type FROM strategy_review_task WHERE id = %s::uuid", (task_id,))
            assert cur.fetchone()[0] == "kpi_breach"
        strategy_kpi_refresh.refresh_objective_kpis(conn, objective_id)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM strategy_review_task WHERE strategy_plan_id = %s::uuid AND review_type = 'kpi_breach'", (plan_id,))
            assert cur.fetchone()[0] == 1
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if objective_id:
                cur.execute("DELETE FROM objective WHERE id = %s::uuid", (objective_id,))
            if metric_id:
                cur.execute("DELETE FROM metric_value WHERE metric_id = %s::uuid", (metric_id,))
                cur.execute("DELETE FROM metric_definition WHERE id = %s::uuid", (metric_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
