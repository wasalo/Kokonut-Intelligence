"""Tests for the VSM value-stream analytics module."""

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import value_stream as vs


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
