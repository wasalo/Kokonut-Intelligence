#!/usr/bin/env python3
"""
Tests for Waste Management
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from contextlib import redirect_stderr
from datetime import date
from unittest.mock import MagicMock, patch

from services.analytics import waste_management
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
from services.common.tenant_context import TenantContextDenied


class TestRecordWaste(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_legacy_helper_fails_before_opening_cursor(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            record_waste(
                self.conn, "loc-001", "organic", "Crop residues",
                50.0, "composting", source="field A", notes="Clean plastic",
            )
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()

    def test_legacy_cli_writer_fails_before_opening_database(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run([
                    "record-waste", "--location-id", "loc-001",
                    "--waste-type", "organic", "--waste-name", "Crop residues",
                    "--quantity", "50", "--disposal-method", "composting",
                ])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway waste-capture workflow", stderr.getvalue())


class TestRecordComposting(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_legacy_helper_fails_before_opening_cursor(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            record_composting(
                self.conn, "loc-001", "Banana stems", 100.0, "vermicomposting",
                duration_days=30, output_kg=45, temperature_c=55, ph=6.5,
                moisture_pct=60,
            )
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()

    def test_legacy_cli_writer_fails_before_opening_database(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run([
                    "record-composting", "--location-id", "loc-001",
                    "--feedstock", "Banana stems", "--feedstock-kg", "100",
                    "--method", "vermicomposting",
                ])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway composting-capture workflow", stderr.getvalue())


class TestRecordRecycling(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_legacy_recycling_helper_fails_before_opening_cursor(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            record_recycling(
                self.conn, "loc-001", "plastic", 15.0, "Recycling center",
                revenue=5.0, notes="synthetic",
            )
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()

    def test_legacy_recycling_cli_fails_before_opening_database(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run([
                    "record-recycling", "--location-id", "loc-001",
                    "--material", "plastic", "--quantity", "15",
                    "--destination", "Recycling center",
                ])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway recycling-capture workflow", stderr.getvalue())


class TestReportIncident(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_legacy_report_helper_fails_before_opening_cursor(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            report_incident(
                self.conn, "loc-001", "chemical_spill", "high",
                "Pesticide container leak", "Near stream",
            )
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()

    def test_legacy_report_cli_fails_before_opening_database(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run([
                    "report-incident", "--location-id", "loc-001",
                    "--incident-type", "chemical_spill", "--severity", "high",
                    "--description", "Synthetic report", "--affected-area", "North plot",
                ])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway incident-capture workflow", stderr.getvalue())


class TestResolveIncident(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_legacy_resolve_helper_fails_before_opening_cursor(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            resolve_incident(self.conn, "inc-001", "Cleaned and neutralized soil")
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()

    def test_legacy_resolve_cli_fails_before_opening_database(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run([
                    "resolve-incident", "--incident-id", "11111111-1111-4111-8111-111111111111",
                    "--remedial-action", "Synthetic cleanup",
                ])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway review workflow", stderr.getvalue())


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

    def test_legacy_composting_helper_fails_before_opening_cursor(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            record_composting(
                self.conn, "loc-001", "Banana stems", 100.0, "vermicomposting",
                output_kg=45.0, ph=6.5, metadata={"source": "field"},
            )
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()


class TestOpenIncidents(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_unscoped_incident_reader_fails_before_cursor_access(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            get_open_incidents(self.conn, "loc-001")
        self.conn.cursor.assert_not_called()

    def test_unscoped_incident_cli_fails_before_database_access(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run([
                    "open-incidents", "--location-id", "loc-001",
                ])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway", stderr.getvalue())


class TestWasteDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()

    def test_unscoped_dashboard_fails_before_cursor_access(self):
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            get_waste_dashboard(self.conn, "loc-001")
        self.conn.cursor.assert_not_called()

    def test_unscoped_dashboard_cli_fails_before_database_access(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run([
                    "dashboard", "--location-id", "loc-001",
                ])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
