#!/usr/bin/env python3
"""
Tests for Equipment Usage Logging and OEE Tracking
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone, timedelta

from services.analytics.equipment import (
    log_equipment_usage,
    get_equipment_status,
    compute_oee,
    get_maintenance_schedule,
    equipment_cost_analysis,
    _format_status,
    _format_oee,
    _format_maintenance,
    _format_cost,
)


class TestEquipmentUsageLogging(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("log-001",)
        self.mock_cursor.description = [("id",)]

    def test_log_equipment_usage(self):
        start = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        with patch("services.analytics.equipment._update_utilization"):
            result = log_equipment_usage(
                self.conn, "loc-001", "asset-001", start, end,
                operation_type="plowing", output_produced=5.0, output_unit="hectares",
            )
            self.assertIn("log_id", result)
            self.assertEqual(result["location_id"], "loc-001")
            self.assertEqual(result["hours"], 4.0)

    def test_log_without_end_time(self):
        start = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
        result = log_equipment_usage(
            self.conn, "loc-001", "asset-001", start, operation_type="plowing",
        )
        self.assertIn("log_id", result)
        self.assertIsNone(result["end_time"])

    def test_log_with_fuel(self):
        start = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
        with patch("services.analytics.equipment._update_utilization"):
            result = log_equipment_usage(
                self.conn, "loc-001", "asset-001", start, end,
                fuel_consumed=20.0, energy_consumed_kwh=15.0,
            )
            self.assertIn("log_id", result)


class TestEquipmentStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_empty_status(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = []
        result = get_equipment_status(self.conn, "loc-001")
        self.assertEqual(result, [])

    def test_status_with_equipment(self):
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "Tractor 1", "vehicle", 50, "good", date(2026, 1, 1), "active", 75.0, 120.0, 200.0),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("capacity",),
            ("condition_status",), ("last_inspection_date",),
            ("status",), ("latest_utilization",),
            ("hours_this_month",), ("fuel_this_month",),
        ]
        result = get_equipment_status(self.conn, "loc-001")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Tractor 1")
        self.assertEqual(result[0]["latest_utilization"], 75.0)


class TestOEE(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_oee_no_data(self):
        self.mock_cursor.fetchone.return_value = ("Tractor 1", "vehicle", "50")
        self.mock_cursor.description = [("name",), ("asset_type",), ("capacity",)]
        self.mock_cursor.fetchall.side_effect = [[], []]
        result = compute_oee(self.conn, "asset-001", 30)
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["oee"], 0)

    def test_oee_computed(self):
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchone.return_value = ("Tractor 1", "vehicle", "50")
        self.mock_cursor.description = [("name",), ("asset_type",), ("capacity",)]
        self.mock_cursor.fetchall.side_effect = [
            [(now - timedelta(hours=4), now, 5.0, 20.0)],
            [(date.today(), 50.0, 4.0, 5.0)],
        ]
        result = compute_oee(self.conn, "asset-001", 30)
        self.assertIn("oee", result)
        self.assertEqual(result["asset_name"], "Tractor 1")

    def test_oee_asset_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = compute_oee(self.conn, "nonexistent", 30)
        self.assertEqual(result["error"], "Asset not found")


class TestMaintenance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_empty_maintenance(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = []
        result = get_maintenance_schedule(self.conn, "loc-001")
        self.assertEqual(result, [])

    def test_critical_needs_attention(self):
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "Old Tractor", "vehicle", "critical", date(2025, 6, 1), 220),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("condition_status",),
            ("last_inspection_date",), ("days_since_inspection",),
        ]
        result = get_maintenance_schedule(self.conn, "loc-001")
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["inspection_overdue"])
        self.assertEqual(result[0]["maintenance_urgency"], "critical")

    def test_good_condition_ok(self):
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "New Tractor", "vehicle", "good", date.today() - timedelta(days=30), 30),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("condition_status",),
            ("last_inspection_date",), ("days_since_inspection",),
        ]
        result = get_maintenance_schedule(self.conn, "loc-001")
        self.assertEqual(result[0]["maintenance_urgency"], "ok")

    def test_overdue_inspection(self):
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "Tractor", "vehicle", "good", date.today() - timedelta(days=100), 100),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("condition_status",),
            ("last_inspection_date",), ("days_since_inspection",),
        ]
        result = get_maintenance_schedule(self.conn, "loc-001")
        self.assertTrue(result[0]["inspection_overdue"])
        self.assertEqual(result[0]["maintenance_urgency"], "overdue")

    def test_no_inspection_date(self):
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "Tractor", "vehicle", "good", None, None),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("condition_status",),
            ("last_inspection_date",), ("days_since_inspection",),
        ]
        result = get_maintenance_schedule(self.conn, "loc-001")
        self.assertTrue(result[0]["inspection_overdue"])
        self.assertEqual(result[0]["maintenance_urgency"], "unknown")


class TestCostAnalysis(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_empty_cost_analysis(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = []
        self.mock_cursor.fetchone.return_value = (0,)
        result = equipment_cost_analysis(self.conn, "loc-001", 30)
        self.assertEqual(result["total_operating_cost_usd"], 0)
        self.assertEqual(result["total_hours"], 0)

    def test_cost_with_usage(self):
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "Tractor 1", "vehicle", 100, 50, 40, 10),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("total_fuel",),
            ("total_energy",), ("total_hours",), ("usage_count",),
        ]
        self.mock_cursor.fetchone.return_value = (50000,)
        result = equipment_cost_analysis(self.conn, "loc-001", 30)
        self.assertGreater(result["total_fuel_cost_usd"], 0)
        self.assertGreater(result["total_electricity_cost_usd"], 0)
        self.assertGreater(result["depreciation_estimate_usd"], 0)

    def test_cost_per_hour(self):
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "Tractor 1", "vehicle", 100, 50, 20, 5),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("total_fuel",),
            ("total_energy",), ("total_hours",), ("usage_count",),
        ]
        self.mock_cursor.fetchone.return_value = (50000,)
        result = equipment_cost_analysis(self.conn, "loc-001", 30)
        self.assertGreater(result["cost_per_hour"], 0)


class TestFormatting(unittest.TestCase):

    def test_format_status_empty(self):
        result = _format_status([])
        self.assertEqual(result, "No active equipment.")

    def test_format_status_with_equipment(self):
        result = _format_status([
            {"name": "Tractor 1", "asset_type": "vehicle", "condition_status": "good", "latest_utilization": 75.0},
        ])
        self.assertIn("Tractor 1", result)
        self.assertIn("75%", result)

    def test_format_oee(self):
        result = _format_oee({
            "asset_name": "Tractor 1",
            "period_days": 30,
            "availability": 85.0,
            "performance": 70.0,
            "quality": 95.0,
            "oee": 56.7,
        })
        self.assertIn("OEE", result)
        self.assertIn("56.7%", result)

    def test_format_oee_error(self):
        result = _format_oee({"error": "Not found"})
        self.assertIn("Not found", result)

    def test_format_maintenance_empty(self):
        result = _format_maintenance([])
        self.assertEqual(result, "No maintenance needed.")

    def test_format_cost(self):
        result = _format_cost({
            "period_days": 30,
            "total_fuel_cost_usd": 150.0,
            "total_electricity_cost_usd": 6.0,
            "total_operating_cost_usd": 156.0,
            "depreciation_estimate_usd": 13.70,
            "total_cost_usd": 169.70,
            "total_hours": 40.0,
            "cost_per_hour": 3.90,
        })
        self.assertIn("Fuel", result)
        self.assertIn("$169.70", result)


if __name__ == "__main__":
    unittest.main()
