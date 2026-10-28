"""Tests for the state_of_kokonut ecosystem report generator.

Covers registration, the UUID-scope guard, the location-selection parsing, and
the composition/rollup orchestration. Per-location sub-generators are mocked so
the test is deterministic and DB-free; actor-view and location composition are
stubbed to validate the aggregation logic.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.export import report_generator as rg
from services.export.reports import common as reports_common
from services.export.reports import state as state_module


def _actor_view_connection(result_sets):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.side_effect = result_sets
    connection.cursor.return_value = cursor
    return connection, cursor


def test_registered():
    assert "state_of_kokonut" in rg.REPORT_GENERATORS
    assert rg.REPORT_GENERATORS["state_of_kokonut"] is rg.generate_state_of_kokonut


def test_looks_like_uuid_guard():
    assert reports_common._looks_like_uuid("a0000000-0000-0000-0000-000000000001") is True
    assert reports_common._looks_like_uuid("all") is False
    assert reports_common._looks_like_uuid("a,b,c") is False
    assert reports_common._looks_like_uuid("") is False
    assert reports_common._looks_like_uuid(None) is False


def _fake_section(financial_total_revenue=0.0, financial_total_expenses=0.0, harvest_qty=0.0):
    return {
        "farm_summary": {
            "financial_summary": {
                "total_revenue": financial_total_revenue,
                "total_expenses": financial_total_expenses,
            },
            "harvest_summary": {
                "total_quantity": harvest_qty,
                "quantity_unit": "kg",
                "total_quantity_by_unit": {"kg": harvest_qty},
            },
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
    with patch.object(state_module, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(state_module, "_state_of_kokonut_actors", return_value=actor_view):
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
    assert ov["total_harvest_quantity_unit"] == "kg"
    assert ov["total_harvest_quantity_by_unit"] == {"kg": 8.0}
    assert report["actor_view"]["total_raised"] == 815000.0
    assert len(report["locations"]) == 2
    assert "limitations" in report


def test_network_harvest_rollup_does_not_mix_units():
    loc_rows = [
        {"id": "a0000000-0000-0000-0000-000000000001", "name": "Adelphi"},
        {"id": "b0000000-0000-0000-0000-000000000002", "name": "Other"},
    ]
    composed = [
        {
            "location_id": loc_rows[0]["id"],
            "sections": {"farm_summary": {"harvest_summary": {"total_quantity": None, "total_quantity_by_unit": {"kg": 120}}}},
        },
        {
            "location_id": loc_rows[1]["id"],
            "sections": {"farm_summary": {"harvest_summary": {"total_quantity": None, "total_quantity_by_unit": {"tonnes": 1.5}}}},
        },
    ]
    conn = MagicMock()
    with patch.object(state_module, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(state_module, "_state_of_kokonut_actors", return_value={"total_raised": 0.0}):
        report = rg.generate_state_of_kokonut(conn, "all")

    overview = report["ecosystem_overview"]
    assert overview["total_harvest_quantity"] is None
    assert overview["total_harvest_quantity_unit"] is None
    assert overview["total_harvest_quantity_by_unit"] == {"kg": 120.0, "tonnes": 1.5}


def test_composes_selected_locations_from_comma_list():
    loc_rows = [
        {"id": "a0000000-0000-0000-0000-000000000001", "name": "Adelphi", "slug": "adelphi",
         "country": "DR", "region": "x", "status": "active"},
    ]
    composed = [
        {"location_id": loc_rows[0]["id"], "name": "Adelphi", "sections": _fake_section(100.0, 40.0, 5.0)},
    ]
    conn = MagicMock()
    with patch.object(state_module, "_state_of_kokonut_locations", return_value=(loc_rows, composed)), \
         patch.object(state_module, "_state_of_kokonut_actors", return_value={"total_raised": 0.0}) as actor_view:
        report = rg.generate_state_of_kokonut(
            conn, "a0000000-0000-0000-0000-000000000001", None, None
        )

    actor_view.assert_called_once_with(
        conn, None, None, location_ids=["a0000000-0000-0000-0000-000000000001"]
    )
    assert report["scope"] == "selected_locations"
    assert report["selected_location_ids"] == ["a0000000-0000-0000-0000-000000000001"]
    assert report["ecosystem_overview"]["total_locations"] == 1


def test_empty_selected_location_list_fails_before_database_access():
    conn = MagicMock()

    with pytest.raises(ValueError, match="at least one location_id"):
        rg.generate_state_of_kokonut(conn, " , ,, ")

    conn.cursor.assert_not_called()


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
    with patch.object(state_module, "generate_crop_noi", side_effect=RuntimeError("boom")), \
         patch.object(state_module, "generate_farm_summary", return_value={"report_type": "farm_summary"}), \
         patch.object(state_module, "generate_environmental", return_value={"report_type": "environmental"}), \
         patch.object(state_module, "generate_climate_impact", return_value={"report_type": "climate_impact"}), \
         patch.object(state_module, "generate_financial_sustainability", return_value={"report_type": "financial_sustainability"}), \
         patch.object(state_module, "generate_capital_efficiency", return_value={"report_type": "capital_efficiency"}), \
         patch.object(state_module, "generate_holistic_wellbeing", return_value={"report_type": "holistic_wellbeing"}), \
         patch.object(state_module, "generate_community_governance", return_value={"report_type": "community_governance"}), \
         patch.object(state_module, "generate_gnh_alignment", return_value={"report_type": "gnh_alignment"}), \
         patch.object(state_module, "generate_training_impact", return_value={"report_type": "training_impact"}), \
         patch.object(state_module, "generate_regenerative_outcomes", return_value={"report_type": "regenerative_outcomes"}):
        _, composed = state_module._state_of_kokonut_locations(conn, [loc_id], None, None)
    entry = composed[0]
    assert "crop_noi" in entry["sections"]
    assert "error" in entry["sections"]["crop_noi"]
    # A working section is still present.
    assert "farm_summary" in entry["sections"]


def test_actor_rollups_preserve_currency_dimensions():
    connection, cursor = _actor_view_connection(
        [
            [
                {"actor_type": "network", "actor_name": "Kokonut", "currency": "USD", "total_raised": Decimal("100.25")},
                {"actor_type": "network", "actor_name": "Kokonut", "currency": "USDC", "total_raised": Decimal("80.50")},
            ],
            [
                {"source_type": "grant", "currency": "USD", "total_raised": Decimal("100.25")},
                {"source_type": "grant", "currency": "USDC", "total_raised": Decimal("80.50")},
            ],
            [
                {
                    "actor_type": "dao",
                    "decision_status": "executed",
                    "token": "USD",
                    "count": 2,
                    "amount": Decimal("100.25"),
                },
                {
                    "actor_type": "dao",
                    "decision_status": "executed",
                    "token": "USDC",
                    "count": 1,
                    "amount": Decimal("80.50"),
                }
            ],
            [],
        ]
    )

    result = state_module._state_of_kokonut_actors(connection, None, None)

    assert result["total_raised"] is None
    assert result["total_raised_currency"] is None
    assert result["total_raised_by_currency"] == {
        "USD": Decimal("100.25"),
        "USDC": Decimal("80.50"),
    }
    assert [row["currency"] for row in result["by_actor"]] == ["USD", "USDC"]
    assert result["by_source"][0]["currency"] == "USD"
    assert result["by_source"][1]["currency"] == "USDC"
    assert [(row["token"], row["amount"]) for row in result["participation"]] == [
        ("USD", Decimal("100.25")),
        ("USDC", Decimal("80.50")),
    ]
    source_query = cursor.execute.call_args_list[1].args[0]
    participation_query = cursor.execute.call_args_list[2].args[0]
    assert "GROUP BY fr.source_type, fr.currency" in source_query
    assert "GROUP BY pf.actor_type, pf.decision_status, pf.token" in participation_query


def test_actor_total_keeps_legacy_scalar_for_one_currency():
    connection, _cursor = _actor_view_connection(
        [[{"currency": "USD", "total_raised": Decimal("12.345") }], [], [], []]
    )

    result = state_module._state_of_kokonut_actors(connection, None, None)

    assert result["total_raised"] == 12.35
    assert result["total_raised_currency"] == "USD"
    assert result["total_raised_by_currency"] == {"USD": Decimal("12.345")}


def test_selected_location_actor_queries_bind_only_selected_funding_rows():
    location_id = "a0000000-0000-0000-0000-000000000001"
    connection, cursor = _actor_view_connection([[], [], [], []])

    state_module._state_of_kokonut_actors(
        connection, None, None, location_ids=[location_id]
    )

    assert len(cursor.execute.call_args_list) == 4
    for call in cursor.execute.call_args_list:
        query, params = call.args
        assert "fr.location_id = ANY(%s::uuid[])" in query
        assert params[-1] == [location_id]


def test_network_actor_queries_remain_unfiltered():
    connection, cursor = _actor_view_connection([[], [], [], []])

    state_module._state_of_kokonut_actors(connection, None, None, location_ids=None)

    assert len(cursor.execute.call_args_list) == 4
    assert all(
        "fr.location_id = ANY(%s::uuid[])" not in call.args[0]
        for call in cursor.execute.call_args_list
    )
