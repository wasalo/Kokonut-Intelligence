#!/usr/bin/env python3
"""
Tests for Yield Monitoring
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta

from services.analytics.yield_monitoring import (
    record_yield_observation,
    get_yield_summary,
    compute_yield_trend,
    predict_yield,
    compare_benchmark,
    _format_record,
    _format_summary,
    _format_trend,
    _format_predict,
    _format_benchmark,
)


class TestYieldRecording(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("obs-001",)
        self.mock_cursor.description = [("id",)]

    def test_record_basic(self):
        result = record_yield_observation(
            self.conn, "loc-001", 2500.0, 1.5, "maize",
        )
        self.assertIn("observation_id", result)
        self.assertEqual(result["yield_kg_ha"], 2500.0)
        self.assertEqual(result["area_ha"], 1.5)
        self.assertEqual(result["total_yield_kg"], 3750.0)

    def test_record_with_date(self):
        result = record_yield_observation(
            self.conn, "loc-001", 2000.0, 1.0, "beans",
            harvest_date=date(2026, 1, 15),
        )
        self.assertEqual(result["harvest_date"], "2026-01-15")

    def test_record_with_metadata(self):
        result = record_yield_observation(
            self.conn, "loc-001", 2500.0, crop_name="maize",
            metadata={"field_zone": "A"},
        )
        self.assertIn("observation_id", result)


class TestYieldSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_empty_summary(self):
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (0, None, None, None, None)
        result = get_yield_summary(self.conn, "loc-001")
        self.assertEqual(result["total_observations"], 0)

    def test_summary_with_crops(self):
        self.mock_cursor.fetchall.side_effect = [
            [("maize", 5, 2500.0, 2000.0, 3000.0, 300.0, 12500.0)],
            [],
        ]
        self.mock_cursor.fetchone.return_value = (5, 12500.0, 2500.0, date(2025, 1, 1), date(2026, 1, 1))
        # Set description for the first query (crops)
        self.mock_cursor.description = [
            ("crop_name",), ("observations",), ("avg_yield",),
            ("min_yield",), ("max_yield",), ("stddev_yield",), ("total_production",),
        ]
        # The function calls cursor() once and reuses it, so we need to set
        # description for each query. We'll use a side_effect approach.
        # Actually, the function calls cursor() once and fetchall twice + fetchone once.
        # The description changes between queries. Let's mock more carefully.
        self.conn.cursor.return_value = self.mock_cursor
        result = get_yield_summary(self.conn, "loc-001")
        self.assertEqual(result["total_observations"], 5)
        self.assertEqual(len(result["crops"]), 1)


class TestYieldTrend(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_insufficient_data(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("day_num",), ("yield_amount",), ("harvest_date",), ("crop_name",)]
        result = compute_yield_trend(self.conn, "loc-001", "maize")
        self.assertEqual(result["trend"], "insufficient_data")

    def test_increasing_trend(self):
        base_date = date(2023, 1, 1)
        self.mock_cursor.fetchall.return_value = [
            (float(base_date.toordinal()), 1000.0, base_date, "maize"),
            (float((base_date + timedelta(days=365)).toordinal()), 1500.0, base_date + timedelta(days=365), "maize"),
            (float((base_date + timedelta(days=730)).toordinal()), 2000.0, base_date + timedelta(days=730), "maize"),
        ]
        self.mock_cursor.description = [("day_num",), ("yield_amount",), ("harvest_date",), ("crop_name",)]
        result = compute_yield_trend(self.conn, "loc-001", "maize")
        self.assertEqual(result["trend"], "increasing")
        self.assertGreater(result["slope_per_month"], 0)

    def test_decreasing_trend(self):
        base_date = date(2023, 1, 1)
        self.mock_cursor.fetchall.return_value = [
            (float(base_date.toordinal()), 2000.0, base_date, "maize"),
            (float((base_date + timedelta(days=365)).toordinal()), 1500.0, base_date + timedelta(days=365), "maize"),
            (float((base_date + timedelta(days=730)).toordinal()), 1000.0, base_date + timedelta(days=730), "maize"),
        ]
        self.mock_cursor.description = [("day_num",), ("yield_amount",), ("harvest_date",), ("crop_name",)]
        result = compute_yield_trend(self.conn, "loc-001", "maize")
        self.assertEqual(result["trend"], "decreasing")
        self.assertLess(result["slope_per_month"], 0)

    def test_stable_trend(self):
        base_date = date(2023, 1, 1)
        self.mock_cursor.fetchall.return_value = [
            (float(base_date.toordinal()), 1500.0, base_date, "maize"),
            (float((base_date + timedelta(days=365)).toordinal()), 1500.0, base_date + timedelta(days=365), "maize"),
            (float((base_date + timedelta(days=730)).toordinal()), 1500.0, base_date + timedelta(days=730), "maize"),
        ]
        self.mock_cursor.description = [("day_num",), ("yield_amount",), ("harvest_date",), ("crop_name",)]
        result = compute_yield_trend(self.conn, "loc-001", "maize")
        self.assertEqual(result["trend"], "stable")


class TestYieldPrediction(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_prediction_basic(self):
        self.mock_cursor.fetchone.side_effect = [
            (2000.0, 300.0, 5),  # historical avg, stddev, count
            (1000.0,),           # current GDD
            (25.0, 60.0),        # temperature, rainfall
        ]
        result = predict_yield(self.conn, "loc-001", "maize", 60)
        self.assertIn("predicted_yield_kg_ha", result)
        self.assertIn("confidence_low", result)
        self.assertIn("confidence_high", result)
        self.assertGreater(result["predicted_yield_kg_ha"], 0)

    def test_prediction_no_history(self):
        self.mock_cursor.fetchone.side_effect = [
            (None, None, 0),  # no historical data
            (None,),          # no GDD
            (None, None),     # no weather
        ]
        result = predict_yield(self.conn, "loc-001", "maize", 30)
        self.assertIn("predicted_yield_kg_ha", result)


class TestBenchmarkComparison(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_benchmark_comparison(self):
        self.mock_cursor.fetchall.side_effect = [
            [("historical_avg", 1800.0)],
        ]
        self.mock_cursor.fetchone.return_value = (2200.0,)
        result = compare_benchmark(self.conn, "loc-001", "maize")
        self.assertIn("benchmarks", result)
        self.assertIn("historical_avg", result["benchmarks"])
        self.assertEqual(result["benchmarks"]["historical_avg"]["status"], "above")

    def test_benchmark_below(self):
        self.mock_cursor.fetchall.side_effect = [
            [("historical_avg", 2500.0)],
        ]
        self.mock_cursor.fetchone.return_value = (2000.0,)
        result = compare_benchmark(self.conn, "loc-001", "maize")
        self.assertEqual(result["benchmarks"]["historical_avg"]["status"], "below")


class TestFormatting(unittest.TestCase):

    def test_format_record(self):
        result = _format_record({
            "crop_name": "maize", "yield_kg_ha": 2500.0,
            "area_ha": 1.5, "total_yield_kg": 3750.0,
            "harvest_date": "2026-01-15",
        })
        self.assertIn("maize", result)
        self.assertIn("2500", result)

    def test_format_summary_empty(self):
        result = _format_summary({"location_id": "loc-001", "total_observations": 0, "crops": []})
        self.assertIn("No yield data", result)

    def test_format_trend_insufficient(self):
        result = _format_trend({"trend": "insufficient_data", "data_points": 1})
        self.assertIn("Insufficient", result)

    def test_format_predict(self):
        result = _format_predict({
            "crop_name": "maize",
            "predicted_yield_kg_ha": 2500.0,
            "confidence_low": 2000.0,
            "confidence_high": 3000.0,
            "days_to_harvest": 60,
            "confidence": 0.7,
        })
        self.assertIn("2500", result)

    def test_format_benchmark_empty(self):
        result = _format_benchmark({"location_id": "loc-001", "crop_name": "maize", "benchmarks": {}})
        self.assertIn("No benchmarks", result)


if __name__ == "__main__":
    unittest.main()
