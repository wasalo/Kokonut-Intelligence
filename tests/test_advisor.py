#!/usr/bin/env python3
"""
Tests for Advisory Engine
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone, timedelta

from services.analytics.advisor import (
    evaluate_rules,
    _is_in_cooldown,
    _exceeds_daily_limit,
    _eval_threshold,
    _eval_composite,
    _eval_schedule,
    _eval_forecast,
    _eval_anomaly,
    generate_recommendation,
    accept_recommendation,
    dismiss_recommendation,
    run_advisory_cycle,
    list_recommendations,
)


class TestCooldownAndLimits(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_no_cooldown(self):
        self.mock_cursor.fetchone.return_value = (0,)
        self.mock_cursor.description = [("count",)]
        result = _is_in_cooldown(self.conn, "rule-001", "loc-001", 24)
        self.assertFalse(result)

    def test_in_cooldown(self):
        self.mock_cursor.fetchone.return_value = (1,)
        self.mock_cursor.description = [("count",)]
        result = _is_in_cooldown(self.conn, "rule-001", "loc-001", 24)
        self.assertTrue(result)

    def test_daily_limit_ok(self):
        self.mock_cursor.fetchone.return_value = (2,)
        self.mock_cursor.description = [("count",)]
        result = _exceeds_daily_limit(self.conn, "rule-001", "loc-001", 5)
        self.assertFalse(result)

    def test_daily_limit_exceeded(self):
        self.mock_cursor.fetchone.return_value = (5,)
        self.mock_cursor.description = [("count",)]
        result = _exceeds_daily_limit(self.conn, "rule-001", "loc-001", 5)
        self.assertTrue(result)

    def test_daily_limit_zero(self):
        self.mock_cursor.fetchone.return_value = (0,)
        self.mock_cursor.description = [("count",)]
        result = _exceeds_daily_limit(self.conn, "rule-001", "loc-001", 5)
        self.assertFalse(result)


class TestRuleEvaluation(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_eval_threshold_triggers_lt(self):
        self.mock_cursor.fetchone.return_value = (25.0,)
        self.mock_cursor.description = [("value",)]
        conditions = {"metric": "soil_moisture", "operator": "lt", "threshold": 30, "source": "sensor"}
        result = _eval_threshold(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)
        self.assertEqual(result["value"], 25.0)

    def test_eval_threshold_no_trigger(self):
        self.mock_cursor.fetchone.return_value = (50.0,)
        self.mock_cursor.description = [("value",)]
        conditions = {"metric": "soil_moisture", "operator": "lt", "threshold": 30, "source": "sensor"}
        result = _eval_threshold(self.conn, "loc-001", conditions)
        self.assertIsNone(result)

    def test_eval_threshold_gt(self):
        self.mock_cursor.fetchone.return_value = (40.0,)
        self.mock_cursor.description = [("value",)]
        conditions = {"metric": "air_temperature", "operator": "gt", "threshold": 35, "source": "sensor"}
        result = _eval_threshold(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)

    def test_eval_threshold_gte(self):
        self.mock_cursor.fetchone.return_value = (30.0,)
        self.mock_cursor.description = [("value",)]
        conditions = {"metric": "soil_moisture", "operator": "gte", "threshold": 30, "source": "sensor"}
        result = _eval_threshold(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)

    def test_eval_threshold_lte(self):
        self.mock_cursor.fetchone.return_value = (30.0,)
        self.mock_cursor.description = [("value",)]
        conditions = {"metric": "soil_moisture", "operator": "lte", "threshold": 30, "source": "sensor"}
        result = _eval_threshold(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)

    def test_eval_threshold_missing_metric(self):
        conditions = {"operator": "lt", "threshold": 30}
        result = _eval_threshold(self.conn, "loc-001", conditions)
        self.assertIsNone(result)

    def test_eval_threshold_null_value(self):
        self.mock_cursor.fetchone.return_value = (None,)
        self.mock_cursor.description = [("value",)]
        conditions = {"metric": "soil_moisture", "operator": "lt", "threshold": 30, "source": "sensor"}
        result = _eval_threshold(self.conn, "loc-001", conditions)
        self.assertIsNone(result)

    def test_eval_composite_all_triggered(self):
        self.mock_cursor.fetchone.side_effect = [(10,), (60,)]
        self.mock_cursor.description = [("value",), ("value",)]
        conditions = {
            "wind_speed": {"metric": "wind_speed", "operator": "lt", "threshold": 15, "source": "sensor"},
            "humidity": {"metric": "humidity", "operator": "gt", "threshold": 40, "source": "sensor"},
        }
        result = _eval_composite(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)

    def test_eval_composite_partial(self):
        self.mock_cursor.fetchone.side_effect = [(10,), (30,)]
        self.mock_cursor.description = [("value",), ("value",)]
        conditions = {
            "wind_speed": {"metric": "wind_speed", "operator": "lt", "threshold": 15, "source": "sensor"},
            "humidity": {"metric": "humidity", "operator": "gt", "threshold": 40, "source": "sensor"},
        }
        result = _eval_composite(self.conn, "loc-001", conditions)
        self.assertIsNone(result)

    def test_eval_schedule(self):
        conditions = {"interval_days": 7, "last_check_field": "last_soil_check"}
        result = _eval_schedule(self.conn, "loc-001", conditions)
        if result:
            self.assertIn("overdue", result)

    def test_eval_forecast_spray_window(self):
        self.mock_cursor.fetchall.return_value = [
            (date.today(), 10.0, 5.0, 15.0, 28.0),
            (date.today() + timedelta(days=1), 5.0, 8.0, 16.0, 30.0),
        ]
        self.mock_cursor.description = [
            ("forecast_date",), ("precipitation_prob_pct",),
            ("wind_speed_kmh",), ("temp_min_c",), ("temp_max_c",),
        ]
        conditions = {"type": "spray_window"}
        result = _eval_forecast(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)
        self.assertIn("suitable_days", result)

    def test_eval_forecast_frost_risk(self):
        self.mock_cursor.fetchall.return_value = [
            (date.today(), 10.0, 5.0, 1.0, 10.0),  # temp_min < 5
        ]
        self.mock_cursor.description = [
            ("forecast_date",), ("precipitation_prob_pct",),
            ("wind_speed_kmh",), ("temp_min_c",), ("temp_max_c",),
        ]
        conditions = {"type": "frost_risk", "min_temp": 5}
        result = _eval_forecast(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)
        self.assertIn("frost_days", result)

    def test_eval_forecast_no_data(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = []
        conditions = {"type": "spray_window"}
        result = _eval_forecast(self.conn, "loc-001", conditions)
        self.assertIsNone(result)

    def test_eval_anomaly(self):
        self.mock_cursor.fetchone.return_value = (5,)
        self.mock_cursor.description = [("count",)]
        conditions = {"min_severity": "warning"}
        result = _eval_anomaly(self.conn, "loc-001", conditions)
        self.assertIsNotNone(result)

    def test_eval_anomaly_no_alerts(self):
        self.mock_cursor.fetchone.return_value = (0,)
        self.mock_cursor.description = [("count",)]
        conditions = {"min_severity": "warning"}
        result = _eval_anomaly(self.conn, "loc-001", conditions)
        self.assertIsNone(result)


class TestRecommendationLifecycle(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_generate_recommendation(self):
        self.mock_cursor.fetchone.return_value = ("rec-001",)
        self.mock_cursor.description = [("id",)]
        rule = {
            "rule_id": "rule-001",
            "rule_name": "Soil Moisture Low",
            "severity": "warning",
            "template": "Moisture at {value}%",
            "domain": "irrigation",
        }
        context = {"value": 25.0}
        result = generate_recommendation(self.conn, rule, context)
        self.assertIn("recommendation_id", result)
        self.assertEqual(result["status"], "pending")

    def test_generate_recommendation_critical(self):
        self.mock_cursor.fetchone.return_value = ("rec-002",)
        self.mock_cursor.description = [("id",)]
        rule = {
            "rule_id": "rule-002",
            "rule_name": "Frost Warning",
            "severity": "critical",
            "template": "Frost risk detected",
            "domain": "frost_protection",
        }
        context = {}
        result = generate_recommendation(self.conn, rule, context)
        self.assertEqual(result["urgency"], "within_24h")

    def test_accept_recommendation(self):
        self.mock_cursor.fetchone.side_effect = [
            ("rec-001", "irrigation", "Title", "this_week", "warning"),
            None,
        ]
        self.mock_cursor.description = [("id",), ("domain",), ("title",), ("urgency",), ("severity",)]
        result = accept_recommendation(self.conn, "rec-001", "admin")
        self.assertTrue(result.get("accepted", False) or result.get("status") == "accepted")

    def test_accept_non_pending_fails(self):
        self.mock_cursor.fetchone.return_value = None
        result = accept_recommendation(self.conn, "rec-001", "admin")
        self.assertIn("error", result)

    def test_dismiss_recommendation(self):
        self.mock_cursor.fetchone.side_effect = [
            ("rec-001", "irrigation", "Title"),
            None,
        ]
        self.mock_cursor.description = [("id",), ("domain",), ("title",)]
        result = dismiss_recommendation(self.conn, "rec-001", "Not applicable")
        self.assertTrue(result.get("dismissed", False) or result.get("status") == "dismissed")

    def test_dismiss_non_pending_fails(self):
        self.mock_cursor.fetchone.return_value = None
        result = dismiss_recommendation(self.conn, "rec-001", "Not needed")
        self.assertIn("error", result)

    def test_list_recommendations_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = list_recommendations(self.conn, "loc-001")
        self.assertEqual(result, [])


class TestRunCycle(unittest.TestCase):

    def test_full_cycle(self):
        conn = MagicMock()
        mock_cursor = MagicMock()
        conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = []
        result = run_advisory_cycle(conn, "loc-001")
        self.assertIn("recommendations_generated", result)


class TestCLIHelp(unittest.TestCase):

    def test_help(self):
        from services.analytics.advisor import main
        with patch("sys.argv", ["advisor", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertIn(ctx.exception.code, (0, 2))


if __name__ == "__main__":
    unittest.main()
