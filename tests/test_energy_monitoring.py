#!/usr/bin/env python3
"""
Tests for Energy Monitoring
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, PropertyMock
from datetime import date, timedelta

from services.analytics.energy_monitoring import (
    add_source,
    record_reading,
    get_consumption,
    get_efficiency,
    add_renewable,
    get_renewable_summary,
    get_energy_dashboard,
    compute_carbon_intensity,
    get_cost_analysis,
)


class TestAddSource(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_source_id(self):
        result = add_source(
            self.conn, "loc-001", "Solar PV", "solar",
        )
        self.assertIn("source_id", result)
        self.assertIsNotNone(result["source_id"])

    def test_records_name(self):
        result = add_source(
            self.conn, "loc-001", "Solar PV", "solar",
        )
        self.assertEqual(result["source_name"], "Solar PV")

    def test_records_type(self):
        result = add_source(
            self.conn, "loc-001", "Solar PV", "solar",
        )
        self.assertEqual(result["source_type"], "solar")

    def test_records_capacity(self):
        result = add_source(
            self.conn, "loc-001", "Solar PV", "solar", capacity_kw=15.0,
        )
        self.assertEqual(result["capacity_kw"], 15.0)

    def test_records_location(self):
        result = add_source(
            self.conn, "loc-001", "Solar PV", "solar",
        )
        self.assertEqual(result["location_id"], "loc-001")

    def test_commits(self):
        add_source(self.conn, "loc-001", "Solar PV", "solar")
        self.conn.commit.assert_called_once()

    def test_records_installation_date(self):
        d = date(2026, 1, 1)
        result = add_source(
            self.conn, "loc-001", "Solar PV", "solar",
            installation_date=d,
        )
        self.assertEqual(result["installation_date"], "2026-01-01")


class TestRecordReading(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("loc-001",)

    def test_returns_reading_id(self):
        result = record_reading(
            self.conn, "src-001", date(2026, 7, 1),
            "consumption", 100.0,
        )
        self.assertIn("reading_id", result)
        self.assertIsNotNone(result["reading_id"])

    def test_records_kwh(self):
        result = record_reading(
            self.conn, "src-001", date(2026, 7, 1),
            "consumption", 120.5,
        )
        self.assertEqual(result["kwh"], 120.5)

    def test_records_type(self):
        result = record_reading(
            self.conn, "src-001", date(2026, 7, 1),
            "production", 50.0,
        )
        self.assertEqual(result["reading_type"], "production")

    def test_computes_total_cost(self):
        result = record_reading(
            self.conn, "src-001", date(2026, 7, 1),
            "consumption", 100.0, cost_per_kwh=0.15,
        )
        self.assertEqual(result["total_cost"], 15.0)

    def test_no_cost(self):
        result = record_reading(
            self.conn, "src-001", date(2026, 7, 1),
            "consumption", 100.0,
        )
        self.assertIsNone(result["total_cost"])

    def test_raises_for_missing_source(self):
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            record_reading(
                self.conn, "nonexistent", date(2026, 7, 1),
                "consumption", 100.0,
            )

    def test_records_activity_type(self):
        result = record_reading(
            self.conn, "src-001", date(2026, 7, 1),
            "consumption", 100.0, activity_type="irrigation",
        )
        self.assertEqual(result["activity_type"], "irrigation")


class TestGetConsumption(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("source_name",), ("source_type",), ("activity_type",),
             ("total_kwh",), ("total_cost",), ("readings",)],
            [("source_type",), ("total_kwh",), ("total_cost",)],
        ])

    def test_returns_location_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (0, 0, 0, 0)
        result = get_consumption(self.conn, "loc-001", days=30)
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["period_days"], 30)

    def test_returns_totals(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (500.0, 75.0, 2, 10)
        result = get_consumption(self.conn, "loc-001", days=30)
        self.assertEqual(result["total_kwh"], 500.0)
        self.assertEqual(result["total_cost"], 75.0)

    def test_returns_by_activity(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("solar", "solar", "irrigation", 300.0, 0.0, 5)],
            [("solar", "solar", "lighting", 200.0, 30.0, 5)],
        ]
        self.mock_cursor.fetchone.return_value = (500.0, 30.0, 1, 10)
        result = get_consumption(self.conn, "loc-001", days=30)
        self.assertEqual(len(result["by_activity"]), 1)


class TestGetEfficiency(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_description(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("log_date",), ("period",), ("total_consumption_kwh",),
            ("total_production_kwh",), ("net_energy_kwh",),
            ("renewable_pct",), ("carbon_intensity_kg_kwh",),
            ("cost_per_unit_output",),
        ])

    def test_returns_period(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.side_effect = [(0, 0), (0,)]
        result = get_efficiency(self.conn, "loc-001", period="monthly")
        self.assertEqual(result["period"], "monthly")

    def test_returns_current_metrics(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.side_effect = [(1000.0, 200.0), (100.0,)]
        result = get_efficiency(self.conn, "loc-001")
        self.assertIn("current_metrics", result)
        self.assertEqual(result["current_metrics"]["total_consumption_kwh"], 1000.0)

    def test_with_existing_logs(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 6, 1), "monthly", 1000.0, 200.0, -800.0, 15.0, 0.3, 0.12),
        ]
        result = get_efficiency(self.conn, "loc-001")
        self.assertIsNotNone(result["latest_efficiency"])
        self.assertEqual(len(result["history"]), 1)


class TestAddRenewable(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_renewable_id(self):
        result = add_renewable(
            self.conn, "loc-001", "src-001", "solar_pv", 15.0,
        )
        self.assertIn("renewable_id", result)
        self.assertIsNotNone(result["renewable_id"])

    def test_records_type(self):
        result = add_renewable(
            self.conn, "loc-001", "src-001", "solar_pv", 15.0,
        )
        self.assertEqual(result["renewable_type"], "solar_pv")

    def test_records_capacity(self):
        result = add_renewable(
            self.conn, "loc-001", "src-001", "solar_pv", 15.0,
        )
        self.assertEqual(result["rated_capacity_kw"], 15.0)

    def test_computes_annual_generation(self):
        result = add_renewable(
            self.conn, "loc-001", "src-001", "solar_pv", 15.0,
        )
        self.assertEqual(result["annual_generation_kwh"], 22500.0)

    def test_computes_carbon_offset(self):
        result = add_renewable(
            self.conn, "loc-001", "src-001", "solar_pv", 15.0,
        )
        self.assertEqual(result["carbon_offset_kg"], 9000.0)

    def test_custom_annual_generation(self):
        result = add_renewable(
            self.conn, "loc-001", "src-001", "solar_pv", 15.0,
            annual_generation_kwh=20000.0,
        )
        self.assertEqual(result["annual_generation_kwh"], 20000.0)

    def test_commits(self):
        add_renewable(
            self.conn, "loc-001", "src-001", "solar_pv", 15.0,
        )
        self.conn.commit.assert_called_once()


class TestGetRenewableSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_description(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("renewable_type",), ("source_name",), ("source_type",),
            ("rated_capacity_kw",), ("annual_generation_kwh",),
            ("carbon_offset_kg",), ("status",),
        ])

    def test_returns_location_id(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0,)
        result = get_renewable_summary(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_sources(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("solar_pv", "Solar PV", "solar", 15.0, 22500.0, 9000.0, "active"),
        ]
        self.mock_cursor.fetchone.return_value = (50000.0,)
        result = get_renewable_summary(self.conn, "loc-001")
        self.assertEqual(result["active_sources"], 1)
        self.assertEqual(result["total_capacity_kw"], 15.0)

    def test_computes_share(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("solar_pv", "Solar PV", "solar", 15.0, 22500.0, 9000.0, "active"),
        ]
        self.mock_cursor.fetchone.return_value = (50000.0,)
        result = get_renewable_summary(self.conn, "loc-001")
        self.assertEqual(result["renewable_share_pct"], 45.0)

    def test_caps_at_100(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("solar_pv", "Solar PV", "solar", 50.0, 100000.0, 40000.0, "active"),
        ]
        self.mock_cursor.fetchone.return_value = (50000.0,)
        result = get_renewable_summary(self.conn, "loc-001")
        self.assertEqual(result["renewable_share_pct"], 100.0)


class TestGetEnergyDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_all_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            # get_consumption: by_activity
            [("source_name",), ("source_type",), ("activity_type",),
             ("total_kwh",), ("total_cost",), ("readings",)],
            # get_consumption: by_source
            [("source_type",), ("total_kwh",), ("total_cost",)],
            # get_efficiency: logs
            [("log_date",), ("period",), ("total_consumption_kwh",),
             ("total_production_kwh",), ("net_energy_kwh",),
             ("renewable_pct",), ("carbon_intensity_kg_kwh",),
             ("cost_per_unit_output",)],
            # get_renewable_summary: sources
            [("renewable_type",), ("source_name",), ("source_type",),
             ("rated_capacity_kw",), ("annual_generation_kwh",),
             ("carbon_offset_kg",), ("status",)],
            # source breakdown
            [("source_type",), ("count",), ("total_capacity",)],
            # trend
            [("reading_date",), ("consumption_kwh",), ("production_kwh",)],
        ])

    def test_returns_location_id(self):
        self._mock_all_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], [], [], [], [], []]
        self.mock_cursor.fetchone.side_effect = [
            (0, 0, 0, 0),  # consumption agg
            (0, 0),         # efficiency agg
            (0,),           # renewable cons
        ]
        result = get_energy_dashboard(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_all_sections(self):
        self._mock_all_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], [], [], [], [], []]
        self.mock_cursor.fetchone.side_effect = [
            (0, 0, 0, 0), (0, 0), (0,),
        ]
        result = get_energy_dashboard(self.conn, "loc-001")
        self.assertIn("consumption", result)
        self.assertIn("efficiency", result)
        self.assertIn("renewable", result)
        self.assertIn("source_breakdown", result)
        self.assertIn("trend_7d", result)


class TestComputeCarbonIntensity(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_description(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("source_type",), ("total_kwh",), ("consumption_kwh",),
            ("production_kwh",),
        ])

    def test_returns_location_id(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0,)
        result = compute_carbon_intensity(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_zero_consumption(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0,)
        result = compute_carbon_intensity(self.conn, "loc-001")
        self.assertEqual(result["carbon_intensity_kg_co2e_kwh"], 0)

    def test_grid_intensity(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("grid", 100.0, 100.0, 0.0),
        ]
        self.mock_cursor.fetchone.return_value = (0,)
        result = compute_carbon_intensity(self.conn, "loc-001")
        self.assertEqual(result["carbon_intensity_kg_co2e_kwh"], 0.45)
        self.assertEqual(result["total_emissions_kg_co2e"], 45.0)

    def test_solar_zero_intensity(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("solar", 100.0, 100.0, 0.0),
        ]
        self.mock_cursor.fetchone.return_value = (0,)
        result = compute_carbon_intensity(self.conn, "loc-001")
        self.assertEqual(result["carbon_intensity_kg_co2e_kwh"], 0.0)
        self.assertEqual(result["renewable_share_pct"], 100.0)

    def test_mixed_sources(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("grid", 100.0, 100.0, 0.0),
            ("solar", 100.0, 100.0, 0.0),
        ]
        self.mock_cursor.fetchone.return_value = (0,)
        result = compute_carbon_intensity(self.conn, "loc-001")
        self.assertEqual(result["carbon_intensity_kg_co2e_kwh"], 0.225)

    def test_returns_breakdown(self):
        self._mock_description()
        self.mock_cursor.fetchall.return_value = [
            ("grid", 100.0, 100.0, 0.0),
        ]
        self.mock_cursor.fetchone.return_value = (0,)
        result = compute_carbon_intensity(self.conn, "loc-001")
        self.assertEqual(len(result["breakdown"]), 1)
        self.assertEqual(result["breakdown"][0]["source_type"], "grid")


class TestGetCostAnalysis(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("activity_type",), ("total_kwh",), ("total_cost",),
             ("avg_cost_per_kwh",), ("readings",)],
            [("source_type",), ("total_kwh",), ("total_cost",),
             ("avg_cost_per_kwh",)],
        ])

    def test_returns_location_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (0, 0, None)
        result = get_cost_analysis(self.conn, "loc-001", days=30)
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_totals(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (150.0, 1000.0, 0.15)
        result = get_cost_analysis(self.conn, "loc-001", days=30)
        self.assertEqual(result["total_cost"], 150.0)
        self.assertEqual(result["total_kwh"], 1000.0)

    def test_monthly_projection(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.return_value = (100.0, 1000.0, 0.10)
        result = get_cost_analysis(self.conn, "loc-001", days=10)
        self.assertEqual(result["monthly_projected_cost"], 300.0)

    def test_returns_by_activity(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("irrigation", 500.0, 75.0, 0.15, 5)],
            [],
        ]
        self.mock_cursor.fetchone.return_value = (75.0, 500.0, 0.15)
        result = get_cost_analysis(self.conn, "loc-001", days=30)
        self.assertEqual(len(result["by_activity"]), 1)

    def test_returns_by_source(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [],
            [("grid", 500.0, 75.0, 0.15)],
        ]
        self.mock_cursor.fetchone.return_value = (75.0, 500.0, 0.15)
        result = get_cost_analysis(self.conn, "loc-001", days=30)
        self.assertEqual(len(result["by_source_type"]), 1)


if __name__ == "__main__":
    unittest.main()
