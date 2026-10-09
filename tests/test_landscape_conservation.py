#!/usr/bin/env python3
"""
Tests for Landscape Conservation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone

from services.analytics.landscape_conservation import (
    create_habitat_zone,
    create_corridor,
    record_hedgerow,
    record_buffer_check,
    record_biodiversity_score,
    get_habitat_summary,
    get_corridor_status,
    get_buffer_compliance,
    get_biodiversity_trends,
    get_landscape_dashboard,
)


class TestCreateHabitatZone(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_create_habitat_zone_returns_zone_id(self):
        result = create_habitat_zone(
            self.conn, "loc-001", "Riparian Buffer", "riparian", 0.5,
        )
        self.assertIn("zone_id", result)
        self.assertEqual(result["zone_name"], "Riparian Buffer")
        self.assertEqual(result["habitat_type"], "riparian")
        self.assertEqual(result["area_ha"], 0.5)
        self.assertEqual(result["biodiversity_value"], "medium")
        self.conn.commit.assert_called_once()

    def test_create_habitat_zone_with_biodiversity(self):
        result = create_habitat_zone(
            self.conn, "loc-001", "Wetland", "wetland", 1.2,
            biodiversity_value="critical", perimeter_m=500.0,
        )
        self.assertEqual(result["biodiversity_value"], "critical")
        self.assertEqual(result["location_id"], "loc-001")

    def test_create_habitat_zone_calls_execute(self):
        create_habitat_zone(self.conn, "loc-001", "Forest", "forest_patch", 2.0)
        self.mock_cursor.execute.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestCreateCorridor(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_create_corridor_returns_corridor_id(self):
        result = create_corridor(
            self.conn, "loc-001", "Stream Link",
            source_habitat_id="hab-001", target_habitat_id="hab-002",
        )
        self.assertIn("corridor_id", result)
        self.assertEqual(result["corridor_name"], "Stream Link")
        self.assertEqual(result["source_habitat_id"], "hab-001")
        self.assertEqual(result["target_habitat_id"], "hab-002")
        self.conn.commit.assert_called_once()

    def test_create_corridor_with_dimensions(self):
        result = create_corridor(
            self.conn, "loc-001", "Hedgerow Link",
            width_m=15.0, length_m=200.0, vegetation_type="mixed_shrub",
        )
        self.assertEqual(result["width_m"], 15.0)
        self.assertEqual(result["length_m"], 200.0)


class TestRecordHedgerow(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_hedgerow_returns_hedgerow_id(self):
        result = record_hedgerow(
            self.conn, "loc-001", hedgerow_name="North Windbreak",
            species_mix=["calliandra", "leucaena"],
            length_m=180.0, purpose=["windbreak", "biodiversity"],
        )
        self.assertIn("hedgerow_id", result)
        self.assertEqual(result["hedgerow_name"], "North Windbreak")
        self.assertEqual(result["species_mix"], ["calliandra", "leucaena"])
        self.assertEqual(result["length_m"], 180.0)
        self.assertEqual(result["purpose"], ["windbreak", "biodiversity"])
        self.conn.commit.assert_called_once()

    def test_record_hedgerow_minimal(self):
        result = record_hedgerow(self.conn, "loc-001")
        self.assertIn("hedgerow_id", result)
        self.assertEqual(result["species_mix"], [])
        self.assertEqual(result["purpose"], [])


class TestRecordBufferCheck(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_buffer_check_returns_check_id(self):
        result = record_buffer_check(
            self.conn, "loc-001",
            habitat_zone_id="hz-001", buffer_width_m=12.0,
            minimum_required_m=10.0, vegetation_coverage_pct=85.0,
        )
        self.assertIn("check_id", result)
        self.assertEqual(result["compliant"], True)
        self.assertEqual(result["buffer_width_m"], 12.0)
        self.assertEqual(result["minimum_required_m"], 10.0)
        self.conn.commit.assert_called_once()

    def test_record_buffer_check_non_compliant(self):
        result = record_buffer_check(
            self.conn, "loc-001", buffer_width_m=5.0,
            minimum_required_m=10.0,
        )
        self.assertEqual(result["compliant"], False)

    def test_record_buffer_check_with_erosion(self):
        result = record_buffer_check(
            self.conn, "loc-001", buffer_width_m=10.0,
            minimum_required_m=10.0, erosion_observed=True,
        )
        self.assertEqual(result["erosion_observed"], True)


class TestRecordBiodiversityScore(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_biodiversity_score_returns_score_id(self):
        result = record_biodiversity_score(
            self.conn, "loc-001",
            species_richness=34, shannon_index=2.45,
            habitat_diversity_index=1.8, connectivity_score=6.5,
            overall_score=7.2,
        )
        self.assertIn("score_id", result)
        self.assertEqual(result["species_richness"], 34)
        self.assertEqual(result["shannon_index"], 2.45)
        self.assertEqual(result["overall_score"], 7.2)
        self.conn.commit.assert_called_once()

    def test_record_biodiversity_score_with_assessor(self):
        result = record_biodiversity_score(
            self.conn, "loc-001", overall_score=8.0,
            assessor="ecologist_01",
        )
        self.assertEqual(result["location_id"], "loc-001")


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
