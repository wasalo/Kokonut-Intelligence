#!/usr/bin/env python3
"""
Tests for Prescription Map Generation (VRT)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone

from services.analytics.prescription import (
    classify_rates_natural_breaks,
    classify_rates_equal_interval,
    compute_application_rate,
    generate_prescription_map,
    list_prescriptions,
    approve_prescription,
    get_material_estimate,
)


class TestRateClassification(unittest.TestCase):

    def test_natural_breaks_basic(self):
        values = [1.0, 2.0, 3.0, 10.0, 11.0, 12.0]
        result = classify_rates_natural_breaks(values, 3)
        self.assertEqual(len(result), 3)
        self.assertTrue(all("class_index" in r and "min" in r and "max" in r for r in result))

    def test_natural_breaks_uniform(self):
        values = [5.0, 5.0, 5.0, 5.0]
        result = classify_rates_natural_breaks(values, 3)
        self.assertGreater(len(result), 0)

    def test_natural_breaks_empty(self):
        result = classify_rates_natural_breaks([], 3)
        self.assertEqual(result, [])

    def test_natural_breaks_single_value(self):
        result = classify_rates_natural_breaks([10.0], 3)
        self.assertEqual(len(result), 1)

    def test_natural_breaks_sorted_output(self):
        result = classify_rates_natural_breaks([1, 5, 3, 9, 7], 3)
        for i in range(len(result) - 1):
            self.assertLessEqual(result[i]["max"], result[i + 1]["min"])

    def test_equal_interval(self):
        # Many values to get all 4 classes
        values = list(range(0, 101))  # 0..100
        result = classify_rates_equal_interval(values, 4)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["min"], 0)
        self.assertEqual(result[-1]["max"], 100)

    def test_equal_interval_single_value(self):
        result = classify_rates_equal_interval([5.0, 5.0], 3)
        self.assertGreater(len(result), 0)

    def test_equal_interval_two_values(self):
        result = classify_rates_equal_interval([0, 100], 4)
        # With only 2 values, at most 2 classes will have data
        self.assertLessEqual(len(result), 2)


class TestApplicationRates(unittest.TestCase):

    def test_fertilizer_rate_maize(self):
        result = compute_application_rate(25.0, "maize", "fertilizer", "mid")
        self.assertIn("rate", result)
        self.assertIn("unit", result)
        self.assertIn("level", result)

    def test_fertilizer_rate_development(self):
        result = compute_application_rate(25.0, "maize", "fertilizer", "development")
        self.assertIn("rate", result)
        self.assertIn("unit", result)

    def test_irrigation_rate(self):
        result = compute_application_rate(30.0, "maize", "irrigation", "flowering")
        self.assertIn("rate", result)
        self.assertIsInstance(result["rate"], (int, float))
        self.assertGreater(result["rate"], 0)

    def test_seed_rate(self):
        result = compute_application_rate(1.0, "maize", "seed", "planting")
        self.assertIn("rate", result)
        self.assertGreater(result["rate"], 0)

    def test_pesticide_rate(self):
        result = compute_application_rate(0.7, "maize", "pesticide", "vegetative")
        self.assertIn("rate", result)
        self.assertGreaterEqual(result["rate"], 0)

    def test_rate_different_levels(self):
        low = compute_application_rate(80.0, "maize", "irrigation", "mid")
        high = compute_application_rate(10.0, "maize", "irrigation", "mid")
        # Higher soil moisture → less irrigation needed
        self.assertGreaterEqual(low["rate"], high["rate"])

    def test_rate_returns_level(self):
        result = compute_application_rate(50.0, "maize", "fertilizer", "mid")
        self.assertIn("level", result)
        self.assertIn(result["level"], ["low", "medium", "high"])

    def test_unknown_crop(self):
        result = compute_application_rate(50.0, "unknown_crop", "fertilizer", "mid")
        self.assertIn("rate", result)

    def test_rate_with_soil_classes(self):
        classes = [
            {"class_index": 0, "min": 0, "max": 30, "rate": 200},
            {"class_index": 1, "min": 31, "max": 60, "rate": 150},
            {"class_index": 2, "min": 61, "max": 100, "rate": 100},
        ]
        result = compute_application_rate(25.0, "maize", "fertilizer", "mid", soil_classes=classes)
        self.assertEqual(result["level"], "high")

    def test_rate_confidence_with_classes(self):
        result = compute_application_rate(50.0, "maize", "fertilizer", "mid", soil_classes=[{"class_index": 1, "min": 30, "max": 70, "rate": 100}])
        self.assertEqual(result["confidence"], 0.8)

    def test_rate_confidence_without_classes(self):
        result = compute_application_rate(50.0, "maize", "fertilizer", "mid")
        self.assertEqual(result["confidence"], 0.5)


class TestPrescriptionMap(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_generate_creates_map(self):
        self.mock_cursor.fetchone.return_value = ("map-001",)
        self.mock_cursor.description = [("id",)]
        with patch("services.analytics.prescription._get_basis_values") as mock_get:
            mock_get.return_value = [
                {"value": 25.0, "latitude": 1.0, "longitude": 1.0, "zone": "A"},
                {"value": 35.0, "latitude": 1.1, "longitude": 1.1, "zone": "B"},
            ]
            with patch("services.analytics.prescription._get_material_cost") as mock_cost:
                mock_cost.return_value = None
                result = generate_prescription_map(self.conn, "loc-001", "plot-001", "fertilizer")
                self.assertIn("prescription_id", result)

    def test_generate_no_data(self):
        with patch("services.analytics.prescription._get_basis_values") as mock_get:
            mock_get.return_value = []
            result = generate_prescription_map(self.conn, "loc-001", "plot-001", "fertilizer")
            self.assertIn("error", result)

    def test_get_material_estimate(self):
        self.mock_cursor.fetchone.return_value = (
            "fertilizer", "kg", 500.0, 10.0, 50.0, 2.5, "USD",
        )
        self.mock_cursor.description = [
            ("input_type",), ("unit",), ("total_volume",), ("total_area_ha",),
            ("avg_rate",), ("cost_per_unit",), ("cost_unit",),
        ]
        result = get_material_estimate(self.conn, "map-001")
        self.assertIn("prescription_id", result)
        self.assertIn("total_cost_usd", result)
        self.assertEqual(result["total_cost_usd"], 1250.0)

    def test_get_material_estimate_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_material_estimate(self.conn, "nonexistent")
        self.assertIn("error", result)

    def test_approve_prescription(self):
        self.mock_cursor.fetchone.return_value = ("map-001", "fertilizer", 500.0)
        self.mock_cursor.description = [("id",), ("input_type",), ("total_volume",)]
        result = approve_prescription(self.conn, "map-001", "admin")
        self.assertEqual(result["status"], "approved")

    def test_approve_non_pending_fails(self):
        self.mock_cursor.fetchone.return_value = None
        result = approve_prescription(self.conn, "map-001", "admin")
        self.assertIn("error", result)

    def test_list_prescriptions(self):
        self.mock_cursor.fetchall.return_value = []
        result = list_prescriptions(self.conn, "loc-001")
        self.assertEqual(result, [])


class TestCLIHelp(unittest.TestCase):

    def test_help(self):
        from services.analytics.prescription import main
        with patch("sys.argv", ["prescription", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertIn(ctx.exception.code, (0, 2))


if __name__ == "__main__":
    unittest.main()
