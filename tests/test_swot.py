"""Tests for the SWOT analysis service (business-plan section)."""

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import swot


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


def test_module_shape():
    assert hasattr(swot, "create")
    assert hasattr(swot, "list_swot")
    assert hasattr(swot, "suggest")


def test_create_and_list():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = swot.create(
            conn, location_id=loc,
            strengths=["Strong soil carbon"], threats=["Drought"],
            created_by=None,
        )
        assert created["entity_type"] == "location"
        assert str(created["entity_id"]) == loc
        assert created["status"] == "draft"
        rows = swot.list_swot(conn, location_id=loc)
        assert any(str(r["id"]) == str(created["id"]) for r in rows)
    except psycopg2.ProgrammingError:
        pytest.skip("swot_analysis table not present (migration not applied)")
    finally:
        conn.close()


def test_suggest_runs():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        out = swot.suggest(conn, location_id=loc)
        assert {"strengths", "weaknesses", "opportunities", "threats"} <= set(out)
    except psycopg2.ProgrammingError:
        pytest.skip("swot_analysis table not present (migration not applied)")
    finally:
        conn.close()
