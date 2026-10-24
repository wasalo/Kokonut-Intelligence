"""Privacy and query-contract tests for the landscape reference preflight."""

import unittest

from services.analytics.landscape_reference_preflight import (
    REFERENCE_TYPES,
    get_location_reference_mismatch_counts,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement):
        self.statements.append(statement)

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.fake_cursor = FakeCursor(rows)

    def cursor(self):
        return self.fake_cursor


class LandscapeReferencePreflightTests(unittest.TestCase):
    def test_query_is_read_only_location_qualified_and_aggregate_only(self):
        connection = FakeConnection([(reference_type, 0) for reference_type in REFERENCE_TYPES])
        get_location_reference_mismatch_counts(connection)
        transaction_sql, lock_timeout_sql, statement_timeout_sql, query_sql = (
            connection.fake_cursor.statements
        )

        self.assertEqual(
            transaction_sql,
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        )
        self.assertEqual(lock_timeout_sql, "SET LOCAL lock_timeout = '2s'")
        self.assertEqual(statement_timeout_sql, "SET LOCAL statement_timeout = '30s'")
        self.assertEqual(query_sql.count("COUNT(*)"), 3)
        self.assertEqual(query_sql.count("habitat.location_id ="), 3)
        self.assertEqual(query_sql.count("NOT EXISTS"), 3)
        self.assertNotIn("SELECT corridor.id", query_sql)
        self.assertNotIn("SELECT habitat.id", query_sql)
        self.assertNotIn("zone_name", query_sql)
        self.assertNotIn("location_name", query_sql)

    def test_result_contains_only_fixed_categories_and_global_counts(self):
        connection = FakeConnection([
            ("buffer_habitat", 2),
            ("corridor_source", 1),
            ("corridor_target", 0),
        ])

        report = get_location_reference_mismatch_counts(connection)

        self.assertEqual(
            connection.fake_cursor.statements[0],
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        )
        self.assertIn("SELECT 'corridor_source'", connection.fake_cursor.statements[3])
        self.assertEqual(report["scope"], "all_locations_global_aggregate")
        self.assertEqual(
            report["location_reference_mismatch_counts"],
            {"corridor_source": 1, "corridor_target": 0, "buffer_habitat": 2},
        )
        self.assertEqual(report["total_location_reference_mismatch_count"], 3)
        self.assertEqual(report["status"], "mismatches_present")
        self.assertEqual(set(report["location_reference_mismatch_counts"]), set(REFERENCE_TYPES))

    def test_empty_archive_reports_zero_for_each_reference_type(self):
        report = get_location_reference_mismatch_counts(
            FakeConnection([(reference_type, 0) for reference_type in REFERENCE_TYPES])
        )

        self.assertEqual(report["total_location_reference_mismatch_count"], 0)
        self.assertEqual(report["status"], "no_mismatches")

    def test_unknown_categories_and_invalid_counts_fail_closed(self):
        invalid_rows = (
            [("unexpected_identifier", 1)],
            [("corridor_source", -1)],
            [("corridor_source", "1")],
            [("corridor_source", 1)] * 2,
            [("corridor_source", 1)],
        )
        for rows in invalid_rows:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                get_location_reference_mismatch_counts(FakeConnection(rows))


if __name__ == "__main__":
    unittest.main()
