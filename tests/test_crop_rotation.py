#!/usr/bin/env python3
"""
Tests for Crop Rotation Planning
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, PropertyMock
from datetime import date

from services.analytics.crop_rotation import (
    create_plan,
    add_slot,
    get_plan,
    list_plans,
    record_impact,
    get_impact_summary,
    get_crop_family_usage,
    recommend_rotation,
    validate_plan,
    get_rotation_dashboard,
)


class TestCreatePlan(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_plan_id(self):
        result = create_plan(self.conn, "loc-001", "3-Year Plan")
        self.assertIn("plan_id", result)
        self.assertIsNotNone(result["plan_id"])

    def test_records_plan_name(self):
        result = create_plan(self.conn, "loc-001", "3-Year Plan")
        self.assertEqual(result["plan_name"], "3-Year Plan")

    def test_records_location(self):
        result = create_plan(self.conn, "loc-001", "3-Year Plan")
        self.assertEqual(result["location_id"], "loc-001")

    def test_records_duration(self):
        result = create_plan(
            self.conn, "loc-001", "3-Year Plan", duration_seasons=6,
        )
        self.assertEqual(result["duration_seasons"], 6)

    def test_default_status_draft(self):
        result = create_plan(self.conn, "loc-001", "3-Year Plan")
        self.assertEqual(result["status"], "draft")

    def test_commits(self):
        create_plan(self.conn, "loc-001", "3-Year Plan")
        self.conn.commit.assert_called_once()


class TestAddSlot(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = None  # no crop family match

    def test_returns_slot_id(self):
        result = add_slot(self.conn, "plan-001", 1, "maize")
        self.assertIn("slot_id", result)
        self.assertIsNotNone(result["slot_id"])

    def test_records_season_number(self):
        result = add_slot(self.conn, "plan-001", 2, "beans")
        self.assertEqual(result["season_number"], 2)

    def test_records_crop_name(self):
        result = add_slot(self.conn, "plan-001", 1, "maize")
        self.assertEqual(result["crop_name"], "maize")

    def test_records_purpose(self):
        result = add_slot(
            self.conn, "plan-001", 1, "maize", purpose="cash_crop",
        )
        self.assertEqual(result["purpose"], "cash_crop")

    def test_records_area(self):
        result = add_slot(
            self.conn, "plan-001", 1, "maize", expected_area_ha=2.5,
        )
        self.assertEqual(result["expected_area_ha"], 2.5)

    def test_commits(self):
        add_slot(self.conn, "plan-001", 1, "maize")
        self.conn.commit.assert_called_once()


class TestGetPlan(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_plan_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_plan(self.conn, "nonexistent")
        self.assertIn("error", result)

    def test_returns_plan_with_slots(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("id",), ("location_id",), ("plan_name",), ("plot_id",), ("zone_id",),
             ("duration_seasons",), ("start_season",), ("status",), ("notes",),
             ("metadata",), ("created_at",), ("updated_at",)],
            [("id",), ("season_number",), ("season_name",), ("crop_name",),
             ("family_name",), ("purpose",), ("expected_area_ha",),
             ("notes",), ("metadata",)],
        ])
        self.mock_cursor.fetchone.side_effect = [
            ("plan-001", "loc-001", "3-Year Plan", None, None,
             4, None, "draft", None, "{}", date(2026, 1, 1), date(2026, 1, 1)),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("slot-001", 1, "Season 1", "maize", "Poaceae", "cash_crop", 2.0, None, "{}"),
        ]
        result = get_plan(self.conn, "plan-001")
        self.assertEqual(result["id"], "plan-001")
        self.assertEqual(len(result["slots"]), 1)
        self.assertEqual(result["crop_sequence"], ["maize"])

    def test_filled_slots_count(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("id",), ("location_id",), ("plan_name",), ("plot_id",), ("zone_id",),
             ("duration_seasons",), ("start_season",), ("status",), ("notes",),
             ("metadata",), ("created_at",), ("updated_at",)],
            [("id",), ("season_number",), ("season_name",), ("crop_name",),
             ("family_name",), ("purpose",), ("expected_area_ha",),
             ("notes",), ("metadata",)],
        ])
        self.mock_cursor.fetchone.side_effect = [
            ("plan-001", "loc-001", "3-Year Plan", None, None,
             4, None, "draft", None, "{}", date(2026, 1, 1), date(2026, 1, 1)),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("s1", 1, "S1", "maize", "Poaceae", "cash_crop", 2.0, None, "{}"),
            ("s2", 2, "S2", "beans", "Fabaceae", "nitrogen_fixer", 1.5, None, "{}"),
        ]
        result = get_plan(self.conn, "plan-001")
        self.assertEqual(result["filled_slots"], 2)


class TestListPlans(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_empty_list(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("id",), ("plan_name",), ("plot_id",), ("zone_id",),
            ("duration_seasons",), ("status",), ("start_season",),
            ("slot_count",), ("created_at",),
        ])
        self.mock_cursor.fetchall.return_value = []
        result = list_plans(self.conn, "loc-001")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["plans"], [])

    def test_returns_plans(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("id",), ("plan_name",), ("plot_id",), ("zone_id",),
            ("duration_seasons",), ("status",), ("start_season",),
            ("slot_count",), ("created_at",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("plan-001", "3-Year Plan", None, None, 4, "draft", None, 3, date(2026, 1, 1)),
        ]
        result = list_plans(self.conn, "loc-001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["plans"][0]["plan_name"], "3-Year Plan")

    def test_returns_location_id(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("id",), ("plan_name",), ("plot_id",), ("zone_id",),
            ("duration_seasons",), ("status",), ("start_season",),
            ("slot_count",), ("created_at",),
        ])
        self.mock_cursor.fetchall.return_value = []
        result = list_plans(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")


class TestRecordImpact(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_impact_id(self):
        result = record_impact(
            self.conn, plan_id="plan-001", impact_type="soil_health",
        )
        self.assertIn("impact_id", result)
        self.assertIsNotNone(result["impact_id"])

    def test_records_type(self):
        result = record_impact(
            self.conn, plan_id="plan-001", impact_type="pest_pressure",
        )
        self.assertEqual(result["impact_type"], "pest_pressure")

    def test_records_direction(self):
        result = record_impact(
            self.conn, plan_id="plan-001",
            impact_type="soil_health", impact_direction="positive",
        )
        self.assertEqual(result["impact_direction"], "positive")

    def test_records_severity(self):
        result = record_impact(
            self.conn, plan_id="plan-001",
            impact_type="yield_effect", severity_pct=15.0,
        )
        self.assertEqual(result["severity_pct"], 15.0)

    def test_records_plan_id(self):
        result = record_impact(
            self.conn, plan_id="plan-001",
        )
        self.assertEqual(result["plan_id"], "plan-001")

    def test_commits(self):
        record_impact(self.conn, plan_id="plan-001")
        self.conn.commit.assert_called_once()


class TestGetImpactSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("impact_type",), ("impact_direction",), ("record_count",),
             ("avg_severity",), ("max_severity",), ("first_recorded",),
             ("last_recorded",), ("measurement_unit",)],
        ])

    def test_returns_plan_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0, 0, 0)
        result = get_impact_summary(self.conn, "plan-001")
        self.assertEqual(result["plan_id"], "plan-001")

    def test_returns_totals(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.return_value = [
            ("soil_health", "positive", 5, 12.0, 20.0,
             date(2026, 1, 1), date(2026, 6, 1), "%"),
        ]
        self.mock_cursor.fetchone.return_value = (5, 3, 2)
        result = get_impact_summary(self.conn, "plan-001")
        self.assertEqual(result["total_records"], 5)
        self.assertEqual(result["positive_count"], 3)
        self.assertEqual(result["negative_count"], 2)

    def test_impacts_by_type(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.return_value = [
            ("soil_health", "positive", 3, 10.0, 15.0,
             date(2026, 1, 1), date(2026, 6, 1), "%"),
            ("pest_pressure", "negative", 2, 8.0, 12.0,
             date(2026, 2, 1), date(2026, 5, 1), "%"),
        ]
        self.mock_cursor.fetchone.return_value = (5, 3, 2)
        result = get_impact_summary(self.conn, "plan-001")
        self.assertEqual(len(result["impacts_by_type"]), 2)


class TestGetCropFamilyUsage(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("family_id",), ("family_name",), ("example_crops",),
             ("plan_name",), ("plan_id",), ("slot_count",),
             ("crops_used",), ("seasons_used",)],
            [("family_name",), ("total_slots",), ("plan_count",)],
        ])

    def test_returns_location_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], []]
        result = get_crop_family_usage(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_family_usage(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("fam-001", "Poaceae", "maize", "3-Year Plan", "plan-001", 2, ["maize", "sorghum"], [1, 3])],
            [("Poaceae", 3, 1)],
        ]
        result = get_crop_family_usage(self.conn, "loc-001")
        self.assertEqual(len(result["family_usage"]), 1)
        self.assertEqual(result["families_used"], 1)


class TestRecommendRotation(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("crop_name",), ("family_name",), ("plot_id",), ("times_used",)],
            [("id",), ("family_name",), ("example_crops",), ("notes",)],
            [("avg_soil_severity",)],
            [("impact_type",), ("impact_direction",), ("cnt",)],
        ])

    def test_returns_recommendations(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [],  # history
            [("fam-001", "Poaceae", '["maize"]', None)],  # families
            [],  # impacts
        ]
        self.mock_cursor.fetchone.return_value = (None,)
        result = recommend_rotation(self.conn, "loc-001")
        self.assertIn("recommendations", result)
        self.assertGreater(len(result["recommendations"]), 0)

    def test_overused_families(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("maize", "Poaceae", None, 3)],  # history - used 3 times
            [("fam-001", "Poaceae", '["maize"]', None)],
            [],
        ]
        self.mock_cursor.fetchone.return_value = (None,)
        result = recommend_rotation(self.conn, "loc-001")
        self.assertIn("Poaceae", result["overused_families"])

    def test_unused_families(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("maize", "Poaceae", None, 1)],  # minimal history
            [("fam-001", "Poaceae", '["maize"]', None),
             ("fam-002", "Fabaceae", '["beans"]', None),
             ("fam-003", "Euphorbiaceae", '["cassava"]', None)],
            [],
        ]
        self.mock_cursor.fetchone.return_value = (None,)
        result = recommend_rotation(self.conn, "loc-001")
        self.assertIn("recommendations", result)
        self.assertGreater(len(result["recommendations"]), 0)

    def test_confidence_scores(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [],
            [("fam-001", "Poaceae", '["maize"]', None)],
            [],
        ]
        self.mock_cursor.fetchone.return_value = (None,)
        result = recommend_rotation(self.conn, "loc-001")
        for rec in result["recommendations"]:
            self.assertGreaterEqual(rec["confidence_score"], 0.0)
            self.assertLessEqual(rec["confidence_score"], 1.0)


class TestValidatePlan(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_plan_not_found(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("season_number",), ("crop_name",), ("family_name",), ("purpose",)],
        ])
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = None
        result = validate_plan(self.conn, "nonexistent")
        self.assertIn("error", result)

    def test_valid_plan(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("season_number",), ("crop_name",), ("family_name",), ("purpose",)],
        ])
        self.mock_cursor.fetchall.return_value = [
            (1, "maize", "Poaceae", "cash_crop"),
            (2, "beans", "Fabaceae", "nitrogen_fixer"),
            (3, "cassava", "Euphorbiaceae", "cash_crop"),
            (4, "maize", "Poaceae", "cash_crop"),
        ]
        self.mock_cursor.fetchone.return_value = (4,)
        result = validate_plan(self.conn, "plan-001")
        self.assertTrue(result["valid"])
        self.assertEqual(result["total_checks"], 5)

    def test_consecutive_same_family(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("season_number",), ("crop_name",), ("family_name",), ("purpose",)],
        ])
        self.mock_cursor.fetchall.return_value = [
            (1, "maize", "Poaceae", "cash_crop"),
            (2, "sorghum", "Poaceae", "cash_crop"),
        ]
        self.mock_cursor.fetchone.return_value = (4,)
        result = validate_plan(self.conn, "plan-001")
        self.assertFalse(result["valid"])
        checks = [i["check"] for i in result["issues"]]
        self.assertIn("no_same_family_consecutive", checks)

    def test_no_cover_crop_warning(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("season_number",), ("crop_name",), ("family_name",), ("purpose",)],
        ])
        self.mock_cursor.fetchall.return_value = [
            (1, "maize", "Poaceae", "cash_crop"),
            (2, "beans", "Fabaceae", "cash_crop"),
        ]
        self.mock_cursor.fetchone.return_value = (4,)
        result = validate_plan(self.conn, "plan-001")
        checks = [w["check"] for w in result["warnings"]]
        self.assertIn("cover_crop_inclusion", checks)

    def test_score_computed(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("season_number",), ("crop_name",), ("family_name",), ("purpose",)],
        ])
        self.mock_cursor.fetchall.return_value = [
            (1, "maize", "Poaceae", "cash_crop"),
        ]
        self.mock_cursor.fetchone.return_value = (4,)
        result = validate_plan(self.conn, "plan-001")
        self.assertIn("score_pct", result)
        self.assertGreaterEqual(result["score_pct"], 0)
        self.assertLessEqual(result["score_pct"], 100)


class TestGetRotationDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("id",), ("plan_name",), ("status",), ("duration_seasons",),
             ("slot_count",), ("created_at",)],
            [("impact_type",), ("impact_direction",), ("cnt",), ("avg_severity",)],
            [("family_name",), ("slot_count",)],
            [("impact_type",), ("impact_direction",), ("severity_pct",),
             ("record_date",), ("crop_name",)],
        ])

    def test_returns_location_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], [], [], []]
        result = get_rotation_dashboard(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_summary(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("p1", "3-Year Plan", "active", 4, 4, date(2026, 1, 1))],
            [],
            [("Poaceae", 3)],
            [],
        ]
        result = get_rotation_dashboard(self.conn, "loc-001")
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["total_plans"], 1)
        self.assertEqual(result["summary"]["active_plans"], 1)

    def test_returns_all_sections(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], [], [], []]
        result = get_rotation_dashboard(self.conn, "loc-001")
        self.assertIn("plans", result)
        self.assertIn("impacts_by_type", result)
        self.assertIn("family_diversity", result)
        self.assertIn("recent_impacts", result)


if __name__ == "__main__":
    unittest.main()
