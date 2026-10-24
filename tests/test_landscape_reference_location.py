"""Contract tests for location-bound landscape foreign keys and views."""

import unittest
from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1]
    / "schemas/postgres/603_location_bound_landscape_references.sql"
).read_text()


class LandscapeReferenceLocationTests(unittest.TestCase):
    def test_all_landscape_habitat_links_include_location_in_database_constraint(self):
        for name in (
            "fk_corridor_source_habitat_location",
            "fk_corridor_target_habitat_location",
            "fk_buffer_habitat_location",
        ):
            with self.subTest(constraint=name):
                definition = MIGRATION.split(name, 1)[1].split("END IF", 1)[0]
                self.assertIn("FOREIGN KEY (location_id,", definition)
                self.assertIn("REFERENCES public.habitat_zone (location_id, id)", definition)
                self.assertIn("NOT VALID", definition)

    def test_existing_links_are_not_rewritten_and_views_filter_by_location(self):
        self.assertNotIn("UPDATE wildlife_corridor", MIGRATION)
        self.assertNotIn("UPDATE buffer_zone_monitoring", MIGRATION)
        self.assertIn("wc.location_id = hz.location_id", MIGRATION)
        self.assertIn("bzm.location_id = hz.location_id", MIGRATION)
        self.assertIn("src.location_id = wc.location_id", MIGRATION)
        self.assertIn("tgt.location_id = wc.location_id", MIGRATION)
        self.assertIn("hz.location_id = bzm.location_id", MIGRATION)

    def test_same_location_indexes_and_replay_guards_are_present(self):
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS uq_habitat_zone_location_id", MIGRATION)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_corridor_location_habitats", MIGRATION)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_buffer_location_habitat", MIGRATION)
        self.assertEqual(MIGRATION.count("IF NOT EXISTS"), 6)


if __name__ == "__main__":
    unittest.main()
