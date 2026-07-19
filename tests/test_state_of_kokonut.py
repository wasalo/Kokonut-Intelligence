"""Tests for the state_of_kokonut ecosystem report generator.

Covers registration, the UUID-scope guard, the location-selection parsing, and
the composition/rollup orchestration. Per-location sub-generators are mocked so
the test is deterministic and DB-free; actor-view and location composition are
stubbed to validate the aggregation logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.export import report_generator as rg


def test_registered():
    assert "state_of_kokonut" in rg.REPORT_GENERATORS
    assert rg.REPORT_GENERATORS["state_of_kokonut"] is rg.generate_state_of_kokonut


def test_looks_like_uuid_guard():
    assert rg._looks_like_uuid("a0000000-0000-0000-0000-000000000001") is True
    assert rg._looks_like_uuid("all") is False
    assert rg._looks_like_uuid("a,b,c") is False
    assert rg._looks_like_uuid("") is False
    assert rg._looks_like_uuid(None) is False


def _fake_section(financial_total_revenue=0.0, financial_total_expenses=0.0, harvest_qty=0.0):
    return {
        "farm_summary": {
            "financial_summary": {
                "total_revenue": financial_total_revenue,
                "total_expenses": financial_total_expenses,
            },
            "harvest_summary": {"total_quantity": harvest_qty},
        }
    }


def test_composes_all_locations_and_rolls_up():
    loc_rows = [
        {"id": "a0000000-0000-0000-0000-000000000001", "name": "Adelphi", "slug": "adelphi",
         "country": "DR", "region": "x", "status": "active"},
        {"id": "b0000000-0000-0000-0000-000000000002", "name": "Other", "slug": "other",
         "country": "DR", "region": "y", "status": "active"},
    ]
    composed = [
        {"location_id": loc_rows[0]["id"], "name": "Adelphi", "sections": _fake_section(100.0, 40.0, 5.0)},
        {"location_id": loc_rows[1]["id"], "name": "Other", "sections": _fake_section(50.0, 20.0, 3.0)},
    ]
    actor_view = {"by_actor": [], "by_source": [], "participation": [], "rounds": [], "total_raised": 815000.0}

    conn = MagicMock()
    with patch.object(rg, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(rg, "_state_of_kokonut_actors", return_value=actor_view):
        report = rg.generate_state_of_kokonut(conn, "all", "2021-01-01", "2024-12-31")

    assert report["report_type"] == "state_of_kokonut"
    assert report["scope"] == "all_locations"
    assert report["selected_location_ids"] is None
    ov = report["ecosystem_overview"]
    assert ov["total_locations"] == 2
    assert ov["total_revenue_usd"] == 150.0
    assert ov["total_expenses_usd"] == 60.0
    assert ov["net_income_usd"] == 90.0
    assert ov["total_harvest_quantity"] == 8.0
    assert report["actor_view"]["total_raised"] == 815000.0
    assert len(report["locations"]) == 2
    assert "limitations" in report


def test_composes_selected_locations_from_comma_list():
    loc_rows = [
        {"id": "a0000000-0000-0000-0000-000000000001", "name": "Adelphi", "slug": "adelphi",
         "country": "DR", "region": "x", "status": "active"},
    ]
    composed = [
        {"location_id": loc_rows[0]["id"], "name": "Adelphi", "sections": _fake_section(100.0, 40.0, 5.0)},
    ]
    conn = MagicMock()
    with patch.object(rg, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(rg, "_state_of_kokonut_actors", return_value={"total_raised": 0.0}):
        report = rg.generate_state_of_kokonut(
            conn, "a0000000-0000-0000-0000-000000000001", None, None
        )

    assert report["scope"] == "selected_locations"
    assert report["selected_location_ids"] == ["a0000000-0000-0000-0000-000000000001"]
    assert report["ecosystem_overview"]["total_locations"] == 1


def test_isolates_failing_section():
    # The section-error isolation lives inside _state_of_kokonut_locations, which
    # calls each per-location sub-generator and captures failures per section.
    loc_id = "a0000000-0000-0000-0000-000000000001"
    loc_rows = [
        {"id": loc_id, "name": "Adelphi", "slug": "adelphi",
         "country": "DR", "region": "x", "status": "active"},
    ]
    conn = MagicMock()
    # First fetchall() (location lookup) returns loc_rows; later cursor calls
    # serve the sub-generators which we stub except for the failing one.
    cur = MagicMock()
    cur.fetchall.return_value = loc_rows
    cur.fetchone.return_value = {}
    conn.cursor.return_value = cur
    with patch.object(rg, "generate_crop_noi", side_effect=RuntimeError("boom")), \
         patch.object(rg, "generate_farm_summary", return_value={"report_type": "farm_summary"}), \
         patch.object(rg, "generate_environmental", return_value={"report_type": "environmental"}), \
         patch.object(rg, "generate_climate_impact", return_value={"report_type": "climate_impact"}), \
         patch.object(rg, "generate_financial_sustainability", return_value={"report_type": "financial_sustainability"}), \
         patch.object(rg, "generate_capital_efficiency", return_value={"report_type": "capital_efficiency"}), \
         patch.object(rg, "generate_holistic_wellbeing", return_value={"report_type": "holistic_wellbeing"}), \
         patch.object(rg, "generate_community_governance", return_value={"report_type": "community_governance"}), \
         patch.object(rg, "generate_gnh_alignment", return_value={"report_type": "gnh_alignment"}), \
         patch.object(rg, "generate_training_impact", return_value={"report_type": "training_impact"}), \
         patch.object(rg, "generate_regenerative_outcomes", return_value={"report_type": "regenerative_outcomes"}):
        _, composed = rg._state_of_kokonut_locations(conn, [loc_id], None, None)
    entry = composed[0]
    assert "crop_noi" in entry["sections"]
    assert "error" in entry["sections"]["crop_noi"]
    # A working section is still present.
    assert "farm_summary" in entry["sections"]
