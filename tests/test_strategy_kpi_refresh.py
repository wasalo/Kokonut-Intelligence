"""Tests for verified strategy KPI refresh."""

import uuid

import pytest

from services.analytics import strategy_kpi_refresh
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
