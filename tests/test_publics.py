"""Tests for Publics & Market Segmentation service."""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import psycopg2

SCHEMA = Path("schemas/postgres/205_publics_market_segmentation.sql")


def _db():
    try:
        from services.ingestion.base import get_db
        return get_db()
    except psycopg2.OperationalError as exc:
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


# --- Module shape ---

def test_module_has_add_public():
    from services.analytics import publics
    assert hasattr(publics, "add_public")


def test_module_has_list_publics():
    from services.analytics import publics
    assert hasattr(publics, "list_publics")


def test_module_has_create_segment():
    from services.analytics import publics
    assert hasattr(publics, "create_segment")


def test_module_has_influence_interest_matrix():
    from services.analytics import publics
    assert hasattr(publics, "influence_interest_matrix")


def test_module_has_suggest():
    from services.analytics import publics
    assert hasattr(publics, "suggest")


# --- Schema validation ---

def test_schema_file_exists():
    assert SCHEMA.exists(), f"{SCHEMA} does not exist"


def test_schema_defines_stakeholder_public():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS stakeholder_public" in text


def test_schema_defines_market_segment():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS market_segment" in text


def test_schema_has_public_type_check():
    text = SCHEMA.read_text()
    assert "'financial'" in text
    assert "'government'" in text
    assert "'citizen_action'" in text


def test_schema_has_segment_type_check():
    text = SCHEMA.read_text()
    assert "'consumer'" in text
    assert "'business'" in text
    assert "'export'" in text


def test_schema_has_views():
    text = SCHEMA.read_text()
    assert "v_publics_matrix" in text
    assert "v_market_segment_summary" in text


# --- Validation ---

def test_add_public_invalid_type():
    from services.analytics import publics
    conn = MagicMock()
    with pytest.raises(ValueError, match="public_type"):
        publics.add_public(conn, "loc-id", "invalid", "Test")


def test_add_public_invalid_stance():
    from services.analytics import publics
    conn = MagicMock()
    with pytest.raises(ValueError, match="stance"):
        publics.add_public(conn, "loc-id", "financial", "Test", stance="invalid")


def test_create_segment_invalid_type():
    from services.analytics import publics
    conn = MagicMock()
    with pytest.raises(ValueError, match="segment_type"):
        publics.create_segment(conn, "loc-id", "invalid", "Test")


# --- Matrix (no DB) ---

def test_influence_interest_matrix_empty():
    from services.analytics import publics
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = publics.influence_interest_matrix(mock_conn, str(uuid.uuid4()))
    assert "key_player" in result
    assert "monitor" in result
    assert len(result["key_player"]) == 0


# --- DB integration ---

def test_add_and_list_publics():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import publics
        created = publics.add_public(conn, loc, "government", "Local Municipality",
                                     influence_score=8.0, interest_score=6.0)
        assert created["public_type"] == "government"
        assert created["influence_score"] == 8.0
        rows = publics.list_publics(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in rows)
    finally:
        conn.close()


def test_create_segment():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import publics
        created = publics.create_segment(conn, loc, "business", "Organic Buyers",
                                         description="Premium organic market",
                                         size_estimate=500.0)
        assert created["segment_type"] == "business"
        assert created["name"] == "Organic Buyers"
        rows = publics.list_segments(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in rows)
    finally:
        conn.close()


def test_suggest_returns_dict():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import publics
        result = publics.suggest(conn, loc)
        assert "publics" in result
        assert "segments" in result
        assert isinstance(result["publics"], list)
        assert isinstance(result["segments"], list)
    finally:
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
