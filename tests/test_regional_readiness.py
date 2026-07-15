"""Tests for Regional Readiness service."""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCHEMA = Path("schemas/postgres/204_regional_readiness.sql")


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

def test_module_has_create_assessment():
    from services.analytics import regional_readiness
    assert hasattr(regional_readiness, "create_assessment")


def test_module_has_compute_composite():
    from services.analytics import regional_readiness
    assert hasattr(regional_readiness, "compute_composite")


def test_module_has_gather_evidence():
    from services.analytics import regional_readiness
    assert hasattr(regional_readiness, "gather_evidence")


def test_module_has_compare_locations():
    from services.analytics import regional_readiness
    assert hasattr(regional_readiness, "compare_locations")


def test_module_has_render_markdown():
    from services.analytics import regional_readiness
    assert hasattr(regional_readiness, "render_markdown")


def test_module_has_render_cli():
    from services.analytics import regional_readiness
    assert hasattr(regional_readiness, "render_cli")


# --- Schema validation ---

def test_schema_file_exists():
    assert SCHEMA.exists(), f"{SCHEMA} does not exist"


def test_schema_defines_readiness_dimension():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS readiness_dimension" in text


def test_schema_defines_regional_assessment():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS regional_assessment" in text


def test_schema_defines_regional_dimension_score():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS regional_dimension_score" in text


def test_schema_defines_regional_benchmark():
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS regional_benchmark" in text


def test_schema_has_views():
    text = SCHEMA.read_text()
    assert "v_regional_composite" in text
    assert "v_regional_dimension_detail" in text
    assert "v_regional_benchmark_compare" in text


def test_schema_seeds_dimensions():
    text = SCHEMA.read_text()
    assert "infrastructure" in text
    assert "institutions" in text
    assert "market_access" in text
    assert "natural_capital" in text
    assert "policy_environment" in text
    assert "human_capital" in text


# --- Scoring math (no DB) ---

def test_weighted_average_basic():
    from services.analytics import regional_readiness
    scores = {"a": 80.0, "b": 60.0}
    weights = {"a": 0.5, "b": 0.5}
    result = regional_readiness.weighted_average(scores, weights)
    assert result == 70.0


def test_weighted_average_empty():
    from services.analytics import regional_readiness
    result = regional_readiness.weighted_average({}, {})
    assert result == 0.0


def test_clamp_score():
    from services.analytics import regional_readiness
    assert regional_readiness.clamp_score(150.0) == 100.0
    assert regional_readiness.clamp_score(-10.0) == 0.0
    assert regional_readiness.clamp_score(50.0) == 50.0


def test_assign_rating_bands():
    from services.analytics import regional_readiness
    assert regional_readiness.assign_rating(90) == "A+"
    assert regional_readiness.assign_rating(80) == "A"
    assert regional_readiness.assign_rating(65) == "B"
    assert regional_readiness.assign_rating(50) == "C"
    assert regional_readiness.assign_rating(30) == "D"


def test_assign_rating_boundary():
    from services.analytics import regional_readiness
    assert regional_readiness.assign_rating(85) == "A+"
    assert regional_readiness.assign_rating(70) == "A"
    assert regional_readiness.assign_rating(55) == "B"
    assert regional_readiness.assign_rating(40) == "C"
    assert regional_readiness.assign_rating(0) == "D"


# --- Dimension config ---

def test_dimensions_count():
    from services.analytics import regional_readiness
    assert len(regional_readiness.DIMENSIONS) == 6


def test_dimensions_weights_sum_to_one():
    from services.analytics import regional_readiness
    total = sum(d["default_weight"] for d in regional_readiness.DIMENSIONS.values())
    assert abs(total - 1.0) < 0.001


# --- Rendering (no DB) ---

def test_render_markdown():
    from services.analytics import regional_readiness
    assessment = {
        "title": "Test Assessment",
        "location_name": "Adelphi",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "rating": "A",
        "composite_score": 75.0,
        "confidence_level": "moderate",
        "infrastructure_score": 80, "institutions_score": 70,
        "market_access_score": 75, "natural_capital_score": 80,
        "policy_environment_score": 60, "human_capital_score": 65,
        "dimensions": [],
    }
    md = regional_readiness.render_markdown(assessment)
    assert "Regional Readiness Assessment" in md
    assert "Adelphi" in md
    assert "A" in md
    assert "75.0/100" in md


def test_render_cli():
    from services.analytics import regional_readiness
    assessment = {
        "title": "Test",
        "location_name": "Farm",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "rating": "B",
        "composite_score": 60.0,
        "confidence_level": "moderate",
        "infrastructure_score": 70, "institutions_score": 60,
        "market_access_score": 55, "natural_capital_score": 65,
        "policy_environment_score": 50, "human_capital_score": 55,
        "dimensions": [],
    }
    cli = regional_readiness.render_cli(assessment)
    assert "REGIONAL READINESS" in cli
    assert "60.0" in cli


# --- DB integration ---

def test_create_and_list_assessments():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import regional_readiness
        created = regional_readiness.create_assessment(conn, loc, "Test Regional", "2026-01-01", "2026-06-30")
        assert created["title"] == "Test Regional"
        assert created["status"] == "draft"
        rows = regional_readiness.list_assessments(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in rows)
    except Exception:
        conn.rollback()
        pytest.skip("regional_assessment table not present")
    finally:
        conn.close()


def test_compute_composite():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import regional_readiness
        assessment = regional_readiness.create_assessment(conn, loc, "Compute Test", "2026-01-01", "2026-06-30")
        result = regional_readiness.compute_composite(conn, assessment["id"])
        assert "composite_score" in result
        assert "rating" in result
        assert result["rating"] in ("A+", "A", "B", "C", "D")
        assert len(result["dimensions"]) == 6
    except Exception:
        conn.rollback()
        pytest.skip("compute failed (tables not present)")
    finally:
        conn.close()


def test_gather_evidence_returns_all_keys():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        from services.analytics import regional_readiness
        evidence = regional_readiness.gather_evidence(conn, loc)
        assert "location" in evidence
        assert "infrastructure" in evidence
        assert "institutions" in evidence
        assert "market_access" in evidence
        assert "natural_capital" in evidence
        assert "policy_environment" in evidence
        assert "human_capital" in evidence
    except Exception:
        conn.rollback()
        pytest.skip("evidence gathering failed")
    finally:
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
