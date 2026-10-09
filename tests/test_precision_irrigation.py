#!/usr/bin/env python3
"""
Tests for Precision Irrigation Automation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import unittest.mock
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone

from services.analytics.precision_irrigation import (
    create_zone,
    set_moisture_target,
    generate_schedule,
    record_irrigation_event,
    create_automation_rule,
    evaluate_automation_rules,
    get_zone_status,
    get_irrigation_status,
    get_water_efficiency,
    compute_water_balance,
    optimize_schedule,
    get_efficiency_report,
)


class TestCreateZone(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("zone-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_zone_returns_zone_id(self):
        result = create_zone(self.conn, "loc-001", "Zone A")
        self.assertIn("zone_id", result)
        self.assertEqual(result["name"], "Zone A")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["status"], "active")

    def test_create_zone_with_area(self):
        result = create_zone(self.conn, "loc-001", "Zone A", area_ha=2.5)
        self.assertEqual(result["area_ha"], 2.5)
        self.assertEqual(result["area_m2"], 25000.0)

    def test_create_zone_calls_insert(self):
        create_zone(self.conn, "loc-001", "Zone A")
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestSetMoistureTarget(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("target-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_set_target_returns_target_id(self):
        result = set_moisture_target(
            self.conn, "zone-001", "vegetative",
            target_min=50.0, target_max=65.0,
            trigger_pct=40.0, refill_pct=65.0,
        )
        self.assertIn("target_id", result)
        self.assertEqual(result["crop_stage"], "vegetative")
        self.assertEqual(result["target_min_pct"], 50.0)
        self.assertEqual(result["target_max_pct"], 65.0)

    def test_set_target_calls_insert(self):
        set_moisture_target(
            self.conn, "zone-001", "flowering",
            target_min=45.0, target_max=60.0,
            trigger_pct=35.0, refill_pct=60.0,
        )
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestGenerateSchedule(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            (5000.0, 30.0),  # zone area_m2, depth_cm
            ("sched-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]

    def test_generate_schedule_returns_schedule(self):
        result = generate_schedule(
            self.conn, "zone-001", etc_mm=4.5, rainfall_forecast_mm=2.0,
            current_moisture_pct=42.0,
        )
        self.assertIn("schedule_id", result)
        self.assertEqual(result["etc_mm"], 4.5)
        self.assertEqual(result["rainfall_forecast_mm"], 2.0)
        self.assertEqual(result["status"], "pending")

    def test_generate_schedule_computes_net_need(self):
        result = generate_schedule(
            self.conn, "zone-001", etc_mm=5.0, rainfall_forecast_mm=3.0,
        )
        self.assertEqual(result["net_need_mm"], 2.0)
        self.assertGreater(result["planned_volume_l"], 0)

    def test_generate_schedule_zero_rainfall(self):
        result = generate_schedule(
            self.conn, "zone-001", etc_mm=4.0, rainfall_forecast_mm=0.0,
        )
        self.assertEqual(result["net_need_mm"], 4.0)


class TestRecordIrrigationEvent(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("event-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_record_event_returns_event_id(self):
        result = record_irrigation_event(
            self.conn, "zone-001", 500.0, 60.0, "drip",
            moisture_before=38.0, moisture_after=62.0,
        )
        self.assertIn("event_id", result)
        self.assertEqual(result["volume_liters"], 500.0)
        self.assertEqual(result["method"], "drip")
        self.assertEqual(result["moisture_before_pct"], 38.0)
        self.assertEqual(result["moisture_after_pct"], 62.0)

    def test_record_event_computes_flow_rate(self):
        result = record_irrigation_event(
            self.conn, "zone-001", 600.0, 120.0, "sprinkler",
            moisture_before=40.0, moisture_after=55.0,
        )
        self.assertEqual(result["flow_rate_lpm"], 5.0)

    def test_record_event_with_schedule_updates_schedule(self):
        record_irrigation_event(
            self.conn, "zone-001", 500.0, 60.0, "drip",
            moisture_before=38.0, moisture_after=62.0,
            schedule_id="sched-001",
        )
        self.assertEqual(self.mock_cursor.execute.call_count, 2)


class TestCreateAutomationRule(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("rule-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_rule_returns_rule_id(self):
        result = create_automation_rule(
            self.conn, "loc-001", "Low Moisture Alert",
            "soil_moisture", "lt", 40.0,
        )
        self.assertIn("rule_id", result)
        self.assertEqual(result["name"], "Low Moisture Alert")
        self.assertEqual(result["sensor_metric"], "soil_moisture")
        self.assertEqual(result["operator"], "lt")
        self.assertEqual(result["threshold_low"], 40.0)
        self.assertEqual(result["status"], "active")

    def test_create_rule_with_zone(self):
        result = create_automation_rule(
            self.conn, "loc-001", "Rule A",
            "temperature", "gt", 35.0,
            zone_id="zone-001",
        )
        self.assertEqual(result["zone_id"], "zone-001")


class TestEvaluateAutomationRules(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.rule_cols = [
            "id", "name", "sensor_metric", "operator",
            "threshold_low", "threshold_high", "unit", "action",
            "action_params", "cooldown_min", "max_per_day",
            "time_window_start", "time_window_end", "requires_approval",
            "priority",
        ]
        self.rule_description = [(c,) for c in self.rule_cols]

    def test_evaluate_no_rules(self):
        self.mock_cursor.description = self.rule_description
        self.mock_cursor.fetchall.return_value = []
        result = evaluate_automation_rules(self.conn, "zone-001", {"soil_moisture": 35})
        self.assertEqual(result["rules_evaluated"], 0)
        self.assertEqual(result["rules_triggered"], 0)

    def test_evaluate_triggers_rule(self):
        self.mock_cursor.description = self.rule_description
        rule = ("rule-1", "Low Moisture", "soil_moisture", "lt", 40.0, None, "%", "irrigate", {}, 60, 5, None, None, True, 50)
        self.mock_cursor.fetchall.return_value = [rule]
        self.mock_cursor.fetchone.return_value = (0,)  # cooldown count
        result = evaluate_automation_rules(self.conn, "zone-001", {"soil_moisture": 35})
        self.assertEqual(result["rules_evaluated"], 1)
        self.assertEqual(result["rules_triggered"], 1)
        self.assertEqual(result["triggered"][0]["action"], "irrigate")

    def test_evaluate_condition_not_met(self):
        self.mock_cursor.description = self.rule_description
        rule = ("rule-1", "Low Moisture", "soil_moisture", "lt", 40.0, None, "%", "irrigate", {}, 60, 5, None, None, True, 50)
        self.mock_cursor.fetchall.return_value = [rule]
        result = evaluate_automation_rules(self.conn, "zone-001", {"soil_moisture": 55})
        self.assertEqual(result["rules_triggered"], 0)


class TestGetZoneStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_zone_status_returns_data(self):
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("name",), ("zone_code",), ("soil_type",),
            ("area_m2",), ("depth_cm",), ("status",),
            ("target_min_pct",), ("target_max_pct",),
            ("irrigation_trigger_pct",), ("refill_to_pct",), ("growth_stage",),
            ("current_moisture_pct",), ("last_moisture_reading",),
            ("next_irrigation_start",), ("next_irrigation_volume_l",),
            ("next_irrigation_status",),
            ("last_irrigation_at",), ("last_irrigation_volume_l",),
        ]
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchone.return_value = (
            "zone-001", "loc-001", "Zone A", "ZA", "loam",
            5000.0, 30.0, "active",
            50.0, 65.0, 40.0, 65.0, "vegetative",
            45.0, now, None, None, None, None, None,
        )
        result = get_zone_status(self.conn, "zone-001")
        self.assertEqual(result["zone_id"], "zone-001")
        self.assertEqual(result["current_moisture_pct"], 45.0)
        self.assertEqual(result["moisture_status"], "below_target")

    def test_zone_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_zone_status(self.conn, "zone-999")
        self.assertEqual(result["error"], "zone_not_found")


class TestGetIrrigationStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_irrigation_status_returns_zones(self):
        self.mock_cursor.fetchall.return_value = [("zone-001",), ("zone-002",)]
        with patch("services.analytics.precision_irrigation.get_zone_status") as mock_status:
            mock_status.return_value = {"zone_id": "zone-001", "name": "Zone A"}
            result = get_irrigation_status(self.conn, "loc-001")
            self.assertEqual(result["location_id"], "loc-001")
            self.assertEqual(result["zone_count"], 2)


class TestGetWaterEfficiency(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_water_efficiency_returns_metrics(self):
        zone_cols = [
            ("zone_id",), ("zone_name",), ("event_count",), ("total_volume_l",),
            ("avg_volume_l",), ("avg_efficiency_pct",), ("avg_uniformity",),
            ("avg_water_productivity",), ("total_yield_kg",), ("total_effective_l",),
        ]
        overall_cols = [
            ("total_events",), ("total_volume_l",), ("avg_efficiency_pct",),
            ("avg_uniformity",), ("avg_water_productivity",),
        ]
        type(self.mock_cursor).description = unittest.mock.PropertyMock(
            side_effect=[zone_cols, overall_cols]
        )
        self.mock_cursor.fetchall.return_value = [
            ("zone-001", "Zone A", 10, 5000.0, 500.0, 85.0, 0.9, 2.5, 12500.0, 4250.0),
        ]
        self.mock_cursor.fetchone.return_value = (10, 5000.0, 85.0, 0.9, 2.5)
        result = get_water_efficiency(self.conn, "loc-001", days=30)
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["period_days"], 30)
        self.assertIn("overall", result)
        self.assertIn("zones", result)


class TestComputeWaterBalance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_water_balance_returns_balance(self):
        self.mock_cursor.fetchone.side_effect = [
            ("zone-001", "loc-001", "Zone A", 5000.0, 30.0),  # zone info
            (2500.0,),   # irrigation liters
            (10.0,),     # rainfall mm
            (8.0,),      # etc_mm total
            (45.0,),     # current moisture
        ]
        result = compute_water_balance(self.conn, "zone-001")
        self.assertEqual(result["zone_id"], "zone-001")
        self.assertIn("net_balance_liters", result)
        self.assertIn("status", result)
        self.assertIn(result["status"], ["surplus", "deficit", "balanced"])

    def test_water_balance_zone_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = compute_water_balance(self.conn, "zone-999")
        self.assertEqual(result["error"], "zone_not_found")


class TestOptimizeSchedule(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.schedule_cols = [
            ("id",), ("scheduled_start",), ("planned_volume_l",), ("etc_mm",),
            ("rainfall_forecast_mm",), ("current_soil_moisture_pct",),
        ]
        self.target_cols = [
            ("target_min_pct",), ("target_max_pct",), ("irrigation_trigger_pct",), ("refill_to_pct",),
        ]
        self.zone_cols = [("area_m2",)]
        type(self.mock_cursor).description = unittest.mock.PropertyMock(
            side_effect=[
                self.schedule_cols,
                self.target_cols,
                self.zone_cols,
            ]
        )

    def test_optimize_no_target(self):
        self.mock_cursor.fetchone.side_effect = [
            None,  # no pending schedule
            None,  # no moisture target
            (5000.0,),  # zone area (runs before early return)
        ]
        result = optimize_schedule(self.conn, "zone-001")
        self.assertFalse(result["optimized"])
        self.assertEqual(result["reason"], "no_moisture_target")

    def test_optimize_no_current_moisture(self):
        self.mock_cursor.fetchone.side_effect = [
            # One row per query, matching real cursor consumption.
            ("sched-1", None, 500.0, 4.0, 0.0, None),
            (50.0, 65.0, 40.0, 65.0),
            # zone area
            (5000.0,),
        ]
        result = optimize_schedule(self.conn, "zone-001")
        self.assertFalse(result["optimized"])
        self.assertEqual(result["reason"], "no_current_moisture")


class TestGetEfficiencyReport(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_efficiency_report_returns_report(self):
        week_cols = [
            ("week",), ("event_count",), ("total_volume_l",),
            ("avg_efficiency",), ("avg_uniformity",), ("avg_productivity",),
            ("total_yield_kg",),
        ]
        zone_cols = [
            ("zone_id",), ("zone_name",), ("total_irrigated_l",), ("total_events",),
        ]
        summary_cols = [
            ("overall_efficiency",), ("overall_uniformity",), ("overall_productivity",),
            ("total_volume_l",), ("total_yield_kg",),
        ]
        type(self.mock_cursor).description = unittest.mock.PropertyMock(
            side_effect=[week_cols, zone_cols, summary_cols]
        )
        self.mock_cursor.fetchall.side_effect = [
            [],  # weekly trends
            [("zone-001", "Zone A", 5000.0, 10)],  # by zone
        ]
        self.mock_cursor.fetchone.return_value = (85.0, 0.9, 2.5, 5000.0, 12500.0)
        result = get_efficiency_report(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertIn("summary", result)
        self.assertIn("by_zone", result)
        self.assertIn("weekly_trends", result)


if __name__ == "__main__":
    unittest.main()
