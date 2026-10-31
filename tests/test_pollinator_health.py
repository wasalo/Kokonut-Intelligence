"""Focused contract tests for the pollinator service and migrations 155/602."""

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

    def test_pollinator_capture_writers_fail_before_database_access(self):
        calls = (
            (
                pollinators.record_observation,
                (self.conn, "loc-1", "honeybee", 12),
                "Unscoped pollinator observation writes are retired",
            ),
            (
                pollinators.create_habitat,
                (self.conn, "loc-1", "Flowers", "wildflower_strip", 120),
                "Unscoped pollinator habitat writes are retired",
            ),
            (
                pollinators.record_pesticide_impact,
                (self.conn, "loc-1", date(2026, 10, 1), "Product", "active", "high"),
                "Unscoped pesticide-impact writes are retired",
            ),
        )
        for writer, args, message in calls:
            with self.subTest(writer=writer.__name__):
                conn = MagicMock()
                args = (conn, *args[1:])
                with self.assertRaisesRegex(RuntimeError, message):
                    writer(*args)
                conn.cursor.assert_not_called()
                conn.commit.assert_not_called()
                conn.rollback.assert_not_called()

    def test_legacy_managed_hive_writers_fail_before_database_access(self):
        with self.assertRaisesRegex(RuntimeError, "authenticated Kokonut Gateway"):
            pollinators.add_hive(self.conn, "loc-1", "H-1")
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()
        self.conn.rollback.assert_not_called()

        with self.assertRaisesRegex(RuntimeError, "authenticated Kokonut Gateway"):
            pollinators.record_hive_inspection(self.conn, "loc-1", "H-1")
        self.conn.cursor.assert_not_called()
        self.conn.commit.assert_not_called()
        self.conn.rollback.assert_not_called()

    def test_retired_pollinator_cli_capture_commands_do_not_open_database(self):
        from services.analytics import cli_pollinator_health

        commands = {command.name: command for command in cli_pollinator_health.cli._commands}
        self.assertFalse(commands["record-observation"].needs_db)
        self.assertFalse(commands["create-habitat"].needs_db)
        self.assertFalse(commands["record-pesticide"].needs_db)


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

    def test_capture_write_denial_migration_is_replay_safe_and_read_preserving(self):
        sql = (
            Path(__file__).parents[1]
            / "schemas/postgres/693_runtime_pollinator_capture_writes_read_only.sql"
        ).read_text()
        self.assertEqual(sql.count("BEGIN;"), 1)
        self.assertEqual(sql.count("COMMIT;"), 1)
        self.assertIn("'pollinator_observation'", sql)
        self.assertIn("'pollinator_habitat'", sql)
        self.assertIn("'pesticide_impact_log'", sql)
        self.assertIn("'kokonut_runtime'", sql)
        self.assertIn("'kokonut_directus_runtime'", sql)
        self.assertIn("'PUBLIC'", sql)
        self.assertIn("GRANT SELECT ON TABLE %I.%I TO %s", sql)
        self.assertIn("REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I)", sql)
        self.assertIn("does not make reads tenant-safe", sql)


if __name__ == "__main__":
    unittest.main()
