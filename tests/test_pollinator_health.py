"""Focused contract tests for the pollinator service and migrations 155/602."""

import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

from services.analytics import pollinator_health as pollinators


class PollinatorWriteTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value

    def test_observation_targets_schema_and_defaults_review_state(self):
        result = pollinators.record_observation(self.conn, "loc-1", "honeybee", 12)
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("INSERT INTO pollinator_observation", sql)
        self.assertIn("observation_date", sql)
        self.assertIn("plot_id", sql)
        self.assertIn("'recorded'", sql)
        self.assertNotIn("habitat_area_id", sql)
        self.assertEqual(params[7], "visual_count")
        self.assertEqual(result["status"], "recorded")
        self.assertEqual(result["observation_date"], date.today().isoformat())
        self.conn.commit.assert_called_once()
        self.cursor.close.assert_called_once()

    def test_observation_maps_legacy_visual_and_serializes_weather(self):
        pollinators.record_observation(
            self.conn, "loc-1", "butterfly", 3, observation_method="visual",
            weather_conditions="sunny", observation_date=date(2026, 10, 1),
        )
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("weather_conditions", sql)
        self.assertEqual(params[7], "visual_count")
        self.assertEqual(json.loads(params[9]), {"description": "sunny"})
        self.assertEqual(params[3], date(2026, 10, 1))

    def test_observation_rejects_schema_invalid_type_before_database(self):
        with self.assertRaises(ValueError):
            pollinators.record_observation(self.conn, "loc-1", "bumblebee", 1)
        self.conn.cursor.assert_not_called()

    def test_habitat_maps_legacy_alias_but_rejects_unknown_type(self):
        result = pollinators.create_habitat(
            self.conn, "loc-1", "Flowers", "wildflower", 120,
            plant_species=["clover"], bloom_start_month=3,
        )
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("INSERT INTO pollinator_habitat", sql)
        self.assertIn("nesting_sites", sql)
        self.assertEqual(params[3], "wildflower_strip")
        self.assertEqual(result["habitat_type"], "wildflower_strip")
        conn = MagicMock()
        with self.assertRaises(ValueError):
            pollinators.create_habitat(conn, "loc-1", "Bad", "clover", 1)
        conn.cursor.assert_not_called()

    def test_pesticide_writes_installed_log_and_all_structured_fields(self):
        pollinators.record_pesticide_impact(
            self.conn, "loc-1", date(2026, 10, 1), "Product", "active", "high",
            pollinator_safe_period_days=3, pollinator_mortality_observed=True,
            mortality_pct=12.5,
        )
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("INSERT INTO pesticide_impact_log", sql)
        self.assertNotIn("pollinator_pesticide_impact", sql)
        self.assertIn("pollinator_safe_period_days", sql)
        self.assertIn("pollinator_mortality_observed", sql)
        self.assertEqual(params[11:13], (3, True))

    def test_hive_score_and_category_are_kept_separate(self):
        score_result = pollinators.add_hive(self.conn, "loc-1", "H-1", colony_strength=8)
        _, score_params = self.cursor.execute.call_args.args
        self.assertIsNone(score_params[4])
        self.assertEqual(score_params[5], 8)
        self.assertEqual(score_result["colony_strength_score"], 8)
        self.cursor.reset_mock()
        category_result = pollinators.add_hive(self.conn, "loc-1", "H-2", colony_strength="strong")
        _, category_params = self.cursor.execute.call_args.args
        self.assertEqual(category_params[4], "strong")
        self.assertIsNone(category_params[5])
        self.assertEqual(category_result["colony_strength"], "strong")

    def test_inspection_is_location_scoped_and_updates_same_hive(self):
        self.cursor.fetchall.return_value = [("hive-uuid",)]
        self.cursor.rowcount = 1
        result = pollinators.record_hive_inspection(
            self.conn, "loc-1", "H-1", colony_strength="moderate", varroa_count=2,
        )
        calls = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertIn("WHERE location_id = %s AND hive_id = %s FOR UPDATE", calls[0])
        self.assertIn("INSERT INTO pollinator_hive_inspection", calls[1])
        self.assertIn("UPDATE hive_record", calls[2])
        self.assertIn("location_id = %s::uuid", calls[2])
        self.assertEqual(result["location_id"], "loc-1")
        self.conn.commit.assert_called_once()

    def test_inspection_rejects_missing_or_ambiguous_hive_and_rolls_back(self):
        for rows in ([], [("one",), ("two",)]):
            conn = MagicMock()
            cursor = conn.cursor.return_value
            cursor.fetchall.return_value = rows
            with self.assertRaises(ValueError):
                pollinators.record_hive_inspection(conn, "loc-1", "H-1")
            conn.rollback.assert_called_once()
            cursor.close.assert_called_once()
            self.assertEqual(cursor.execute.call_count, 1)

    def test_write_failure_rolls_back_and_closes_cursor(self):
        self.cursor.execute.side_effect = RuntimeError("database failure")
        with self.assertRaises(RuntimeError):
            pollinators.record_observation(self.conn, "loc-1", "honeybee", 1)
        self.conn.rollback.assert_called_once()
        self.cursor.close.assert_called_once()


class PollinatorReadTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value

    def test_summary_uses_reviewed_rows_and_bound_intervals(self):
        self.cursor.description = [(name,) for name in (
            "pollinator_type", "observations", "avg_count", "max_count", "first_obs",
            "last_obs", "first_half_avg", "second_half_avg", "total_count",
        )]
        self.cursor.fetchall.return_value = [(
            "honeybee", 4, 12.5, 20, date(2026, 9, 1), date(2026, 10, 1), 10, 15, 50,
        )]
        result = pollinators.get_pollinator_summary(self.conn, "loc-1", 30)
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("status IN ('verified', 'reviewed')", sql)
        self.assertNotIn("INTERVAL '%s days'", sql)
        self.assertEqual(params, (15, 15, "loc-1", 30))
        self.assertEqual(result["pollinator_types"][0]["trend"], "increasing")
        self.assertEqual(result["pollinator_types"][0]["total_count"], 50.0)

    def test_summary_rejects_invalid_window_before_database(self):
        for days in (0, -1, 3651, True):
            conn = MagicMock()
            with self.assertRaises(ValueError):
                pollinators.get_pollinator_summary(conn, "loc-1", days)
            conn.cursor.assert_not_called()

    def test_habitat_inventory_uses_current_columns_and_handles_null_area(self):
        self.cursor.description = [(name,) for name in (
            "id", "habitat_name", "habitat_type", "area_m2", "plant_species", "bloom_period",
            "bloom_start_month", "bloom_end_month", "water_source", "nesting_features",
            "nesting_sites", "condition", "last_maintenance", "notes",
        )]
        self.cursor.fetchall.return_value = [(
            "id", "Strip", "wildflower_strip", None, '["clover"]', None, 3, 8, True,
            '{"logs": 2}', "logs", "good", None, None,
        )]
        result = pollinators.get_habitat_inventory(self.conn, "loc-1")
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("nesting_features", sql)
        self.assertNotIn("management_notes", sql)
        self.assertEqual(params, ("loc-1",))
        self.assertEqual(result["total_habitat_m2"], 0)
        self.assertEqual(result["habitats"][0]["plant_species"], ["clover"])

    def test_pesticide_read_uses_current_log_and_counts_advisory_records(self):
        self.cursor.description = [(name,) for name in (
            "id", "application_date", "product_name", "active_ingredient", "toxicity_class",
            "application_rate", "rate_unit", "area_treated_m2", "bloom_stage_at_application",
            "pollinator_distance_m", "pollinator_safe_period_days", "pollinator_mortality_observed",
            "mortality_pct", "status", "total_matching",
        )]
        self.cursor.fetchall.side_effect = [
            [("p-1", date(2026, 10, 1), "P", "ingredient", "high", None, None, None, None,
              None, 3, True, 12.5, "verified", 1)],
            [("high", 1, 1)],
        ]
        result = pollinators.get_pesticide_risk(self.conn, "loc-1")
        sql, params = self.cursor.execute.call_args_list[0].args
        self.assertIn("FROM pesticide_impact_log", sql)
        self.assertIn("status IN ('recorded', 'verified', 'reviewed')", sql)
        self.assertNotIn("pollinator_pesticide_impact", sql)
        self.assertEqual(params, ("loc-1", 90, 500))
        self.assertEqual(result["total_applications"], 1)
        self.assertEqual(result["overall_risk"], "critical")
        self.assertEqual(result["applications"][0]["pollinator_risk"], "high")

    def test_hive_status_uses_location_bound_lateral_inspection(self):
        columns = (
            "id", "hive_id", "hive_type", "colony_strength", "colony_strength_score", "queen_status",
            "frame_count", "queen_year", "honey_yield_kg", "inspection_date", "varroa_count", "status",
            "avg_daily_foragers",
            "inspection_id", "last_inspection_date", "last_colony_strength", "last_colony_strength_score",
            "last_queen_status", "queen_seen", "last_varroa_count", "brood_pattern", "honey_stores",
            "disease_signs", "temperament", "population_estimate", "swarm_cells", "inspection_status",
        )
        self.cursor.description = [(name,) for name in columns]
        self.cursor.fetchall.return_value = [(
            "h-uuid", "H-1", "langstroth", "strong", 8, "present", 10, 2025,
            Decimal("12.5"), date(2026, 10, 1), 2, "active", Decimal("20"), "i-uuid", date(2026, 10, 1),
            "moderate", 6, "present", True, 3, "solid", "good", None, "calm", 5000, False, "verified",
        )]
        self.cursor.fetchone.return_value = (Decimal("8.0"),)
        result = pollinators.get_hive_status(self.conn, "loc-1")
        sql = self.cursor.execute.call_args_list[0].args[0]
        self.assertIn("LEFT JOIN LATERAL", sql)
        self.assertIn("pi.location_id = h.location_id AND pi.hive_record_id = h.id", sql)
        self.assertIn("po.location_id = h.location_id", sql)
        self.assertEqual(result["avg_colony_strength"], 8.0)
        self.assertEqual(result["hives"][0]["last_inspection"]["status"], "verified")
        self.assertEqual(result["hives"][0]["avg_daily_foragers"], 20.0)


class PollinatorMigrationContractTests(unittest.TestCase):
    def test_alignment_migration_is_additive_and_location_binds_hive_links(self):
        sql = (Path(__file__).parents[1] / "schemas/postgres/602_pollinator_health_kernel_alignment.sql").read_text()
        self.assertIn("ADD COLUMN IF NOT EXISTS hive_record_id UUID", sql)
        self.assertIn("FOREIGN KEY (location_id, hive_record_id)", sql)
        self.assertIn("REFERENCES public.hive_record (location_id, id)", sql)
        self.assertIn("ON DELETE SET NULL (hive_record_id)", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS pollinator_hive_inspection", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS source_system", sql)
        self.assertIn("idx_pollinator_obs_location_hive_date", sql)


if __name__ == "__main__":
    unittest.main()
