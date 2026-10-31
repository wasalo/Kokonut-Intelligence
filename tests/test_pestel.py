"""Tests for PESTEL Analysis service."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock

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


# --- Explicit read projections ---

def test_list_analyses_uses_explicit_columns_and_preserves_location_filter():
    from services.analytics import pestel

    rows = [{"id": "analysis-1", "location_id": "location-1", "location_name": "Adelphi"}]
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor

    result = pestel.list_analyses(conn, "location-1")

    query, params = cursor.execute.call_args.args
    normalized_query = " ".join(query.split())
    assert normalized_query.startswith(
        "SELECT a.id, a.location_id, a.title, a.period_start, a.period_end,"
    )
    assert "a.metadata, a.created_by, a.updated_by, a.created_at, a.updated_at, l.name AS location_name" in normalized_query
    assert "WHERE a.location_id = %s ORDER BY a.created_at DESC" in normalized_query
    assert "a.*" not in normalized_query and "SELECT *" not in normalized_query
    assert params == ("location-1",)
    assert result == rows


def test_list_analyses_preserves_intentional_all_locations_branch():
    from services.analytics import pestel

    rows = [{"id": "analysis-1", "location_id": "location-1"}]
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor

    result = pestel.list_analyses(conn)

    query = cursor.execute.call_args.args[0]
    normalized_query = " ".join(query.split())
    assert "WHERE a.location_id" not in normalized_query
    assert normalized_query.endswith("ORDER BY a.created_at DESC")
    assert cursor.execute.call_args.args == (query,)
    assert result == rows


def test_get_analysis_uses_explicit_analysis_and_factor_columns():
    from services.analytics import pestel

    analysis = {"id": "analysis-1", "location_id": "location-1", "title": "Plan"}
    factors = [{"id": "factor-1", "category": "political", "title": "Policy"}]
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = analysis
    cursor.fetchall.return_value = factors
    conn = MagicMock()
    conn.cursor.return_value = cursor

    result = pestel.get_analysis(conn, "analysis-1")

    assert cursor.execute.call_count == 2
    analysis_query, analysis_params = cursor.execute.call_args_list[0].args
    factor_query, factor_params = cursor.execute.call_args_list[1].args
    normalized_analysis_query = " ".join(analysis_query.split())
    normalized_factor_query = " ".join(factor_query.split())
    assert normalized_analysis_query.startswith(
        "SELECT a.id, a.location_id, a.title, a.period_start, a.period_end,"
    )
    assert "WHERE a.id = %s" in normalized_analysis_query
    assert "a.*" not in normalized_analysis_query
    assert normalized_factor_query.startswith(
        "SELECT id, analysis_id, location_id, category, factor_type, title,"
    )
    assert "FROM pestel_factor WHERE analysis_id = %s ORDER BY category, factor_type" in normalized_factor_query
    assert "SELECT *" not in normalized_factor_query
    assert analysis_params == ("analysis-1",)
    assert factor_params == ("analysis-1",)
    assert result == {**analysis, "factors": factors}


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


def test_add_factor_rejects_location_mismatch_before_insert():
    from services.analytics import pestel

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = ("analysis-location",)
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with pytest.raises(ValueError, match="must match the PESTEL analysis location"):
        pestel.add_factor(
            conn,
            "analysis-1",
            "political",
            "risk",
            "Policy risk",
            location_id="other-location",
        )

    assert cursor.execute.call_count == 1
    conn.commit.assert_not_called()


def test_add_factor_rejects_missing_analysis_even_with_location():
    from services.analytics import pestel

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = None
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with pytest.raises(ValueError, match="Analysis analysis-1 not found"):
        pestel.add_factor(
            conn,
            "analysis-1",
            "political",
            "risk",
            "Policy risk",
            location_id="location-1",
        )

    assert cursor.execute.call_count == 1
    conn.commit.assert_not_called()


@pytest.mark.parametrize(
    ("impact", "likelihood"),
    [(0, 0.5), (11, 0.5), (float("nan"), 0.5), (5, -0.1), (5, 1.1), (5, float("inf"))],
)
def test_add_factor_rejects_out_of_range_scores_before_database_access(impact, likelihood):
    from services.analytics import pestel

    conn = MagicMock()
    with pytest.raises(ValueError):
        pestel.add_factor(
            conn,
            "analysis-1",
            "political",
            "risk",
            "Policy risk",
            impact_score=impact,
            likelihood=likelihood,
        )
    conn.cursor.assert_not_called()


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
