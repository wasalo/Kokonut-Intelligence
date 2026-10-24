#!/usr/bin/env python3
"""
Tests for Waste Management
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from services.analytics.waste_management import (
    get_composting_efficiency,
    get_open_incidents,
    get_waste_dashboard,
    get_waste_summary,
    record_composting,
    record_recycling,
    record_waste,
    report_incident,
    resolve_incident,
)


class TestRecordWaste(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_waste_returns_waste_id(self):
        result = record_waste(
            self.conn, "loc-001", "organic", "Crop residues",
            50.0, "composting",
        )
        self.assertIn("waste_id", result)
        self.assertEqual(result["waste_type"], "organic")
        self.assertEqual(result["waste_name"], "Crop residues")
        self.assertEqual(result["quantity_kg"], 50.0)
        self.assertEqual(result["disposal_method"], "composting")
        self.conn.commit.assert_called_once()

    def test_record_waste_with_source_and_notes(self):
        result = record_waste(
            self.conn, "loc-001", "plastic", "Bags",
            10.0, "recycling", source="field A", notes="Clean plastic",
        )
        self.assertIn("waste_id", result)
        self.assertEqual(result["location_id"], "loc-001")

    def test_record_waste_calls_execute(self):
        record_waste(
            self.conn, "loc-001", "chemical", "Solvent", 5.0, "incineration",
            source="store room", notes="Empty container",
        )
        self.mock_cursor.execute.assert_called_once()
        self.mock_cursor.close.assert_called_once()
        query, params = self.mock_cursor.execute.call_args.args
        self.assertIn("INSERT INTO waste_stream", query)
        self.assertIn("record_date", query)
        self.assertIn("quantity_unit", query)
        self.assertIn("'recorded'", query)
        self.assertNotIn("waste_stream_record", query)
        self.assertNotIn("'draft'", query)
        self.assertEqual(params[2], "other")
        self.assertEqual(params[6], "other")
        self.assertEqual(params[7], "Empty container")
        self.assertEqual(json.loads(params[8]), {
            "source": "store room",
            "legacy_waste_type": "chemical",
            "legacy_disposal_method": "incineration",
        })


class TestRecordComposting(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_composting_returns_compost_id(self):
        result = record_composting(
            self.conn, "loc-001", "Banana stems", 100.0, "vermicomposting",
        )
        self.assertIn("compost_id", result)
        self.assertEqual(result["feedstock_type"], "Banana stems")
        self.assertEqual(result["feedstock_kg"], 100.0)
        self.assertEqual(result["compost_method"], "vermicomposting")
        self.conn.commit.assert_called_once()

    def test_record_composting_with_output(self):
        result = record_composting(
            self.conn, "loc-001", "Maize stover", 200.0, "aerobic",
            output_kg=80.0,
        )
        self.assertEqual(result["output_kg"], 80.0)
        self.assertEqual(result["output_yield_pct"], 40.0)

    def test_record_composting_with_quality_params(self):
        result = record_composting(
            self.conn, "loc-001", "Coffee pulp", 50.0, "bokashi",
            duration_days=30, temperature_c=55.0, ph=6.5, moisture_pct=60.0,
        )
        self.assertIn("compost_id", result)
        self.assertEqual(result["location_id"], "loc-001")


class TestRecordRecycling(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_recycling_returns_recycle_id(self):
        result = record_recycling(
            self.conn, "loc-001", "plastic", 15.0, "Recycling center",
        )
        self.assertIn("recycle_id", result)
        self.assertEqual(result["material_type"], "plastic")
        self.assertEqual(result["quantity_kg"], 15.0)
        self.assertEqual(result["destination"], "Recycling center")
        self.conn.commit.assert_called_once()

    def test_record_recycling_with_revenue(self):
        result = record_recycling(
            self.conn, "loc-001", "metal", 8.0, "Scrap yard", revenue=12.50,
        )
        self.assertEqual(result["revenue"], 12.50)


class TestReportIncident(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_report_incident_returns_incident_id(self):
        result = report_incident(
            self.conn, "loc-001", "chemical_spill", "high",
            "Pesticide container leak", "Near stream",
        )
        self.assertIn("incident_id", result)
        self.assertEqual(result["incident_type"], "chemical_spill")
        self.assertEqual(result["severity"], "high")
        self.assertEqual(result["status"], "open")
        self.conn.commit.assert_called_once()

    def test_report_incident_with_reported_by(self):
        result = report_incident(
            self.conn, "loc-001", "water_contamination", "critical",
            "Fertilizer runoff", "River bank",
            reported_by="field_worker_01",
        )
        self.assertEqual(result["affected_area"], "River bank")


class TestResolveIncident(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_resolve_incident_updates_incident(self):
        self.mock_cursor.fetchone.return_value = (
            "inc-001", "chemical_spill", "high",
        )
        result = resolve_incident(
            self.conn, "inc-001", "Cleaned and neutralized soil",
            resolution_date="2026-07-10",
        )
        self.assertEqual(result["incident_id"], "inc-001")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["remedial_action"], "Cleaned and neutralized soil")
        self.assertEqual(result["resolution_date"], "2026-07-10")
        self.conn.commit.assert_called_once()

    def test_resolve_incident_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            resolve_incident(self.conn, "nonexistent", "Action")


class TestWasteSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_waste_summary_returns_summary(self):
        self.mock_cursor.description = [
            ("waste_type",), ("total_kg",), ("record_count",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("organic", 100.0, 5)],
            [("composting", 100.0, 5)],
        ]
        self.mock_cursor.fetchone.return_value = (100.0, 5)
        result = get_waste_summary(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_waste_kg"], 100.0)
        self.assertEqual(result["total_records"], 5)
        self.assertEqual(len(result["by_type"]), 1)
        self.assertEqual(len(result["by_disposal_method"]), 1)
        statements = self.mock_cursor.execute.call_args_list
        self.assertEqual(len(statements), 3)
        for call in statements:
            query, params = call.args
            self.assertIn("FROM waste_stream", query)
            self.assertNotIn("waste_stream_record", query)
            self.assertIn("record_date >= CURRENT_DATE - (%s - 1)", query)
            self.assertIn("status = 'verified'", query)
            self.assertEqual(params, ("loc-001", 30))
        self.mock_cursor.close.assert_called_once()

    def test_get_waste_summary_rejects_invalid_day_window_before_cursor(self):
        for days in (0, -1, 1.5, True, "30"):
            with self.subTest(days=days):
                conn = MagicMock()
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    get_waste_summary(conn, "loc-001", days=days)
                conn.cursor.assert_not_called()

    def test_get_waste_summary_empty(self):
        self.mock_cursor.description = [
            ("waste_type",), ("total_kg",), ("record_count",),
        ]
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (None, None)
        result = get_waste_summary(self.conn, "loc-001")
        self.assertEqual(result["total_waste_kg"], 0)
        self.assertEqual(result["total_records"], 0)

    def test_get_waste_summary_closes_cursor_when_query_fails(self):
        self.mock_cursor.execute.side_effect = RuntimeError("synthetic query failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic query failure"):
            get_waste_summary(self.conn, "loc-001")
        self.mock_cursor.close.assert_called_once()


class TestCompostingEfficiency(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_composting_efficiency_returns_efficiency(self):
        method_columns = [
            ("compost_method",), ("batches",), ("avg_yield_pct",),
            ("avg_feedstock_kg",), ("avg_output_kg",), ("avg_duration_days",),
        ]
        quality_columns = [
            ("ph",), ("moisture_pct",), ("temperature_c",),
            ("output_yield_pct",), ("recorded_at",),
        ]

        def set_description(query, _params):
            if "GROUP BY compost_method" in query:
                self.mock_cursor.description = method_columns
            elif "ORDER BY compost_date DESC" in query:
                self.mock_cursor.description = quality_columns

        self.mock_cursor.execute.side_effect = set_description
        self.mock_cursor.fetchall.side_effect = [
            [("vermicomposting", 3, 45.0, 100.0, 45.0, 30.0)],
            [(6.5, 60.0, 55.0, 40.0, date(2026, 10, 24))],
        ]
        self.mock_cursor.fetchone.return_value = (3, 300.0, 135.0)
        result = get_composting_efficiency(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_batches"], 3)
        self.assertEqual(result["total_feedstock_kg"], 300.0)
        self.assertEqual(result["total_output_kg"], 135.0)
        self.assertEqual(result["overall_yield_pct"], 45.0)
        self.assertEqual(result["by_method"][0]["avg_yield_pct"], 45.0)
        self.assertEqual(result["recent_quality"], [{
            "ph": 6.5, "moisture_pct": 60.0, "temperature_c": 55.0,
            "output_yield_pct": 40.0, "recorded_at": date(2026, 10, 24),
        }])
        statements = self.mock_cursor.execute.call_args_list
        self.assertEqual(len(statements), 3)
        for call in statements:
            query, params = call.args
            self.assertIn("FROM composting_record", query)
            self.assertIn("location_id = %s", query)
            self.assertIn("status = 'verified'", query)
            self.assertNotIn("status IN ('verified', 'published')", query)
            self.assertEqual(params, ("loc-001",))
        self.assertIn("finished_volume_kg", statements[0].args[0])
        self.assertIn("finished_volume_kg", statements[1].args[0])
        self.assertNotIn("output_yield_pct", statements[0].args[0])
        self.mock_cursor.close.assert_called_once()

    def test_get_composting_efficiency_zero_feedstock(self):
        self.mock_cursor.description = [
            ("compost_method",), ("batches",), ("avg_yield_pct",),
            ("avg_feedstock_kg",), ("avg_output_kg",), ("avg_duration_days",),
        ]
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (0, None, None)
        result = get_composting_efficiency(self.conn, "loc-001")
        self.assertEqual(result["overall_yield_pct"], None)

    def test_get_composting_efficiency_closes_cursor_when_query_fails(self):
        self.mock_cursor.execute.side_effect = RuntimeError("synthetic query failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic query failure"):
            get_composting_efficiency(self.conn, "loc-001")
        self.mock_cursor.close.assert_called_once()

    def test_record_composting_uses_canonical_schema_and_preserves_legacy_inputs(self):
        record_composting(
            self.conn, "loc-001", "Banana stems", 100.0, "vermicomposting",
            output_kg=45.0, ph=6.5, metadata={"source": "field"},
        )

        query, params = self.mock_cursor.execute.call_args.args
        self.assertIn("compost_date", query)
        self.assertIn("finished_volume_kg", query)
        self.assertIn("status", query)
        for removed_column in ("output_kg", "output_yield_pct", " ph,"):
            self.assertNotIn(removed_column, query)
        self.assertEqual(params[3], "other")
        self.assertEqual(params[5], "vermiculture")
        self.assertEqual(params[9], 45.0)
        saved_metadata = json.loads(params[11])
        self.assertEqual(saved_metadata["ph"], 6.5)
        self.assertEqual(saved_metadata["source"], "field")
        self.assertEqual(saved_metadata["legacy_composting_inputs"], {
            "feedstock_type": "Banana stems",
            "compost_method": "vermicomposting",
        })
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestOpenIncidents(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_open_incidents_returns_incidents(self):
        self.mock_cursor.description = [
            ("id",), ("incident_type",), ("severity",), ("description",),
            ("affected_area",), ("reported_by",), ("created_at",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("inc-001", "chemical_spill", "high", "Leak", "Stream", "user1", "2026-07-01")],
            [("high", 1)],
        ]
        self.mock_cursor.fetchone.return_value = (5,)
        result = get_open_incidents(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["open_count"], 1)
        self.assertEqual(result["resolved_count"], 5)
        self.assertEqual(result["severity_breakdown"]["high"], 1)

    def test_get_open_incidents_empty(self):
        self.mock_cursor.description = [
            ("id",), ("incident_type",), ("severity",), ("description",),
            ("affected_area",), ("reported_by",), ("created_at",),
        ]
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (0,)
        result = get_open_incidents(self.conn, "loc-001")
        self.assertEqual(result["open_count"], 0)


class TestWasteDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()

    @patch("services.analytics.waste_management.get_open_incidents")
    @patch("services.analytics.waste_management.get_composting_efficiency")
    @patch("services.analytics.waste_management.get_waste_summary")
    def test_get_waste_dashboard_returns_dashboard(self, mock_ws, mock_ce, mock_oi):
        mock_ws.return_value = {
            "location_id": "loc-001",
            "total_waste_kg": 100.0,
            "total_records": 5,
            "by_type": [{"waste_type": "organic", "total_kg": 100.0, "record_count": 5}],
            "by_disposal_method": [
                {"disposal_method": "composting", "total_kg": 60.0, "record_count": 3},
                {"disposal_method": "recycling", "total_kg": 30.0, "record_count": 2},
                {"disposal_method": "landfill", "total_kg": 10.0, "record_count": 1},
            ],
        }
        mock_ce.return_value = {
            "location_id": "loc-001",
            "total_batches": 3,
            "total_feedstock_kg": 300.0,
            "total_output_kg": 135.0,
            "overall_yield_pct": 45.0,
            "by_method": [],
            "recent_quality": [],
        }
        mock_oi.return_value = {
            "location_id": "loc-001",
            "open_count": 1,
            "resolved_count": 0,
            "severity_breakdown": {"high": 1},
            "incidents": [],
        }

        result = get_waste_dashboard(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertIn("waste_summary", result)
        self.assertIn("composting_efficiency", result)
        self.assertIn("incidents", result)
        self.assertIn("key_metrics", result)
        self.assertEqual(result["key_metrics"]["total_waste_kg"], 100.0)
        self.assertEqual(result["key_metrics"]["composted_kg"], 60.0)
        self.assertEqual(result["key_metrics"]["recycled_kg"], 30.0)
        self.assertEqual(result["key_metrics"]["landfill_kg"], 10.0)
        self.assertEqual(result["key_metrics"]["diversion_rate_pct"], 90.0)

    @patch("services.analytics.waste_management.get_open_incidents")
    @patch("services.analytics.waste_management.get_composting_efficiency")
    @patch("services.analytics.waste_management.get_waste_summary")
    def test_get_waste_dashboard_zero_waste(self, mock_ws, mock_ce, mock_oi):
        mock_ws.return_value = {
            "location_id": "loc-001",
            "total_waste_kg": 0,
            "total_records": 0,
            "by_type": [],
            "by_disposal_method": [],
        }
        mock_ce.return_value = {
            "location_id": "loc-001",
            "total_batches": 0,
            "total_feedstock_kg": 0,
            "total_output_kg": 0,
            "overall_yield_pct": None,
            "by_method": [],
            "recent_quality": [],
        }
        mock_oi.return_value = {
            "location_id": "loc-001",
            "open_count": 0,
            "resolved_count": 0,
            "severity_breakdown": {},
            "incidents": [],
        }

        result = get_waste_dashboard(self.conn, "loc-001")
        self.assertEqual(result["key_metrics"]["total_waste_kg"], 0)
        self.assertEqual(result["key_metrics"]["diversion_rate_pct"], None)


if __name__ == "__main__":
    unittest.main()
