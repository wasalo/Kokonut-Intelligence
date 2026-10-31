#!/usr/bin/env python3
"""
Tests for Landscape Conservation
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from services.analytics.landscape_conservation import (
    create_corridor,
    create_habitat_zone,
    get_biodiversity_trends,
    get_buffer_compliance,
    get_corridor_status,
    get_habitat_summary,
    get_landscape_dashboard,
    record_biodiversity_score,
    record_buffer_check,
    record_hedgerow,
)


class TestRetiredLandscapeWriters(unittest.TestCase):
    def test_direct_writers_fail_before_database_access(self):
        calls = (
            (create_habitat_zone, ("loc-001", "Zone", "riparian", 1.0)),
            (create_corridor, ("loc-001", "Corridor")),
            (record_hedgerow, ("loc-001",)),
            (record_buffer_check, ("loc-001",)),
            (record_biodiversity_score, ("loc-001",)),
        )
        for writer, args in calls:
            with self.subTest(writer=writer.__name__):
                conn = MagicMock()
                with self.assertRaisesRegex(
                    RuntimeError, "Unscoped landscape-conservation writes are retired"
                ):
                    writer(conn, *args)
                conn.cursor.assert_not_called()
                conn.commit.assert_not_called()
                conn.rollback.assert_not_called()

    def test_legacy_write_commands_fail_before_database_access(self):
        from services.analytics import landscape_conservation as landscape

        cases = (
            ("create-habitat", ["--location-id", "loc-1", "--name", "Zone", "--type", "riparian", "--area", "1"]),
            ("create-corridor", ["--location-id", "loc-1", "--name", "Corridor"]),
            ("record-hedgerow", ["--location-id", "loc-1"]),
            ("record-buffer-check", ["--location-id", "loc-1"]),
            ("record-biodiversity", ["--location-id", "loc-1"]),
        )
        for command_name, arguments in cases:
            with self.subTest(command=command_name):
                command = next(
                    item for item in landscape.cli._commands
                    if item.name == command_name
                )
                self.assertFalse(command.needs_db)
                with patch.object(
                    landscape.cli,
                    "_connection_factory",
                    side_effect=AssertionError(
                        "retired landscape writer must not open the database"
                    ),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "Unscoped landscape-conservation writes are retired",
                    ):
                        landscape.cli.main([command_name, *arguments])


class TestHabitatSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_habitat_summary_returns_summary(self):
        self.mock_cursor.description = [
            ("habitat_id",), ("zone_name",), ("habitat_type",), ("area_ha",),
            ("perimeter_m",), ("biodiversity_value",), ("status",),
            ("corridor_count",), ("compliant_buffer_checks",), ("total_buffer_checks",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("hz-001", "Riparian Buffer", "riparian", 0.5, 200.0, "high", "active", 2, 5, 5),
        ]
        self.mock_cursor.fetchone.return_value = (1, 0.5, 0, 1)
        result = get_habitat_summary(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_zones"], 1)
        self.assertEqual(result["total_area_ha"], 0.5)
        self.assertEqual(result["high_value_habitats"], 1)
        self.assertEqual(len(result["zones"]), 1)

    def test_get_habitat_summary_empty(self):
        self.mock_cursor.description = [
            ("habitat_id",), ("zone_name",), ("habitat_type",), ("area_ha",),
            ("perimeter_m",), ("biodiversity_value",), ("status",),
            ("corridor_count",), ("compliant_buffer_checks",), ("total_buffer_checks",),
        ]
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0, None, 0, 0)
        result = get_habitat_summary(self.conn, "loc-001")
        self.assertEqual(result["total_zones"], 0)


class TestCorridorStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_corridor_status_returns_status(self):
        self.mock_cursor.description = [
            ("corridor_id",), ("corridor_name",), ("source_habitat",),
            ("target_habitat",), ("width_m",), ("length_m",),
            ("vegetation_type",), ("condition",), ("last_survey_date",),
            ("connectivity_status",), ("status",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("c-001", "Stream Link", "hz-001", "hz-002", 15.0, 200.0,
             "mixed", "good", None, "connected", "active"),
        ]
        self.mock_cursor.fetchone.return_value = (1, 1, 200.0, 15.0)
        result = get_corridor_status(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_corridors"], 1)
        self.assertEqual(result["healthy_corridors"], 1)
        self.assertEqual(result["total_length_m"], 200.0)
        self.assertEqual(len(result["corridors"]), 1)


class TestBufferCompliance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_buffer_compliance_returns_compliance(self):
        self.mock_cursor.description = [
            ("habitat_zone_id",), ("habitat_zone_name",), ("total_checks",),
            ("compliant_checks",), ("compliance_rate_pct",), ("avg_buffer_width_m",),
            ("avg_minimum_required_m",), ("avg_vegetation_coverage_pct",),
            ("erosion_incidents",), ("last_check_date",),
        ]
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (10, 8, 80.0, 1)
        result = get_buffer_compliance(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_checks"], 10)
        self.assertEqual(result["compliant_checks"], 8)
        self.assertEqual(result["overall_compliance_pct"], 80.0)
        self.assertEqual(result["total_erosion_incidents"], 1)

    def test_get_buffer_compliance_empty(self):
        self.mock_cursor.description = [
            ("habitat_zone_id",), ("habitat_zone_name",), ("total_checks",),
            ("compliant_checks",), ("compliance_rate_pct",), ("avg_buffer_width_m",),
            ("avg_minimum_required_m",), ("avg_vegetation_coverage_pct",),
            ("erosion_incidents",), ("last_check_date",),
        ]
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0, 0, None, 0)
        result = get_buffer_compliance(self.conn, "loc-001")
        self.assertEqual(result["total_checks"], 0)


class TestBiodiversityTrends(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_biodiversity_trends_returns_trends(self):
        self.mock_cursor.description = [
            ("assessment_date",), ("species_richness",), ("shannon_index",),
            ("habitat_diversity_index",), ("connectivity_score",),
            ("overall_score",), ("prev_overall_score",), ("score_change",),
            ("prev_species_richness",), ("prev_connectivity_score",),
            ("assessor",), ("status",),
        ]
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 7, 1), 34, 2.45, 1.8, 6.5, 7.2, 6.8, 0.4, 30, 6.0, "eco1", "recorded"),
        ]
        self.mock_cursor.fetchone.return_value = (1, 7.2, 2.45, 34.0, date(2026, 1, 1), date(2026, 7, 1))
        result = get_biodiversity_trends(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_assessments"], 1)
        self.assertEqual(result["avg_overall_score"], 7.2)
        self.assertEqual(len(result["assessments"]), 1)


class TestLandscapeDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()

    @patch("services.analytics.landscape_conservation.get_biodiversity_trends")
    @patch("services.analytics.landscape_conservation.get_buffer_compliance")
    @patch("services.analytics.landscape_conservation.get_corridor_status")
    @patch("services.analytics.landscape_conservation.get_habitat_summary")
    def test_get_landscape_dashboard_returns_dashboard(
        self, mock_hs, mock_cs, mock_bc, mock_bt,
    ):
        mock_hs.return_value = {
            "location_id": "loc-001",
            "total_zones": 2,
            "total_area_ha": 1.5,
            "critical_habitats": 0,
            "high_value_habitats": 1,
            "zones": [],
        }
        mock_cs.return_value = {
            "location_id": "loc-001",
            "total_corridors": 1,
            "healthy_corridors": 1,
            "total_length_m": 200.0,
            "avg_width_m": 15.0,
            "corridors": [],
        }
        mock_bc.return_value = {
            "location_id": "loc-001",
            "total_checks": 5,
            "compliant_checks": 4,
            "overall_compliance_pct": 80.0,
            "total_erosion_incidents": 0,
            "by_habitat": [],
        }
        mock_bt.return_value = {
            "location_id": "loc-001",
            "total_assessments": 1,
            "avg_overall_score": 7.2,
            "avg_shannon_index": 2.45,
            "avg_species_richness": 34.0,
            "first_assessment": "2026-01-01",
            "last_assessment": "2026-07-01",
            "assessments": [],
        }

        result = get_landscape_dashboard(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertIn("habitats", result)
        self.assertIn("corridors", result)
        self.assertIn("buffer_compliance", result)
        self.assertIn("biodiversity", result)
        self.assertIn("connectivity_ratio_pct", result)
        self.assertEqual(result["connectivity_ratio_pct"], 50.0)

    @patch("services.analytics.landscape_conservation.get_biodiversity_trends")
    @patch("services.analytics.landscape_conservation.get_buffer_compliance")
    @patch("services.analytics.landscape_conservation.get_corridor_status")
    @patch("services.analytics.landscape_conservation.get_habitat_summary")
    def test_get_landscape_dashboard_zero_habitats(
        self, mock_hs, mock_cs, mock_bc, mock_bt,
    ):
        mock_hs.return_value = {
            "location_id": "loc-001",
            "total_zones": 0,
            "total_area_ha": 0,
            "critical_habitats": 0,
            "high_value_habitats": 0,
            "zones": [],
        }
        mock_cs.return_value = {
            "location_id": "loc-001",
            "total_corridors": 0,
            "healthy_corridors": 0,
            "total_length_m": 0,
            "avg_width_m": 0,
            "corridors": [],
        }
        mock_bc.return_value = {
            "location_id": "loc-001",
            "total_checks": 0,
            "compliant_checks": 0,
            "overall_compliance_pct": 0,
            "total_erosion_incidents": 0,
            "by_habitat": [],
        }
        mock_bt.return_value = {
            "location_id": "loc-001",
            "total_assessments": 0,
            "avg_overall_score": None,
            "avg_shannon_index": None,
            "avg_species_richness": None,
            "first_assessment": None,
            "last_assessment": None,
            "assessments": [],
        }

        result = get_landscape_dashboard(self.conn, "loc-001")
        self.assertEqual(result["connectivity_ratio_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
