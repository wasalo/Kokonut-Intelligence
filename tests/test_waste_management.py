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

    def test_unscoped_waste_summary_fails_before_cursor_access(self):
        conn = MagicMock()
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            get_waste_summary(conn, "loc-001")
        conn.cursor.assert_not_called()
        conn.commit.assert_not_called()

    def test_unscoped_waste_summary_cli_fails_before_database_access(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run(["waste-summary", "--location-id", "loc-001"])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway waste summary", stderr.getvalue())


class TestCompostingEfficiency(unittest.TestCase):

    def test_unscoped_composting_summary_fails_before_cursor_access(self):
        conn = MagicMock()
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            get_composting_efficiency(conn, "loc-001")
        conn.cursor.assert_not_called()
        conn.commit.assert_not_called()

    def test_unscoped_composting_summary_cli_fails_before_database_access(self):
        connection_factory = MagicMock(side_effect=AssertionError("database opened"))
        stderr = io.StringIO()
        with patch.object(waste_management.cli, "_connection_factory", connection_factory):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                waste_management.cli.run(["composting-efficiency", "--location-id", "loc-001"])
        self.assertEqual(error.exception.code, 1)
        connection_factory.assert_not_called()
        self.assertIn("authenticated operator Gateway waste summary", stderr.getvalue())

    def test_legacy_composting_writer_still_fails_before_cursor(self):
        conn = MagicMock()
        with self.assertRaisesRegex(TenantContextDenied, "authenticated operator Gateway"):
            record_composting(
                conn, "loc-001", "Banana stems", 100.0, "vermicomposting",
                output_kg=45.0, ph=6.5, metadata={"source": "field"},
            )
        conn.cursor.assert_not_called()
        conn.commit.assert_not_called()


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
