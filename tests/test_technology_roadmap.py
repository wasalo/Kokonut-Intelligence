"""Integration tests for the governed technology roadmap."""

import pytest

from services.analytics import technology_roadmap as tr
from services.export.report_generator import generate_technology_roadmap
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_technology_roadmap_lifecycle():
    conn = _db()
    roadmap_id = None
    try:
        roadmap = tr.create_roadmap(
            "Test Technology Roadmap",
            description="Roadmap test",
            entity_type="platform",
            planning_horizon_start="2026-01-01",
            planning_horizon_end="2027-12-31",
        )
        roadmap_id = roadmap["id"]
        requirement = tr.add_requirement(
            roadmap_id,
            "Reduce onboarding time",
            need_type="operational",
            priority=5,
            target_value=30,
            unit="days",
        )
        area = tr.add_area(roadmap_id, "Platform delivery", sequence_order=1)
        driver = tr.add_driver(
            area["id"],
            "Deployment time",
            requirement_id=requirement["id"],
            metric_key="deployment_days",
            target_value=30,
            unit="days",
            weight=8,
        )
        alternative = tr.add_alternative(
            driver["id"],
            "Reusable deployment package",
            maturity_status="pilot",
            confidence=0.8,
            recommendation="selected",
        )

        detail = tr.get_roadmap_detail(roadmap_id)
        assert detail["name"] == "Test Technology Roadmap"
        assert detail["requirements"][0]["id"] == requirement["id"]
        assert any(row["alternative_id"] == alternative["id"] for row in detail["technology_areas"])
        assert tr.recommend_alternatives(roadmap_id)[0]["alternative_id"] == alternative["id"]

        review = tr.review_roadmap(roadmap_id, "approved", notes="Reviewed test roadmap")
        assert review["result"] == "approved"
        assert tr.get_roadmap(roadmap_id)["status"] == "approved"
    finally:
        conn.rollback()
        if roadmap_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM technology_roadmap WHERE id = %s::uuid", (roadmap_id,))
            conn.commit()
        conn.close()


def test_seeded_roadmap_has_governed_structure():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT requirement_count, technology_area_count, driver_count, alternative_count "
                "FROM v_technology_roadmap_overview WHERE name = 'Kokonut Platform Scale Roadmap'"
            )
            row = cur.fetchone()
        assert row is not None
        assert row[0] == 3
        assert row[1] == 3
        assert row[2] == 3
        assert row[3] == 3
    finally:
        conn.close()


def test_technology_roadmap_report_contains_requirements_and_alternatives():
    conn = _db()
    try:
        report = generate_technology_roadmap(conn)
        assert report["report_type"] == "technology_roadmap"
        assert report["roadmap_count"] >= 1
        seeded = next(item for item in report["roadmaps"] if item["name"] == "Kokonut Platform Scale Roadmap")
        assert len(seeded["requirements"]) == 3
        assert len(seeded["alternatives"]) == 3
    finally:
        conn.close()
