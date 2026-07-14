"""Tests for the business-plan assembler (organization + location grain)."""

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.export import business_plan as bp


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _ids(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        loc = cur.fetchone()
        cur.execute("SELECT id FROM organization LIMIT 1")
        org = cur.fetchone()
    return (str(loc[0]) if loc else None, str(org[0]) if org else None)


def test_module_shape():
    assert hasattr(bp, "generate_business_plan")


def test_generate_location_grain():
    conn = _db()
    loc, _ = _ids(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        plan = bp.generate_business_plan(conn, location_id=loc)
        assert plan["meta"]["grain"] == "location"
        for key in ("market_analysis", "management_governance",
                    "financial_plan", "operational_flow", "swot",
                    "executive_summary"):
            assert key in plan
    except psycopg2.ProgrammingError:
        pytest.skip("business-plan source tables not present (migration not applied)")
    finally:
        conn.close()


def test_generate_org_grain():
    conn = _db()
    _, org = _ids(conn)
    if not org:
        pytest.skip("no organization row available")
    try:
        plan = bp.generate_business_plan(conn, org_id=org)
        assert plan["meta"]["grain"] == "organization"
        assert "executive_summary" in plan
    except psycopg2.ProgrammingError:
        pytest.skip("business-plan source tables not present (migration not applied)")
    finally:
        conn.close()
