#!/usr/bin/env python3
"""
Tests for Nutrient Budget Tracking
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, PropertyMock
from datetime import date

from services.analytics.nutrient_budget import (
    create_budget,
    record_input,
    record_removal,
    get_nutrient_balance,
    get_input_summary,
    record_soil_test,
    get_recommendation,
    get_nutrient_dashboard,
    compute_removal,
    get_efficiency_ratio,
)


class TestCreateBudget(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_budget_id(self):
        result = create_budget(self.conn, "loc-001", "2026S1")
        self.assertIn("budget_id", result)
        self.assertIsNotNone(result["budget_id"])

    def test_records_season(self):
        result = create_budget(self.conn, "loc-001", "2026S1")
        self.assertEqual(result["season"], "2026S1")

    def test_records_crop_name(self):
        result = create_budget(
            self.conn, "loc-001", "2026S1", crop_name="maize",
        )
        self.assertEqual(result["crop_name"], "maize")

    def test_records_area(self):
        result = create_budget(
            self.conn, "loc-001", "2026S1", area_ha=2.5,
        )
        self.assertEqual(result["area_ha"], 2.5)

    def test_records_location(self):
        result = create_budget(self.conn, "loc-001", "2026S1")
        self.assertEqual(result["location_id"], "loc-001")

    def test_commits(self):
        create_budget(self.conn, "loc-001", "2026S1")
        self.conn.commit.assert_called_once()


class TestRecordInput(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_input_id(self):
        result = record_input(
            self.conn, "budget-001", date(2026, 1, 1), "fertilizer",
        )
        self.assertIn("input_id", result)
        self.assertIsNotNone(result["input_id"])

    def test_records_type(self):
        result = record_input(
            self.conn, "budget-001", date(2026, 1, 1), "fertilizer",
        )
        self.assertEqual(result["input_type"], "fertilizer")

    def test_records_npk(self):
        result = record_input(
            self.conn, "budget-001", date(2026, 1, 1), "fertilizer",
            n_kg=50.0, p_kg=10.0, k_kg=20.0,
        )
        self.assertEqual(result["nitrogen_kg"], 50.0)
        self.assertEqual(result["phosphorus_kg"], 10.0)
        self.assertEqual(result["potassium_kg"], 20.0)

    def test_records_product_name(self):
        result = record_input(
            self.conn, "budget-001", date(2026, 1, 1), "fertilizer",
            product_name="Urea 46-0-0",
        )
        self.assertEqual(result["product_name"], "Urea 46-0-0")

    def test_updates_budget(self):
        record_input(
            self.conn, "budget-001", date(2026, 1, 1), "fertilizer",
            n_kg=50.0, p_kg=10.0, k_kg=20.0,
        )
        self.assertEqual(self.mock_cursor.execute.call_count, 2)

    def test_commits(self):
        record_input(
            self.conn, "budget-001", date(2026, 1, 1), "fertilizer",
        )
        self.conn.commit.assert_called_once()


class TestRecordRemoval(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_removal_id(self):
        result = record_removal(
            self.conn, "budget-001", date(2026, 6, 1),
            "maize", 3.5, 86.8, 30.1, 63.7,
        )
        self.assertIn("removal_id", result)
        self.assertIsNotNone(result["removal_id"])

    def test_records_crop(self):
        result = record_removal(
            self.conn, "budget-001", date(2026, 6, 1),
            "maize", 3.5, 86.8, 30.1, 63.7,
        )
        self.assertEqual(result["crop_name"], "maize")

    def test_records_yield(self):
        result = record_removal(
            self.conn, "budget-001", date(2026, 6, 1),
            "maize", 3.5, 86.8, 30.1, 63.7,
        )
        self.assertEqual(result["yield_amount"], 3.5)

    def test_records_npk(self):
        result = record_removal(
            self.conn, "budget-001", date(2026, 6, 1),
            "maize", 3.5, 86.8, 30.1, 63.7,
        )
        self.assertEqual(result["nitrogen_kg"], 86.8)
        self.assertEqual(result["phosphorus_kg"], 30.1)
        self.assertEqual(result["potassium_kg"], 63.7)

    def test_updates_budget(self):
        record_removal(
            self.conn, "budget-001", date(2026, 6, 1),
            "maize", 3.5, 86.8, 30.1, 63.7,
        )
        self.assertEqual(self.mock_cursor.execute.call_count, 2)


class TestGetNutrientBalance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_description(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("budget_id",), ("plot_id",), ("season",), ("crop_name",), ("area_ha",),
            ("nitrogen_input_kg",), ("nitrogen_removal_kg",), ("nitrogen_surplus_kg",),
            ("phosphorus_input_kg",), ("phosphorus_removal_kg",), ("phosphorus_surplus_kg",),
            ("potassium_input_kg",), ("potassium_removal_kg",), ("potassium_surplus_kg",),
            ("nitrogen_balance_status",), ("phosphorus_balance_status",), ("potassium_balance_status",),
        ])

    def test_returns_location_id(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = []
        result = get_nutrient_balance(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_budgets(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("b1", "p1", "2026S1", "maize", 2.0,
             100.0, 80.0, 20.0,
             50.0, 45.0, 5.0,
             80.0, 70.0, 10.0,
             "surplus", "balanced", "surplus"),
        ]
        result = get_nutrient_balance(self.conn, "loc-001")
        self.assertEqual(len(result["budgets"]), 1)
        b = result["budgets"][0]
        self.assertEqual(b["nitrogen"]["surplus_kg"], 20.0)
        self.assertEqual(b["phosphorus"]["status"], "balanced")


class TestGetInputSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_description(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("input_type",), ("event_count",), ("total_nitrogen_kg",),
            ("total_phosphorus_kg",), ("total_potassium_kg",),
            ("total_cost",), ("avg_application_rate",), ("rate_unit",),
        ])

    def test_returns_budget_id(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = []
        result = get_input_summary(self.conn, "budget-001")
        self.assertEqual(result["budget_id"], "budget-001")

    def test_returns_summary(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("fertilizer", 5, 250.0, 50.0, 100.0, 150.0, 100.0, "kg/ha"),
        ]
        result = get_input_summary(self.conn, "budget-001")
        self.assertEqual(len(result["summary"]), 1)
        self.assertEqual(result["summary"][0]["input_type"], "fertilizer")
        self.assertEqual(result["summary"][0]["nitrogen_kg"], 250.0)


class TestRecordSoilTest(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_test_id(self):
        result = record_soil_test(self.conn, "loc-001")
        self.assertIn("test_id", result)
        self.assertIsNotNone(result["test_id"])

    def test_records_ph(self):
        result = record_soil_test(self.conn, "loc-001", soil_ph=6.5)
        self.assertEqual(result["soil_ph"], 6.5)

    def test_records_om(self):
        result = record_soil_test(
            self.conn, "loc-001", organic_matter_pct=3.2,
        )
        self.assertEqual(result["organic_matter_pct"], 3.2)

    def test_records_npk_ppm(self):
        result = record_soil_test(
            self.conn, "loc-001", n_ppm=45.0, p_ppm=22.0, k_ppm=180.0,
        )
        self.assertEqual(result["nitrogen_ppm"], 45.0)
        self.assertEqual(result["phosphorus_ppm"], 22.0)
        self.assertEqual(result["potassium_ppm"], 180.0)

    def test_records_recommendations(self):
        result = record_soil_test(
            self.conn, "loc-001",
            recommended_n_kg_ha=120.0,
            recommended_p_kg_ha=40.0,
            recommended_k_kg_ha=60.0,
        )
        self.assertEqual(result["recommended_n_kg_ha"], 120.0)

    def test_commits(self):
        record_soil_test(self.conn, "loc-001")
        self.conn.commit.assert_called_once()


class TestGetRecommendation(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_no_recommendation(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_recommendation(self.conn, "plot-001")
        self.assertIsNone(result["recommendation"])
        self.assertIn("No soil test", result["message"])

    def test_returns_recommendation(self):
        self.mock_cursor.fetchone.return_value = (
            "test-001", "loc-001", date(2026, 1, 1),
            None, 6.5, 3.2, 45.0, 22.0, 180.0, 25.0,
            120.0, 40.0, 60.0, "Normal",
        )
        result = get_recommendation(self.conn, "plot-001")
        self.assertEqual(result["test_id"], "test-001")
        self.assertEqual(result["recommended"]["nitrogen_kg_ha"], 120.0)
        self.assertEqual(result["recommended"]["phosphorus_kg_ha"], 40.0)
        self.assertEqual(result["recommended"]["potassium_kg_ha"], 60.0)


class TestGetNutrientDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("budget_id",), ("plot_id",), ("season",), ("crop_name",), ("area_ha",),
             ("nitrogen_input_kg",), ("nitrogen_removal_kg",), ("nitrogen_surplus_kg",),
             ("phosphorus_input_kg",), ("phosphorus_removal_kg",), ("phosphorus_surplus_kg",),
             ("potassium_input_kg",), ("potassium_removal_kg",), ("potassium_surplus_kg",)],
            [("input_type",), ("event_count",), ("total_n",), ("total_p",),
             ("total_k",), ("total_cost",)],
            [("plot_id",), ("test_date",), ("soil_ph",), ("organic_matter_pct",),
             ("nitrogen_ppm",), ("phosphorus_ppm",), ("potassium_ppm",)],
        ])

    def test_returns_location_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], [], []]
        result = get_nutrient_dashboard(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_balances(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("b1", "p1", "2026S1", "maize", 2.0,
              100.0, 80.0, 20.0,
              50.0, 45.0, 5.0,
              80.0, 70.0, 10.0)],
            [],
            [],
        ]
        result = get_nutrient_dashboard(self.conn, "loc-001")
        self.assertEqual(len(result["balances"]), 1)

    def test_returns_inputs(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [],
            [("fertilizer", 5, 250.0, 50.0, 100.0, 150.0)],
            [],
        ]
        result = get_nutrient_dashboard(self.conn, "loc-001")
        self.assertEqual(len(result["inputs_by_type"]), 1)

    def test_returns_soil_tests(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [],
            [],
            [("p1", date(2026, 1, 1), 6.5, 3.2, 45.0, 22.0, 180.0)],
        ]
        result = get_nutrient_dashboard(self.conn, "loc-001")
        self.assertEqual(len(result["recent_soil_tests"]), 1)


class TestComputeRemoval(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_removal(self):
        self.mock_cursor.fetchall.return_value = [
            ("nitrogen", 24.8, "grain", "IPCC"),
            ("phosphorus", 8.6, "grain", "IPCC"),
            ("potassium", 18.2, "grain", "IPCC"),
        ]
        result = compute_removal(self.conn, "maize", 3.5)
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["yield_tonnes"], 3.5)

    def test_computes_npk(self):
        self.mock_cursor.fetchall.return_value = [
            ("nitrogen", 24.8, "grain", "IPCC"),
            ("phosphorus", 8.6, "grain", "IPCC"),
            ("potassium", 18.2, "grain", "IPCC"),
        ]
        result = compute_removal(self.conn, "maize", 3.5)
        self.assertAlmostEqual(result["nitrogen_kg"], 86.8, places=2)
        self.assertAlmostEqual(result["phosphorus_kg"], 30.1, places=2)
        self.assertAlmostEqual(result["potassium_kg"], 63.7, places=2)

    def test_zero_yield(self):
        self.mock_cursor.fetchall.return_value = [
            ("nitrogen", 24.8, "grain", "IPCC"),
        ]
        result = compute_removal(self.conn, "maize", 0.0)
        self.assertEqual(result["nitrogen_kg"], 0.0)


class TestGetEfficiencyRatio(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_no_data(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_efficiency_ratio(self.conn, "loc-001", "2026S1")
        self.assertIsNone(result["efficiency"])

    def test_computes_ratios(self):
        self.mock_cursor.fetchall.return_value = [
            (100.0, 80.0, 50.0, 30.0, 60.0, 50.0),
        ]
        result = get_efficiency_ratio(self.conn, "loc-001", "2026S1")
        self.assertIsNotNone(result["efficiency"])
        self.assertEqual(result["efficiency"]["nitrogen"]["input_kg"], 100.0)
        self.assertEqual(result["efficiency"]["nitrogen"]["removal_kg"], 80.0)
        self.assertAlmostEqual(
            result["efficiency"]["nitrogen"]["ratio"], 0.8, places=4,
        )

    def test_zero_input_no_ratio(self):
        self.mock_cursor.fetchall.return_value = [
            (0.0, 10.0, 0.0, 5.0, 0.0, 3.0),
        ]
        result = get_efficiency_ratio(self.conn, "loc-001", "2026S1")
        self.assertIsNone(result["efficiency"]["nitrogen"]["ratio"])

    def test_multiple_budgets(self):
        self.mock_cursor.fetchall.return_value = [
            (100.0, 50.0, 30.0, 20.0, 40.0, 30.0),
            (100.0, 30.0, 30.0, 10.0, 40.0, 20.0),
        ]
        result = get_efficiency_ratio(self.conn, "loc-001", "2026S1")
        self.assertEqual(result["efficiency"]["nitrogen"]["input_kg"], 200.0)
        self.assertEqual(result["efficiency"]["nitrogen"]["removal_kg"], 80.0)


if __name__ == "__main__":
    unittest.main()
