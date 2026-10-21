"""Tests for the VSM value-stream analytics module."""

from unittest.mock import MagicMock

import psycopg2
import pytest

from services.analytics import value_stream as vs
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def test_module_shape():
    assert len(vs._PIPELINE) == 8
    assert set(vs.STAGES) == {"draft", "submitted", "verified", "published", "rejected"}
    assert vs.STAGES["published"]["class"] == "VA"
    assert vs.STAGES["rejected"]["class"] == "NVA"


def test_current_state_map_structure():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM location LIMIT 1")
            row = cur.fetchone()
        loc = str(row[0]) if row else None

        wip = vs.wip_by_stage(conn, loc)
        assert isinstance(wip, list)
        for item in wip:
            assert {"entity_type", "status", "wip"} <= set(item)

        lead = vs.stage_lead_times(conn, loc)
        assert isinstance(lead, list)

        fty = vs.first_time_through(conn, loc)
        assert {"published_count", "first_time_through", "pct"} <= set(fty)

        bottleneck = vs.bottleneck_ranking(conn, loc)
        assert isinstance(bottleneck, list)
        if bottleneck:
            assert {"entity_type", "wip", "pct_of_total"} <= set(bottleneck[0])

        full = vs.current_state_map(conn, loc)
        assert {"scope", "stages", "wip_by_stage", "stage_lead_times_days",
                "first_time_through_yield", "bottleneck_ranking"} <= set(full)
    except psycopg2.ProgrammingError:
        pytest.skip("value-stream tables not present (migrations not applied)")
    finally:
        conn.close()


def test_report_generator_entrypoint():
    conn = _db()
    try:
        out = vs.generate_value_stream_map(conn, None)
        assert isinstance(out, dict)
        assert "bottleneck_ranking" in out
    except psycopg2.ProgrammingError:
        pytest.skip("value-stream tables not present (migrations not applied)")
    finally:
        conn.close()


def test_wip_query_keeps_pipeline_location_and_review_status_rules():
    cur = MagicMock()
    cur.fetchall.return_value = [{"entity_type": "farm_activity", "status": "draft", "wip": 2}]
    conn = MagicMock()
    conn.cursor.return_value = cur

    result = vs.wip_by_stage(conn, "location-1")

    sql, params = cur.execute.call_args.args
    assert result == [{"entity_type": "farm_activity", "status": "draft", "wip": 2}]
    assert params == ("location-1",)
    assert "farm_activity_source_eligible_for_use" in sql
    assert "entity.review_status::text" in sql
    assert "FROM ai_summary AS entity CROSS JOIN scope\n            WHERE scope.loc IS NULL" in sql
    assert "FROM agent_task AS entity CROSS JOIN scope\n            WHERE scope.loc IS NULL" in sql
    assert "entity.location_id = scope.loc" in sql


def test_lead_time_query_uses_location_cte_and_exact_named_parameters():
    cur = MagicMock()
    cur.fetchall.return_value = [{"entity_type": "farm_activity", "avg_lead_days": 2.5}]
    conn = MagicMock()
    conn.cursor.return_value = cur

    result = vs.stage_lead_times(
        conn,
        "location-1",
        "2026-01-01",
        "2026-01-31",
        initial_status="submitted",
        goal_status="verified",
        entity_type="farm_activity",
    )

    sql, params = cur.execute.call_args.args
    assert result == [{"entity_type": "farm_activity", "avg_lead_days": 2.5}]
    assert params == {
        "loc": "location-1",
        "ps": "2026-01-01",
        "pe": "2026-01-31",
        "goal": "verified",
        "initial": "submitted",
        "etype": "farm_activity",
    }
    assert "farm_activity_source_eligible_for_use" in sql
    assert "scope.loc IS NULL OR entity.location_id = scope.loc" in sql
    assert "lt.entity_type = %(etype)s" in sql


def test_first_time_through_query_uses_location_cte_and_exact_named_parameters():
    cur = MagicMock()
    cur.fetchone.return_value = {"published_count": 4, "first_time_through": 3}
    conn = MagicMock()
    conn.cursor.return_value = cur

    result = vs.first_time_through(
        conn,
        "location-1",
        "2026-01-01",
        "2026-01-31",
        goal_status="verified",
        fail_status="rejected",
        entity_type="farm_activity",
    )

    sql, params = cur.execute.call_args.args
    assert result == {
        "published_count": 4,
        "first_time_through": 3,
        "pct": 75.0,
    }
    assert params == {
        "loc": "location-1",
        "ps": "2026-01-01",
        "pe": "2026-01-31",
        "goal": "verified",
        "fail": "rejected",
        "etype": "farm_activity",
    }
    assert "farm_activity_source_eligible_for_use" in sql
    assert "scope.loc IS NULL OR entity.location_id = scope.loc" in sql
    assert "lt.entity_type = %(etype)s" in sql


def test_lead_time_empty_entity_type_keeps_the_unfiltered_behavior():
    cur = MagicMock()
    cur.fetchall.return_value = []
    conn = MagicMock()
    conn.cursor.return_value = cur

    vs.stage_lead_times(conn, entity_type="")

    _sql, params = cur.execute.call_args.args
    assert params["etype"] is None
