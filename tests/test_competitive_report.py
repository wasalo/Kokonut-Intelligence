"""Tests for competitive strategy reporting."""

import uuid
from unittest.mock import MagicMock

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


def test_clean_helper_converts_uuids():
    import uuid as _uuid
    mock_uuid = _uuid.uuid4()
    row = {"id": mock_uuid, "strategy_plan_id": "plan-1"}
    cleaned = competitive_report._clean(row)
    assert cleaned["id"] == str(mock_uuid)


def test_health_uses_migration_backed_projection_and_preserves_payload():
    plan_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    row = {
        "strategy_plan_id": plan_id,
        "scope_type": "organization",
        "scope_id": scope_id,
        "landscape_count": 2,
        "verified_landscape_count": 2,
        "average_force_pressure_score": 0.625,
        "unreviewed_material_signal_count": 1,
        "approved_position_count": 3,
        "verified_advantage_count": 4,
        "unlinked_advantage_count": 0,
        "partial_advantage_count": 2,
        "open_competitive_review_count": 1,
    }
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor

    result = competitive_report.health(conn, str(plan_id))

    sql, params = cursor.execute.call_args.args
    assert " ".join(sql.split()) == (
        "SELECT strategy_plan_id, scope_type, scope_id, landscape_count, "
        "verified_landscape_count, average_force_pressure_score, "
        "unreviewed_material_signal_count, approved_position_count, "
        "verified_advantage_count, unlinked_advantage_count, "
        "partial_advantage_count, open_competitive_review_count "
        "FROM v_strategy_competitive_health WHERE strategy_plan_id = %s::uuid"
    )
    assert params == (str(plan_id),)
    assert result == {
        **row,
        "strategy_plan_id": str(plan_id),
        "scope_id": str(scope_id),
    }


def test_health_raises_when_not_found():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="strategy competitive health not found"):
        competitive_report.health(mock_conn, "missing-plan")


def _competitive_report_projection_fixture(monkeypatch):
    plan_id = uuid.uuid4()
    landscape = {
        "id": uuid.uuid4(),
        "strategy_plan_id": plan_id,
        "scope_type": "location",
        "scope_id": uuid.uuid4(),
        "industry": "regenerative agriculture",
        "geography": "Dominican Republic",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "status": "verified",
        "confidence": "high",
        "summary": "Synthetic landscape",
        "created_by_party_id": uuid.uuid4(),
        "verified_by_party_id": uuid.uuid4(),
        "verified_at": "2026-10-01T12:00:00+00:00",
        "created_at": "2026-01-01T12:00:00+00:00",
        "updated_at": "2026-10-01T12:00:00+00:00",
    }
    position = {
        "id": uuid.uuid4(),
        "strategy_plan_id": plan_id,
        "landscape_id": landscape["id"],
        "target_type": "market_segment",
        "target_id": uuid.uuid4(),
        "target_name": "Community food networks",
        "customer_needs": "Reliable regenerative supply",
        "value_drivers": ["traceability", "resilience"],
        "value_proposition": "Locally grounded regenerative food",
        "differentiation": "Verified farm outcomes",
        "alternatives": ["conventional supply"],
        "excluded_scope": None,
        "geographic_scope": "Dominican Republic",
        "product_service_scope": "Farm produce",
        "position_score": 82.5,
        "confidence": "moderate",
        "status": "approved",
        "visibility": "limited",
        "created_by_party_id": uuid.uuid4(),
        "approved_by_party_id": uuid.uuid4(),
        "approved_at": "2026-10-02T12:00:00+00:00",
        "created_at": "2026-01-02T12:00:00+00:00",
        "updated_at": "2026-10-02T12:00:00+00:00",
    }
    advantage = {"advantage_id": uuid.uuid4(), "strategy_plan_id": plan_id}
    cursor = MagicMock()
    cursor.fetchall.side_effect = [[landscape], [position], [advantage]]
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    health = {"strategy_plan_id": str(plan_id), "landscape_count": 1}
    monkeypatch.setattr(competitive_report, "health", lambda _conn, _plan_id: health)
    result = competitive_report.report(conn, str(plan_id))
    return plan_id, landscape, position, cursor, result, health


def test_report_uses_migration_268_competitive_landscape_projection(monkeypatch):
    plan_id, landscape, _position, cursor, result, _health = (
        _competitive_report_projection_fixture(monkeypatch)
    )

    sql, params = cursor.execute.call_args_list[0].args
    assert " ".join(sql.split()) == (
        "SELECT id, strategy_plan_id, scope_type, scope_id, industry, geography, "
        "period_start, period_end, status, confidence, summary, created_by_party_id, "
        "verified_by_party_id, verified_at, created_at, updated_at "
        "FROM competitive_landscape WHERE strategy_plan_id = %s::uuid "
        "ORDER BY period_end DESC"
    )
    assert params == (str(plan_id),)
    assert result["landscapes"] == [competitive_report._clean(landscape)]


def test_report_uses_migration_269_strategy_position_projection(monkeypatch):
    plan_id, _landscape, position, cursor, result, _health = (
        _competitive_report_projection_fixture(monkeypatch)
    )

    sql, params = cursor.execute.call_args_list[1].args
    assert " ".join(sql.split()) == (
        "SELECT id, strategy_plan_id, landscape_id, target_type, target_id, target_name, "
        "customer_needs, value_drivers, value_proposition, differentiation, alternatives, "
        "excluded_scope, geographic_scope, product_service_scope, position_score, confidence, "
        "status, visibility, created_by_party_id, approved_by_party_id, approved_at, "
        "created_at, updated_at FROM strategy_position "
        "WHERE strategy_plan_id = %s::uuid ORDER BY target_name"
    )
    assert params == (str(plan_id),)
    assert result["positions"] == [competitive_report._clean(position)]
