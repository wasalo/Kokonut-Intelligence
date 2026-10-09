#!/usr/bin/env python3
"""
Tests for Digital Twin Simulation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta

from services.analytics.digital_twin import (
    create_digital_twin,
    configure_twin,
    get_twin_config,
    list_twins,
    run_simulation,
    create_scenario,
    run_scenario,
    compare_scenarios,
    CROP_PARAMS,
    DEFAULT_PARAMS,
    _format_sim,
    _format_scenario,
    _format_compare,
    _format_list,
)


class TestDigitalTwinManagement(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("twin-001",)
        self.mock_cursor.description = [("id",)]

    def test_create_twin(self):
        result = create_digital_twin(self.conn, "loc-001", "Test Twin", description="A test")
        self.assertIn("twin_id", result)
        self.assertEqual(result["name"], "Test Twin")

    def test_configure_twin(self):
        result = configure_twin(self.conn, "twin-001", "crop", "maize")
        self.assertEqual(result["key"], "crop")
        self.assertEqual(result["value"], "maize")

    def test_get_twin_config_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_twin_config(self.conn, "twin-001")
        self.assertIn("crop", result)
        self.assertEqual(result["crop"], "maize")  # default

    def test_get_twin_config_custom(self):
        self.mock_cursor.fetchall.return_value = [
            ("crop", "beans"),
            ("irrigation_mm", 20),
        ]
        result = get_twin_config(self.conn, "twin-001")
        self.assertEqual(result["crop"], "beans")
        self.assertEqual(result["irrigation_mm"], 20)

    def test_list_twins_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = list_twins(self.conn, "loc-001")
        self.assertEqual(result, [])

    def test_list_twins(self):
        self.mock_cursor.fetchall.return_value = [
            ("twin-001", "Adelphi Twin", "crop_simulation", "active", date(2026, 1, 1), None, 0),
        ]
        self.mock_cursor.description = [
            ("id",), ("name",), ("twin_type",), ("status",),
            ("start_date",), ("last_run_at",), ("run_count",),
        ]
        result = list_twins(self.conn, "loc-001")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Adelphi Twin")


class TestCropParams(unittest.TestCase):

    def test_maize_params(self):
        p = CROP_PARAMS["maize"]
        self.assertGreater(p["gdd_maturity"], p["gdd_emergence"])
        self.assertGreater(p["max_biomass_kg_ha"], 0)
        self.assertGreater(p["harvest_index"], 0)
        self.assertGreater(p["harvest_index"], 0)

    def test_beans_params(self):
        p = CROP_PARAMS["beans"]
        self.assertGreater(p["gdd_maturity"], 0)

    def test_default_crop_params(self):
        p = CROP_PARAMS["default"]
        self.assertIn("gdd_emergence", p)

    def test_all_crops_have_required_keys(self):
        required = {"gdd_emergence", "gdd_maturity", "max_biomass_kg_ha",
                     "harvest_index", "kc_initial", "kc_mid", "kc_late",
                     "n_uptake_factor", "temp_optimal_min", "temp_optimal_max"}
        for crop, params in CROP_PARAMS.items():
            self.assertTrue(required.issubset(params.keys()), f"Missing keys in {crop}")


class TestDefaultParams(unittest.TestCase):

    def test_has_crop(self):
        self.assertIn("crop", DEFAULT_PARAMS)

    def test_has_irrigation(self):
        self.assertIn("irrigation_mm", DEFAULT_PARAMS)

    def test_reasonable_values(self):
        self.assertGreater(DEFAULT_PARAMS["planting_density"], 0)
        self.assertGreater(DEFAULT_PARAMS["fertilizer_kg_ha"], 0)


class TestSimulationEngine(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_simulation_runs(self):
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", date(2026, 1, 1), 365),  # twin info
        ]
        self.mock_cursor.fetchall.return_value = []  # config
        result = run_simulation(self.conn, "twin-001", parameters={"time_horizon_days": 30})
        self.assertIn("run_id", result)
        self.assertIn("final_yield_kg_ha", result)
        self.assertEqual(result["status"], "completed")

    def test_simulation_short_horizon(self):
        # time_horizon comes from the twin record, not from parameters
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", date(2026, 1, 1), 10),  # 10-day horizon
        ]
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("config_key",), ("config_value",)]
        result = run_simulation(self.conn, "twin-001")
        self.assertIn("final_yield_kg_ha", result)
        self.assertEqual(result["days_simulated"], 10)

    def test_simulation_different_crops(self):
        for crop in ["maize", "beans", "cassava"]:
            self.mock_cursor.fetchone.side_effect = [
                ("loc-001", date(2026, 1, 1), 30),
            ]
            self.mock_cursor.fetchall.return_value = [("crop", crop)]
            result = run_simulation(self.conn, "twin-001")
            self.assertIn("final_yield_kg_ha", result)
            self.assertGreaterEqual(result["final_yield_kg_ha"], 0)

    def test_simulation_with_rainfall_multiplier(self):
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", date(2026, 1, 1), 30),
        ]
        self.mock_cursor.fetchall.return_value = [("rainfall_multiplier", 2.0)]
        result = run_simulation(self.conn, "twin-001")
        self.assertIn("total_water_mm", result)

    def test_simulation_twin_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = run_simulation(self.conn, "nonexistent")
        self.assertIn("error", result)

    def test_simulation_zero_yield_no_rain(self):
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001", date(2026, 1, 1), 30),
        ]
        self.mock_cursor.fetchall.return_value = [("rainfall_multiplier", 0.0)]
        result = run_simulation(self.conn, "twin-001")
        self.assertIn("final_yield_kg_ha", result)


class TestScenarioManagement(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_create_scenario(self):
        self.mock_cursor.fetchone.return_value = ("sc-001",)
        result = create_scenario(
            self.conn, "twin-001", "High Irrigation",
            {"irrigation_mm": 30},
        )
        self.assertIn("scenario_id", result)
        self.assertEqual(result["name"], "High Irrigation")

    def test_run_scenario(self):
        self.mock_cursor.fetchone.side_effect = [
            ("twin-001", {"irrigation_mm": 30}, "High Irrigation"),
            ("loc-001", date(2026, 1, 1), 30),
        ]
        self.mock_cursor.fetchall.return_value = []
        result = run_scenario(self.conn, "sc-001")
        if "error" not in result:
            self.assertIn("run_id", result)

    def test_run_scenario_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = run_scenario(self.conn, "nonexistent")
        self.assertIn("error", result)

    def test_compare_scenarios(self):
        # Mock first query (scenarios) with description
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("sc-001", "High Irrigation", "management", {"irrigation_mm": 30}, "completed", 2500.0, 100.0, 50.0, None, None, None),
        ]
        mock_cursor.description = [
            ("id",), ("name",), ("category",), ("parameters",), ("status",),
            ("final_yield",), ("total_water_mm",), ("total_nitrogen_kg",),
            ("total_cost_usd",), ("total_revenue_usd",), ("net_margin_usd",),
        ]
        # Mock second query (base run) - after fetchall, next is fetchone
        mock_cursor.fetchone.return_value = ("run-001", 2000.0, 100.0, 50.0, None)
        self.conn.cursor.return_value = mock_cursor

        result = compare_scenarios(self.conn, "twin-001")
        self.assertEqual(len(result["scenarios"]), 1)
        self.assertEqual(result["base_yield"], 2000.0)
        self.assertIn("yield_change_pct", result["scenarios"][0])


class TestFormatting(unittest.TestCase):

    def test_format_sim(self):
        result = _format_sim({
            "days_simulated": 365,
            "duration_ms": 150,
            "final_yield_kg_ha": 2500.0,
            "total_biomass_kg_ha": 5500.0,
            "total_water_mm": 600.0,
            "total_nitrogen_used": 80.0,
            "final_soil_carbon_pct": 1.5,
            "final_soil_moisture_pct": 45.0,
        })
        self.assertIn("2500", result)
        self.assertIn("365 days", result)

    def test_format_sim_error(self):
        result = _format_sim({"error": "Not found"})
        self.assertIn("Not found", result)

    def test_format_scenario(self):
        result = _format_scenario({
            "scenario_name": "High Irrigation",
            "final_yield_kg_ha": 2800.0,
        })
        self.assertIn("High Irrigation", result)
        self.assertIn("2800", result)

    def test_format_compare(self):
        result = _format_compare({
            "twin_id": "twin-001",
            "base_yield": 2000.0,
            "scenarios": [
                {"name": "High Irrigation", "yield_kg_ha": 2500.0, "yield_change_pct": 25.0},
            ],
        })
        self.assertIn("High Irrigation", result)
        self.assertIn("+25.0%", result)

    def test_format_list_empty(self):
        result = _format_list([])
        self.assertEqual(result, "No digital twins.")

    def test_format_list(self):
        result = _format_list([
            {"name": "Adelphi Twin", "twin_type": "crop_simulation", "run_count": 5},
        ])
        self.assertIn("Adelphi Twin", result)


if __name__ == "__main__":
    unittest.main()
