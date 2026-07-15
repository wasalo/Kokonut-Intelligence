"""Tests for the Business Model Canvas service."""

import json

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import business_model_canvas as bmc


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
    assert hasattr(bmc, "create")
    assert hasattr(bmc, "list_canvas")
    assert hasattr(bmc, "get")
    assert hasattr(bmc, "update_block")
    assert hasattr(bmc, "create_version")
    assert hasattr(bmc, "list_versions")
    assert hasattr(bmc, "suggest")
    assert hasattr(bmc, "compute_health")


def test_create_and_list():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(
            conn, location_id=loc,
            canvas_name="Test Canvas",
            description="A test canvas",
            fiscal_year=2026,
            tags=["test"],
            created_by=None,
        )
        assert created["entity_type"] == "location"
        assert str(created["entity_id"]) == loc
        assert created["status"] == "draft"
        assert created["version"] == 1
        rows = bmc.list_canvas(conn, location_id=loc)
        assert any(str(r["id"]) == str(created["id"]) for r in rows)
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_get_with_children():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Child Test")
        canvas_id = str(created["id"])
        result = bmc.get(conn, canvas_id)
        assert result is not None
        assert result["canvas_name"] == "Child Test"
        assert "jobs" in result
        assert "pain_points" in result
        assert "gain_creators" in result
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_update_block():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Update Test")
        canvas_id = str(created["id"])
        items = [{"name": "Partner A", "type": "supplier"}]
        result = bmc.update_block(conn, canvas_id, "key_partners", items)
        assert result["id"]
        canvas = bmc.get(conn, canvas_id)
        assert canvas["key_partners"] == items
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_update_block_invalid():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Invalid Test")
        canvas_id = str(created["id"])
        with pytest.raises(ValueError, match="invalid block"):
            bmc.update_block(conn, canvas_id, "nonexistent_block", [])
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_version_snapshot():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Version Test")
        canvas_id = str(created["id"])
        bmc.update_block(conn, canvas_id, "key_partners", [{"name": "P1"}])
        v1 = bmc.create_version(conn, canvas_id, changes="Added partner", change_reason="Testing")
        assert v1["version"] == 1
        bmc.update_block(conn, canvas_id, "key_partners", [{"name": "P1"}, {"name": "P2"}])
        v2 = bmc.create_version(conn, canvas_id, changes="Added second partner")
        assert v2["version"] == 2
        versions = bmc.list_versions(conn, canvas_id)
        assert len(versions) == 2
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_suggest():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        out = bmc.suggest(conn, loc)
        assert "blocks" in out
        assert "generated_from" in out
        assert isinstance(out["blocks"], dict)
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_compute_health():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Health Test")
        canvas_id = str(created["id"])
        bmc.update_block(conn, canvas_id, "key_partners", [{"name": "P1"}, {"name": "P2"}])
        bmc.update_block(conn, canvas_id, "value_propositions", [{"desc": "V1"}])
        health = bmc.compute_health(conn, canvas_id)
        assert 0 <= health["health_score"] <= 100
        assert "breakdown" in health
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_get_nonexistent():
    conn = _db()
    try:
        result = bmc.get(conn, "00000000-0000-0000-0000-000000000000")
        assert result is None
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_entity_validation():
    with pytest.raises(ValueError, match="provide exactly one"):
        bmc._entity(None, None)
    with pytest.raises(ValueError, match="provide exactly one"):
        bmc._entity("org-id", "loc-id")
