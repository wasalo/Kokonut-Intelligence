#!/usr/bin/env python3
"""
Tests for Pollinator Health
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone

from services.analytics.pollinator_health import (
    record_observation,
    create_habitat,
    record_pesticide_impact,
    add_hive,
    record_hive_inspection,
    get_pollinator_summary,
    get_habitat_inventory,
    get_pesticide_risk,
    get_hive_status,
    get_pollinator_dashboard,
)


class TestRecordObservation(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_observation_returns_observation_id(self):
        result = record_observation(
            self.conn, "loc-001", "honeybee", 50,
        )
        self.assertIn("observation_id", result)
        self.assertEqual(result["pollinator_type"], "honeybee")
        self.assertEqual(result["count"], 50)
        self.assertEqual(result["observation_method"], "visual")
        self.assertEqual(result["duration_minutes"], 15)
        self.conn.commit.assert_called_once()

    def test_record_observation_with_method(self):
        result = record_observation(
            self.conn, "loc-001", "butterfly", 12,
            observation_method="transect", duration_minutes=30,
        )
        self.assertEqual(result["observation_method"], "transect")
        self.assertEqual(result["duration_minutes"], 30)

    def test_record_observation_calls_execute(self):
        record_observation(self.conn, "loc-001", "bumblebee", 5)
        self.mock_cursor.execute.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestCreateHabitat(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_create_habitat_returns_habitat_id(self):
        result = create_habitat(
            self.conn, "loc-001", "Wildflower Strip", "wildflower", 200.0,
        )
        self.assertIn("habitat_id", result)
        self.assertEqual(result["habitat_name"], "Wildflower Strip")
        self.assertEqual(result["habitat_type"], "wildflower")
        self.assertEqual(result["area_m2"], 200.0)
        self.assertEqual(result["water_source"], False)
        self.conn.commit.assert_called_once()

    def test_create_habitat_with_species(self):
        result = create_habitat(
            self.conn, "loc-001", "Clover Patch", "clover", 150.0,
            plant_species=["white_clover", "red_clover"],
            bloom_start_month=3, bloom_end_month=9,
            water_source=True,
        )
        self.assertEqual(result["plant_species"], ["white_clover", "red_clover"])
        self.assertEqual(result["water_source"], True)

    def test_create_habitat_minimal(self):
        result = create_habitat(
            self.conn, "loc-001", "Nesting Area", "nesting", 50.0,
        )
        self.assertEqual(result["plant_species"], [])


class TestRecordPesticideImpact(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_pesticide_impact_returns_record_id(self):
        result = record_pesticide_impact(
            self.conn, "loc-001", date(2026, 6, 15),
            "Chlorpyrifos", "chlorpyrifos", "high",
        )
        self.assertIn("record_id", result)
        self.assertEqual(result["product_name"], "Chlorpyrifos")
        self.assertEqual(result["toxicity_class"], "high")
        self.assertEqual(result["pollinator_risk"], "high")
        self.assertEqual(result["pollinator_harm"], "lethal to foragers")
        self.conn.commit.assert_called_once()

    def test_record_pesticide_impact_low_toxicity(self):
        result = record_pesticide_impact(
            self.conn, "loc-001", date(2026, 6, 15),
            "Bt spray", "bacillus_thuringiensis", "low",
        )
        self.assertEqual(result["pollinator_risk"], "low")
        self.assertEqual(result["pollinator_harm"], "minimal")

    def test_record_pesticide_impact_very_high(self):
        result = record_pesticide_impact(
            self.conn, "loc-001", date(2026, 6, 15),
            "Neonicotinoid", "imidacloprid", "very_high",
        )
        self.assertEqual(result["pollinator_risk"], "very_high")
        self.assertEqual(result["pollinator_harm"], "lethal to colony")


class TestAddHive(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_add_hive_returns_record_id(self):
        result = add_hive(
            self.conn, "loc-001", "H-001",
        )
        self.assertIn("record_id", result)
        self.assertEqual(result["hive_id"], "H-001")
        self.assertEqual(result["colony_strength"], 5)
        self.assertEqual(result["queen_status"], "present")
        self.assertEqual(result["hive_type"], "langstroth")
        self.conn.commit.assert_called_once()

    def test_add_hive_custom_strength(self):
        result = add_hive(
            self.conn, "loc-001", "H-002",
            colony_strength=8, queen_status="absent", frame_count=12,
        )
        self.assertEqual(result["colony_strength"], 8)
        self.assertEqual(result["queen_status"], "absent")
        self.assertEqual(result["frame_count"], 12)


class TestRecordHiveInspection(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_record_hive_inspection_records_inspection(self):
        result = record_hive_inspection(
            self.conn, "H-001", colony_strength=9,
            queen_status="present", varroa_count=5,
        )
        self.assertIn("inspection_id", result)
        self.assertEqual(result["hive_id"], "H-001")
        self.assertEqual(result["colony_strength"], 9)
        self.assertEqual(result["queen_status"], "present")
        self.assertEqual(result["varroa_count"], 5)
        self.conn.commit.assert_called_once()

    def test_record_hive_inspection_updates_hive(self):
        result = record_hive_inspection(
            self.conn, "H-001", colony_strength=10,
        )
        calls = self.mock_cursor.execute.call_args_list
        update_calls = [c for c in calls if "UPDATE pollinator_hive" in str(c)]
        self.assertEqual(len(update_calls), 1)

    def test_record_hive_inspection_no_strength_update(self):
        result = record_hive_inspection(
            self.conn, "H-001", queen_seen=True,
        )
        calls = self.mock_cursor.execute.call_args_list
        update_calls = [c for c in calls if "UPDATE pollinator_hive" in str(c)]
        self.assertEqual(len(update_calls), 0)


class TestPollinatorSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_pollinator_summary_returns_summary(self):
        self.mock_cursor.description = [
            ("pollinator_type",), ("observations",), ("avg_count",),
            ("max_count",), ("first_obs",), ("last_obs",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("honeybee", 10, 45.0, 80, date(2026, 6, 1), date(2026, 7, 1)),
        ]
        self.mock_cursor.fetchone.side_effect = [
            (20.0,),  # first half avg
            (40.0,),  # second half avg
        ]
        result = get_pollinator_summary(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["period_days"], 30)
        self.assertEqual(len(result["pollinator_types"]), 1)
        self.assertEqual(result["pollinator_types"][0]["trend"], "increasing")

    def test_get_pollinator_summary_empty(self):
        self.mock_cursor.description = [
            ("pollinator_type",), ("observations",), ("avg_count",),
            ("max_count",), ("first_obs",), ("last_obs",),
        ]
        self.mock_cursor.fetchall.return_value = []
        result = get_pollinator_summary(self.conn, "loc-001")
        self.assertEqual(result["pollinator_types"], [])


class TestHabitatInventory(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_habitat_inventory_returns_inventory(self):
        self.mock_cursor.description = [
            ("id",), ("habitat_name",), ("habitat_type",), ("area_m2",),
            ("plant_species",), ("bloom_start_month",), ("bloom_end_month",),
            ("water_source",), ("nesting_sites",), ("management_notes",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("h-001", "Wildflower Strip", "wildflower", 200.0,
             '["clover", "daisy"]', 3, 9, True, "Logs", None),
        ]
        result = get_habitat_inventory(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_habitat_m2"], 200.0)
        self.assertEqual(result["habitat_count"], 1)
        self.assertEqual(len(result["habitats"]), 1)
        self.assertEqual(result["habitats"][0]["plant_species"], ["clover", "daisy"])

    def test_get_habitat_inventory_empty(self):
        self.mock_cursor.description = [
            ("id",), ("habitat_name",), ("habitat_type",), ("area_m2",),
            ("plant_species",), ("bloom_start_month",), ("bloom_end_month",),
            ("water_source",), ("nesting_sites",), ("management_notes",),
        ]
        self.mock_cursor.fetchall.return_value = []
        result = get_habitat_inventory(self.conn, "loc-001")
        self.assertEqual(result["total_habitat_m2"], 0)
        self.assertEqual(result["habitat_count"], 0)


class TestPesticideRisk(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_pesticide_risk_returns_risk(self):
        self.mock_cursor.description = [
            ("id",), ("application_date",), ("product_name",),
            ("active_ingredient",), ("toxicity_class",), ("application_rate",),
            ("rate_unit",), ("area_treated_m2",), ("bloom_stage_at_application",),
            ("pollinator_distance_m",), ("pollinator_risk",),
            ("pollinator_harm_description",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("r-001", date(2026, 6, 1), "Chlorpyrifos", "chlorpyrifos",
              "high", 2.0, "L/ha", 1000.0, "flowering", 50.0, "high", "lethal")],
            [("high", 1)],
        ]
        result = get_pesticide_risk(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_applications"], 1)
        self.assertEqual(result["overall_risk"], "elevated")
        self.assertEqual(len(result["applications"]), 1)

    def test_get_pesticide_risk_low(self):
        self.mock_cursor.description = [
            ("id",), ("application_date",), ("product_name",),
            ("active_ingredient",), ("toxicity_class",), ("application_rate",),
            ("rate_unit",), ("area_treated_m2",), ("bloom_stage_at_application",),
            ("pollinator_distance_m",), ("pollinator_risk",),
            ("pollinator_harm_description",),
        ]
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = []
        result = get_pesticide_risk(self.conn, "loc-001")
        self.assertEqual(result["overall_risk"], "low")

    def test_get_pesticide_risk_critical(self):
        self.mock_cursor.description = [
            ("id",), ("application_date",), ("product_name",),
            ("active_ingredient",), ("toxicity_class",), ("application_rate",),
            ("rate_unit",), ("area_treated_m2",), ("bloom_stage_at_application",),
            ("pollinator_distance_m",), ("pollinator_risk",),
            ("pollinator_harm_description",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [],
            [("high", 2), ("very_high", 2)],
        ]
        result = get_pesticide_risk(self.conn, "loc-001")
        self.assertEqual(result["overall_risk"], "critical")


class TestHiveStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()

    def test_get_hive_status_returns_status(self):
        c1 = MagicMock()
        c1.description = [
            ("id",), ("hive_id",), ("hive_type",), ("colony_strength",),
            ("queen_status",), ("frame_count",), ("queen_year",), ("status",),
        ]
        c1.fetchall.return_value = [
            ("h-001", "H-001", "langstroth", 8, "present", 10, 2025, "active"),
        ]

        c2 = MagicMock()
        c2.description = [
            ("inspection_date",), ("colony_strength",), ("queen_status",),
            ("queen_seen",), ("varroa_count",), ("brood_pattern",),
            ("honey_stores",), ("disease_signs",), ("swarm_cells",),
        ]
        c2.fetchone.return_value = (
            date(2026, 7, 1), 8, "present", True, 3, "solid", "adequate", None, False,
        )

        c3 = MagicMock()
        c3.fetchone.return_value = (45.0,)

        self.conn.cursor.side_effect = [c1, c2, c3]

        result = get_hive_status(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_hives"], 1)
        self.assertEqual(result["active_hives"], 1)
        self.assertEqual(result["avg_colony_strength"], 8.0)
        self.assertEqual(len(result["hives"]), 1)

    def test_get_hive_status_empty(self):
        c1 = MagicMock()
        c1.description = [
            ("id",), ("hive_id",), ("hive_type",), ("colony_strength",),
            ("queen_status",), ("frame_count",), ("queen_year",), ("status",),
        ]
        c1.fetchall.return_value = []
        self.conn.cursor.return_value = c1

        result = get_hive_status(self.conn, "loc-001")
        self.assertEqual(result["total_hives"], 0)
        self.assertEqual(result["active_hives"], 0)


class TestPollinatorDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()

    @patch("services.analytics.pollinator_health.get_hive_status")
    @patch("services.analytics.pollinator_health.get_pesticide_risk")
    @patch("services.analytics.pollinator_health.get_habitat_inventory")
    @patch("services.analytics.pollinator_health.get_pollinator_summary")
    def test_get_pollinator_dashboard_returns_dashboard(
        self, mock_summary, mock_habitat, mock_pesticide, mock_hive,
    ):
        mock_summary.return_value = {
            "location_id": "loc-001",
            "period_days": 30,
            "pollinator_types": [
                {"pollinator_type": "honeybee", "observations": 10,
                 "avg_count": 45.0, "max_count": 80,
                 "first_obs": date(2026, 6, 1), "last_obs": date(2026, 7, 1),
                 "trend": "increasing", "change_pct": 50.0},
            ],
        }
        mock_habitat.return_value = {
            "location_id": "loc-001",
            "total_habitat_m2": 200.0,
            "habitat_count": 1,
            "habitats": [],
        }
        mock_pesticide.return_value = {
            "location_id": "loc-001",
            "period_days": 90,
            "total_applications": 1,
            "overall_risk": "elevated",
            "risk_distribution": {"high": 1},
            "applications": [],
        }
        mock_hive.return_value = {
            "location_id": "loc-001",
            "total_hives": 2,
            "active_hives": 2,
            "avg_colony_strength": 7.5,
            "hives": [],
        }

        result = get_pollinator_dashboard(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertIn("observations", result)
        self.assertIn("habitats", result)
        self.assertIn("pesticide_risk", result)
        self.assertIn("hives", result)
        self.assertIn("generated_at", result)
        self.assertEqual(result["observations"]["total_observations"], 10)
        self.assertEqual(result["habitats"]["total_area_m2"], 200.0)
        self.assertEqual(result["pesticide_risk"]["overall_risk"], "elevated")
        self.assertEqual(result["hives"]["total"], 2)


if __name__ == "__main__":
    unittest.main()
