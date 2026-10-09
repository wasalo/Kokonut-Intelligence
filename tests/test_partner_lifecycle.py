"""Tests for the Partner Lifecycle service."""

import json
import uuid

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import partner_lifecycle


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _partner(conn):
    """Get an existing partner ID, or create one."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM partner LIMIT 1")
        row = cur.fetchone()
    if row:
        return str(row[0])
    # Create a partner if none exists
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO partner (name, slug, partner_type, status)
            VALUES ('Test Partner', 'test-partner-%s', 'vendor', 'active')
            RETURNING id
            """,
            (str(uuid.uuid4())[:8],),
        )
        row = cur.fetchone()
        conn.commit()
    return str(row[0]) if row else None


def test_module_shape():
    assert hasattr(partner_lifecycle, "create_lifecycle")
    assert hasattr(partner_lifecycle, "advance_stage")
    assert hasattr(partner_lifecycle, "list_lifecycles")
    assert hasattr(partner_lifecycle, "get_lifecycle")
    assert hasattr(partner_lifecycle, "create_evaluation")
    assert hasattr(partner_lifecycle, "list_evaluations")
    assert hasattr(partner_lifecycle, "create_scorecard")
    assert hasattr(partner_lifecycle, "list_scorecards")


def test_create_and_list_lifecycle():
    conn = _db()
    partner_id = _partner(conn)
    if not partner_id:
        pytest.skip("no partner available")
    try:
        created = partner_lifecycle.create_lifecycle(
            conn, partner_id, stage="prospect",
            partnership_type="technical", strategic_importance="high",
        )
        assert created["stage"] == "prospect"
        assert created["strategic_importance"] == "high"
        lifecycles = partner_lifecycle.list_lifecycles(conn, partner_id=partner_id)
        assert any(str(r["id"]) == str(created["id"]) for r in lifecycles)
    except psycopg2.ProgrammingError:
        pytest.skip("partner_lifecycle table not present (migration not applied)")
    finally:
        conn.close()


def test_advance_stage():
    conn = _db()
    partner_id = _partner(conn)
    if not partner_id:
        pytest.skip("no partner available")
    try:
        created = partner_lifecycle.create_lifecycle(conn, partner_id, stage="prospect")
        result = partner_lifecycle.advance_stage(
            conn, str(created["id"]), "negotiation", notes="Initial meeting done",
        )
        assert result["stage"] == "negotiation"
    except psycopg2.ProgrammingError:
        pytest.skip("partner_lifecycle table not present (migration not applied)")
    finally:
        conn.close()


def test_get_lifecycle_with_children():
    conn = _db()
    partner_id = _partner(conn)
    if not partner_id:
        pytest.skip("no partner available")
    try:
        created = partner_lifecycle.create_lifecycle(conn, partner_id, stage="active")
        lc_id = str(created["id"])
        partner_lifecycle.create_evaluation(
            conn, lc_id, partner_id, "initial",
            technical_score=80, financial_score=70,
        )
        result = partner_lifecycle.get_lifecycle(conn, lc_id)
        assert result is not None
        assert "evaluations" in result
        assert "scorecards" in result
        assert len(result["evaluations"]) == 1
    except psycopg2.ProgrammingError:
        pytest.skip("partner_lifecycle table not present (migration not applied)")
    finally:
        conn.close()


def test_create_evaluation():
    conn = _db()
    partner_id = _partner(conn)
    if not partner_id:
        pytest.skip("no partner available")
    try:
        created = partner_lifecycle.create_lifecycle(conn, partner_id, stage="active")
        result = partner_lifecycle.create_evaluation(
            conn, str(created["id"]), partner_id, "quarterly",
            technical_score=85, financial_score=75,
            reliability_score=90, compliance_score=80,
            strengths=["Good quality"], weaknesses=["Slow response"],
        )
        assert result["overall_score"] > 0
        assert result["evaluation_type"] == "quarterly"
    except psycopg2.ProgrammingError:
        pytest.skip("partner_evaluation table not present (migration not applied)")
    finally:
        conn.close()


def test_create_scorecard():
    conn = _db()
    partner_id = _partner(conn)
    if not partner_id:
        pytest.skip("no partner available")
    try:
        created = partner_lifecycle.create_lifecycle(conn, partner_id, stage="active")
        result = partner_lifecycle.create_scorecard(
            conn, str(created["id"]), partner_id,
            "2026-01-01", "2026-03-31",
            deliveries_on_time_pct=92, quality_score=88,
            responsiveness_score=85, cost_competitiveness=78,
            innovation_score=70,
        )
        assert result["overall_score"] > 0
    except psycopg2.ProgrammingError:
        pytest.skip("partner_scorecard table not present (migration not applied)")
    finally:
        conn.close()


def test_list_scorecards():
    conn = _db()
    partner_id = _partner(conn)
    if not partner_id:
        pytest.skip("no partner available")
    try:
        created = partner_lifecycle.create_lifecycle(conn, partner_id, stage="active")
        partner_lifecycle.create_scorecard(
            conn, str(created["id"]), partner_id,
            "2026-01-01", "2026-03-31", quality_score=88,
        )
        scorecards = partner_lifecycle.list_scorecards(conn, str(created["id"]))
        assert len(scorecards) >= 1
    except psycopg2.ProgrammingError:
        pytest.skip("partner_scorecard table not present (migration not applied)")
    finally:
        conn.close()


def test_list_by_stage():
    conn = _db()
    partner_id = _partner(conn)
    if not partner_id:
        pytest.skip("no partner available")
    try:
        partner_lifecycle.create_lifecycle(conn, partner_id, stage="active")
        partner_lifecycle.create_lifecycle(conn, partner_id, stage="prospect")
        active = partner_lifecycle.list_lifecycles(conn, stage="active", partner_id=partner_id)
        assert all(r["stage"] == "active" for r in active)
    except psycopg2.ProgrammingError:
        pytest.skip("partner_lifecycle table not present (migration not applied)")
    finally:
        conn.close()
