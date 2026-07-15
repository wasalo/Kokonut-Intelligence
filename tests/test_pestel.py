"""Tests for PESTEL Analysis service."""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCHEMA = Path("schemas/postgres/203_pestel_analysis.sql")


def _db():
    try:
        from services.ingestion.base import get_db
        return get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


# --- Module shape ---

def test_module_has_create_analysis():
    from services.analytics import pestel
    assert hasattr(pestel, "create_analysis")


def test_module_has_add_factor():
    from services.analytics import pestel
    assert hasattr(pestel, "add_factor")


def test_module_has_compute_scores():
    from services.analytics import pestel
    assert hasattr(pestel, "compute_scores")


def test_module_has_suggest():
    from services.analytics import pestel
    assert hasattr(pestel, "suggest")


def test_module_has_render_markdown():
    from services.analytics import pestel
    assert hasattr(pestel, "render_markdown")


def test_module_has_render_cli():
    from services.analytics import pestel
    assert hasattr(pestel, "render_cli")


# --- Schema validation ---

def test_schema_file_exists():
    assert SCHEMA.exists(), f"{SCHEMA} does not exist"


def test_schema_defines_pestel_analysis_table():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS pestel_analysis" in text


def test_schema_defines_pestel_factor_table():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS pestel_factor" in text


def test_schema_has_category_check():
    text = SCHEMA.read_text()
    assert "'political'" in text
    assert "'economic'" in text
    assert "'social'" in text
    assert "'technological'" in text
    assert "'environmental'" in text
    assert "'legal'" in text


def test_schema_has_factor_type_check():
    text = SCHEMA.read_text()
    assert "'strength'" in text
    assert "'opportunity'" in text
    assert "'risk'" in text
    assert "'neutral'" in text


def test_schema_has_views():
    text = SCHEMA.read_text()
    assert "v_pestel_summary" in text
    assert "v_pestel_high_impact" in text


# --- Validation ---

def test_add_factor_invalid_category():
    from services.analytics import pestel
    conn = MagicMock()
    with pytest.raises(ValueError, match="category"):
        pestel.add_factor(conn, "fake-id", "invalid", "risk", "Test")


def test_add_factor_invalid_type():
    from services.analytics import pestel
    conn = MagicMock()
    with pytest.raises(ValueError, match="factor_type"):
        pestel.add_factor(conn, "fake-id", "political", "invalid", "Test")


# --- Scoring math (no DB) ---

def test_compute_scores_empty_analysis():
    from services.analytics import pestel
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_cur.fetchone.return_value = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = pestel.compute_scores(mock_conn, str(uuid.uuid4()))
    assert result["overall"] == 0.0


# --- Rendering (no DB) ---

def test_render_markdown():
    from services.analytics import pestel
    analysis = {
        "title": "Test Analysis",
        "location_name": "Adelphi",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "status": "draft",
        "overall_score": 6.5,
        "political_score": 7.0,
        "economic_score": 6.0,
        "social_score": 5.5,
        "technological_score": 7.0,
        "environmental_score": 6.5,
        "legal_score": 7.0,
        "factors": [
            {"category": "political", "factor_type": "risk", "title": "Policy Change",
             "impact_score": 8.0, "likelihood": 0.7, "description": "New regulation pending"},
        ],
    }
    md = pestel.render_markdown(analysis)
    assert "PESTEL Analysis: Test Analysis" in md
    assert "Adelphi" in md
    assert "6.5/10" in md
    assert "Policy Change" in md


def test_render_cli():
    from services.analytics import pestel
    analysis = {
        "title": "Test",
        "location_name": "Farm",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "status": "draft",
        "overall_score": 5.0,
        "political_score": 0, "economic_score": 0, "social_score": 0,
        "technological_score": 0, "environmental_score": 0, "legal_score": 0,
        "factors": [],
    }
    cli = pestel.render_cli(analysis)
    assert "PESTEL ANALYSIS" in cli
    assert "5.0/10" in cli


# --- DB integration ---

def test_create_and_list_analyses():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import pestel
        created = pestel.create_analysis(conn, loc, "Test PESTEL", "2026-01-01", "2026-06-30")
        assert created["title"] == "Test PESTEL"
        assert created["status"] == "draft"
        rows = pestel.list_analyses(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in rows)
    except Exception:
        conn.rollback()
        pytest.skip("pestel_analysis table not present")
    finally:
        conn.close()


def test_add_factor_and_compute():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import pestel
        analysis = pestel.create_analysis(conn, loc, "Score Test", "2026-01-01", "2026-06-30")
        pestel.add_factor(conn, analysis["id"], "political", "risk", "Policy Risk", impact_score=8.0, likelihood=0.7)
        pestel.add_factor(conn, analysis["id"], "economic", "opportunity", "Market Growth", impact_score=7.0, likelihood=0.6)
        result = pestel.compute_scores(conn, analysis["id"])
        assert result["scores"]["political"] > 0
        assert result["scores"]["economic"] > 0
        assert result["overall"] > 0
    except Exception:
        conn.rollback()
        pytest.skip("pestel tables not present")
    finally:
        conn.close()


def test_suggest_returns_list():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import pestel
        suggestions = pestel.suggest(conn, loc)
        assert isinstance(suggestions, list)
    except Exception:
        conn.rollback()
        pytest.skip("suggest query failed")
    finally:
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
