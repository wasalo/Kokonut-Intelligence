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


def test_comprehensive_status_contains_fourteen_per_location_sections():
    location_id = "a0000000-0000-0000-0000-000000000001"
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"id": location_id, "name": "Adelphi"}]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    generator_names = (
        "generate_farm_summary",
        "generate_crop_noi",
        "generate_environmental",
        "generate_climate_impact",
        "generate_financial_sustainability",
        "generate_capital_efficiency",
        "generate_holistic_wellbeing",
        "generate_community_governance",
        "generate_gnh_alignment",
        "generate_training_impact",
        "generate_regenerative_outcomes",
        "generate_foundational_wellbeing",
        "generate_stakeholder_outcomes",
        "generate_capital_accounting",
    )

    with patch.multiple(state_module, **{name: MagicMock(return_value={}) for name in generator_names}):
        report = rg.generate_comprehensive_status(conn, location_id)

    sections = report["locations"][0]["sections"]
    assert len(sections) == 14
    assert set(sections) == {
        "farm_summary",
        "crop_noi",
        "environmental",
        "climate_impact",
        "financial_sustainability",
        "capital_efficiency",
        "holistic_wellbeing",
        "community_governance",
        "gnh_alignment",
        "training_impact",
        "regenerative_outcomes",
        "foundational_wellbeing",
        "stakeholder_outcomes",
        "capital_accounting",
    }


def test_comprehensive_status_rollup_keeps_harvest_units_separate():
    loc_rows = [
        {"id": "a0000000-0000-0000-0000-000000000001", "name": "Adelphi"},
        {"id": "b0000000-0000-0000-0000-000000000002", "name": "Other"},
    ]
    composed = [
        {
            "location_id": loc_rows[0]["id"],
            "sections": {
                "farm_summary": {
                    "harvest_summary": {
                        "total_quantity": None,
                        "total_quantity_by_unit": {"kg": 120},
                    }
                }
            },
        },
        {
            "location_id": loc_rows[1]["id"],
            "sections": {
                "farm_summary": {
                    "harvest_summary": {
                        "total_quantity": None,
                        "total_quantity_by_unit": {"tonnes": 1.5},
                    }
                }
            },
        },
    ]
    conn = MagicMock()
    with patch.object(state_module, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(state_module, "generate_foundational_wellbeing", return_value={"ok": True}), \
         patch.object(state_module, "generate_stakeholder_outcomes", return_value={"ok": True}), \
         patch.object(state_module, "generate_capital_accounting", return_value={"ok": True}):
        report = rg.generate_comprehensive_status(conn, "all")

    overview = report["ecosystem_overview"]
    assert overview["total_harvest_quantity"] is None
    assert overview["total_harvest_quantity_unit"] is None
    assert overview["total_harvest_quantity_by_unit"] == {"kg": 120.0, "tonnes": 1.5}


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


def test_comprehensive_status_rolls_back_failed_section_to_savepoint():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value

    def failure(*_args):
        raise RuntimeError("synthetic")

    result = state_module._run_composite_section(
        conn, failure, conn, "location-a", operation="report section"
    )

    assert result == {"error": "report section failed (RuntimeError)"}
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SAVEPOINT kokonut_comprehensive_status_section",
        "ROLLBACK TO SAVEPOINT kokonut_comprehensive_status_section",
        "RELEASE SAVEPOINT kokonut_comprehensive_status_section",
    ]


def test_comprehensive_status_releases_successful_section_savepoint():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value

    result = state_module._run_composite_section(
        conn, lambda *_args: {"ok": True}, conn, "location-a"
    )

    assert result == {"ok": True}
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SAVEPOINT kokonut_comprehensive_status_section",
        "RELEASE SAVEPOINT kokonut_comprehensive_status_section",
    ]


def test_comprehensive_status_recovers_when_section_swallows_database_error():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    failed_release = False

    def execute(statement):
        nonlocal failed_release
        if (
            statement == "RELEASE SAVEPOINT kokonut_comprehensive_status_section"
            and not failed_release
        ):
            failed_release = True
            raise RuntimeError("transaction was left aborted by an inner handler")

    cursor.execute.side_effect = execute

    result = state_module._run_composite_section(conn, lambda: {"partial": True})

    assert result == {"error": "report section failed (RuntimeError)"}
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SAVEPOINT kokonut_comprehensive_status_section",
        "RELEASE SAVEPOINT kokonut_comprehensive_status_section",
        "ROLLBACK TO SAVEPOINT kokonut_comprehensive_status_section",
        "RELEASE SAVEPOINT kokonut_comprehensive_status_section",
    ]
