"""Tests for the comprehensive_status report generator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.export import report_generator as rg
from services.export.reports import state as state_module


def test_registered():
    assert "comprehensive_status" in rg.REPORT_GENERATORS
    assert rg.REPORT_GENERATORS["comprehensive_status"] is rg.generate_comprehensive_status


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


def test_comprehensive_status_network_wide_rolls_up():
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
    conn = MagicMock()
    with patch.object(state_module, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(state_module, "generate_foundational_wellbeing", return_value={"ok": True}), \
         patch.object(state_module, "generate_stakeholder_outcomes", return_value={"ok": True}):
        report = rg.generate_comprehensive_status(conn, "all", "2021-01-01", "2024-12-31")

    assert report["report_type"] == "comprehensive_status"
    assert report["scope"] == "all_locations"
    assert report["ecosystem_overview"]["total_locations"] == 2
    assert report["ecosystem_overview"]["total_revenue_usd"] == 150.0
    assert report["ecosystem_overview"]["net_income_usd"] == 90.0
    assert len(report["locations"]) == 2
    # Extended sections are composed per location.
    assert report["locations"][0]["sections"]["foundational_wellbeing"] == {"ok": True}
    assert report["locations"][0]["sections"]["stakeholder_outcomes"] == {"ok": True}


def test_comprehensive_status_selected_location():
    loc_rows = [
        {"id": "a0000000-0000-0000-0000-000000000001", "name": "Adelphi", "slug": "adelphi",
         "country": "DR", "region": "x", "status": "active"},
    ]
    composed = [
        {"location_id": loc_rows[0]["id"], "name": "Adelphi", "sections": _fake_section(10.0, 5.0, 1.0)},
    ]
    conn = MagicMock()
    with patch.object(state_module, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(state_module, "generate_foundational_wellbeing", return_value={"ok": True}), \
         patch.object(state_module, "generate_stakeholder_outcomes", return_value={"ok": True}):
        report = rg.generate_comprehensive_status(conn, "a0000000-0000-0000-0000-000000000001")

    assert report["scope"] == "selected_locations"
    assert report["selected_location_ids"] == ["a0000000-0000-0000-0000-000000000001"]


def test_comprehensive_status_isolates_section_errors():
    loc_rows = [
        {"id": "a0000000-0000-0000-0000-000000000001", "name": "Adelphi", "slug": "adelphi",
         "country": "DR", "region": "x", "status": "active"},
    ]
    composed = [
        {"location_id": loc_rows[0]["id"], "name": "Adelphi", "sections": _fake_section()},
    ]
    conn = MagicMock()
    with patch.object(state_module, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(state_module, "generate_foundational_wellbeing", side_effect=RuntimeError("boom")), \
         patch.object(state_module, "generate_stakeholder_outcomes", return_value={"ok": True}):
        report = rg.generate_comprehensive_status(conn, "all")

    section = report["locations"][0]["sections"]["foundational_wellbeing"]
    assert "error" in section
    # Other sections still compose.
    assert report["locations"][0]["sections"]["stakeholder_outcomes"] == {"ok": True}
