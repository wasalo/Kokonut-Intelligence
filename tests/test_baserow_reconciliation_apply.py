import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from scripts.baserow_reconciliation_apply import (
    ApplyError,
    IDENTITY_KEYS,
    PostgresApplyStore,
    apply_projection,
    run_staging_apply,
    validate_apply_plan,
    validate_apply_target_config,
    validate_projection_bundle,
    prepare_apply_projection,
)
from scripts.baserow_reconciliation_projection import TARGET_COLUMNS


def synthetic_crop_row() -> dict[str, Any]:
    row: dict[str, Any] = {column: None for column in TARGET_COLUMNS["crop"]}
    row["id"] = "00000000-0000-4000-8000-000000000001"
    row["name"] = "synthetic crop"
    return row


def synthetic_activity_row() -> dict[str, Any]:
    row: dict[str, Any] = {column: None for column in TARGET_COLUMNS["farm_activity"]}
    row.update(
        {
            "id": "00000000-0000-4000-8000-000000000002",
            "location_id": "00000000-0000-4000-8000-000000000003",
            "activity_type": "synthetic activity",
            "activity_date": "2000-01-01",
            "status": "draft",
            "source_system": "synthetic-source",
            "source_id": "synthetic-source-row",
        }
    )
    return row


def crop_allowlist() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "target_tables": [{"target_table": "crop"}],
        "relationship_tables": [],
    }


def projection_bundle(rows_by_target, allowlist):
    canonical_rows = {
        target: [
            {
                column: (str(value) if isinstance(value, Decimal) else value)
                for column, value in row.items()
            }
            for row in rows
        ]
        for target, rows in sorted(rows_by_target.items())
    }
    digest = hashlib.sha256(
        json.dumps(
            canonical_rows,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    allowlist_digest = hashlib.sha256(
        json.dumps(
            allowlist,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "rows_by_target": rows_by_target,
        "projection_sha256": digest,
        "source": {
            "snapshot_sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "crosswalk_sha256": "c" * 64,
            "allowlist_sha256": allowlist_digest,
            "manifest_schema_hash_matched": True,
        },
        "report": {
            "run_type": "allowlisted_scratch_projection",
            "import_authorized": False,
            "summary": {"projection_sha256": digest},
        },
    }


class MemoryApplyStore:
    def __init__(self, rows: dict[str, list[dict[str, Any]]] | None = None):
        self.rows: dict[str, list[dict[str, Any]]] = copy.deepcopy(rows or {})
        self.events: list[tuple[str, str | None]] = []
        self.committed = False
        self.rolled_back = False
        self.baseline: dict[str, list[dict[str, Any]]] | None = None

    def __enter__(self):
        self.baseline = copy.deepcopy(self.rows)
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        if exc_type is None:
            self.committed = True
        else:
            if self.baseline is not None:
                self.rows = self.baseline
            self.rolled_back = True
        return False

    def begin(self):
        self.events.append(("begin", None))

    def find_matches(self, target, record, identity_keys):
        self.events.append(("select", target))
        matches = [
            existing
            for existing in self.rows.get(target, [])
            if any(all(existing.get(column) == record.get(column) for column in key) for key in identity_keys)
        ]
        return copy.deepcopy(matches)

    def insert(self, target, record):
        self.events.append(("insert", target))
        self.rows.setdefault(target, []).append(copy.deepcopy(record))


class FixedMatchApplyStore(MemoryApplyStore):
    def __init__(self, matched_row: dict[str, Any]):
        super().__init__()
        self.matched_row = copy.deepcopy(matched_row)

    def find_matches(
        self,
        target: str,
        record: dict[str, Any],
        identity_keys: tuple[tuple[str, ...], ...],
    ) -> list[dict[str, Any]]:
        self.events.append(("select", target))
        return [copy.deepcopy(self.matched_row)]


class MemoryResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class MemoryDatabaseConnection:
    def __init__(self, store, database_name="kokonut_intelligence"):
        self.store = store
        self.database_name = database_name

    def __enter__(self):
        self.store.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self.store.__exit__(exc_type, exc, traceback)

    def get_dsn_parameters(self):
        return {"host": "staging-db", "dbname": self.database_name}

    def execute(self, sql, _params=None):
        if "current_database()" not in sql:
            raise AssertionError("unexpected SQL in the target verification fake")
        return MemoryResult({"database_name": self.database_name})


class WrongHostDatabaseConnection(MemoryDatabaseConnection):
    def get_dsn_parameters(self):
        return {"host": "unexpected-host", "dbname": self.database_name}


class RecordingResult:
    def __init__(self, rows=None, rowcount=0):
        self._rows = list(rows or [])
        self.rowcount = rowcount

    def all(self):
        return list(self._rows)


class RecordingConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params or {}))
        if sql.startswith("SELECT"):
            return RecordingResult()
        return RecordingResult(rowcount=1)


class ApplyPlanTests(unittest.TestCase):
    def test_preflight_scope_allows_only_the_owner_approved_partial_category_blocker(self):
        import scripts.baserow_reconciliation_apply as apply_module

        validator = getattr(apply_module, "validate_preflight_blockers", None)
        self.assertTrue(callable(validator), "preflight blocker scope validation is missing")
        allowlist = json.loads(
            (Path(__file__).resolve().parents[1] / "docs/phase1-baserow-projection-allowlist.json").read_text()
        )
        report = {
            "summary": {"structural_issue_count": 0, "blocking_fields_with_data": 1},
            "blocking_fields": [
                {"table_id": "317575", "field_id": "2330114", "disposition": "CONDITIONAL", "populated_cells": 533}
            ],
        }
        self.assertIsNone(validator(report, allowlist))

        report["summary"]["blocking_fields_with_data"] = 2
        report["blocking_fields"].append(
            {"table_id": "317575", "field_id": "4452998", "disposition": "HOLD_RELATIONSHIP", "populated_cells": 1}
        )
        with self.assertRaisesRegex(ApplyError, "unapproved populated-field blockers"):
            validator(report, allowlist)

    def test_plan_rejects_target_outside_the_allowlist(self):
        allowlist = {
            "schema_version": 1,
            "target_tables": [{"target_table": "crop"}],
            "relationship_tables": [],
        }
        rows_by_target = {"crop": [], "not_approved": []}

        with self.assertRaises(ApplyError):
            validate_apply_plan(rows_by_target, allowlist)

    def test_plan_rejects_missing_target_column(self):
        allowlist = {
            "schema_version": 1,
            "target_tables": [{"target_table": "crop"}],
            "relationship_tables": [],
        }
        row = synthetic_crop_row()
        row.pop("growing_season_days")

        with self.assertRaises(ApplyError):
            validate_apply_plan({"crop": [row]}, allowlist)

    def test_plan_rejects_missing_source_identity(self):
        allowlist = {
            "schema_version": 1,
            "target_tables": [{"target_table": "farm_activity"}],
            "relationship_tables": [],
        }
        row = synthetic_activity_row()
        row["source_id"] = None

        with self.assertRaises(ApplyError):
            validate_apply_plan({"farm_activity": [row]}, allowlist)

    def test_plan_rejects_duplicate_deterministic_identity(self):
        allowlist = {
            "schema_version": 1,
            "target_tables": [{"target_table": "crop"}],
            "relationship_tables": [],
        }
        first = synthetic_crop_row()
        second = synthetic_crop_row()
        second["name"] = "a different synthetic crop"

        with self.assertRaises(ApplyError):
            validate_apply_plan({"crop": [first, second]}, allowlist)

    def test_existing_exact_row_is_idempotent(self):
        row = synthetic_crop_row()
        store = MemoryApplyStore({"crop": [row]})

        with store:
            result = apply_projection(store, {"crop": [row]}, allowlist=crop_allowlist())

        self.assertEqual(result["tables"]["crop"], {"inserted": 0, "unchanged": 1})
        self.assertEqual(store.rows["crop"], [row])
        self.assertNotIn(("insert", "crop"), store.events)

    def test_new_row_is_inserted_and_read_back_exactly(self):
        row = synthetic_crop_row()
        store = MemoryApplyStore()

        with store:
            result = apply_projection(store, {"crop": [row]}, allowlist=crop_allowlist())

        self.assertEqual(result["summary"]["inserted_rows"], 1)
        self.assertEqual(result["summary"]["updated_rows"], 0)
        self.assertEqual(store.rows["crop"], [row])
        self.assertEqual(
            store.events,
            [("begin", None), ("select", "crop"), ("insert", "crop"), ("select", "crop")],
        )

    def test_identity_conflict_rolls_back_without_mutating_existing_row(self):
        expected = synthetic_crop_row()
        conflicting = synthetic_crop_row()
        conflicting["crop_category"] = "synthetic-conflict"
        baseline = {"crop": [conflicting]}
        store = MemoryApplyStore(baseline)

        with self.assertRaises(ApplyError):
            with store:
                apply_projection(store, {"crop": [expected]}, allowlist=crop_allowlist())

        self.assertTrue(store.rolled_back)
        self.assertEqual(store.rows, baseline)
        self.assertNotIn(("insert", "crop"), store.events)

    def test_late_identity_conflict_rolls_back_prior_batch_inserts(self):
        first = synthetic_crop_row()
        first["id"] = "00000000-0000-4000-8000-000000000004"
        first["name"] = "first synthetic crop"
        expected_conflict = synthetic_crop_row()
        expected_conflict["id"] = "00000000-0000-4000-8000-000000000005"
        expected_conflict["name"] = "second synthetic crop"
        existing_conflict = copy.deepcopy(expected_conflict)
        existing_conflict["crop_category"] = "synthetic-conflict"
        baseline = {"crop": [existing_conflict]}
        store = MemoryApplyStore(baseline)

        with self.assertRaises(ApplyError):
            with store:
                apply_projection(
                    store,
                    {"crop": [first, expected_conflict]},
                    allowlist=crop_allowlist(),
                )

        self.assertTrue(store.rolled_back)
        self.assertEqual(store.rows, baseline)

    def test_plan_only_mode_never_opens_a_database_connection(self):
        row = synthetic_crop_row()
        connection_calls = []

        def connection_factory():
            connection_calls.append(True)
            raise AssertionError("plan-only mode must not connect")

        report = run_staging_apply(
            projection_bundle({"crop": [row]}, crop_allowlist()),
            crop_allowlist(),
            target="staging",
            commit=False,
            confirm_target=None,
            runtime_environment="development",
            configured_host="localhost",
            expected_target_host=None,
            database_name="kokonut_intelligence",
            connection_factory=connection_factory,
        )

        self.assertEqual(connection_calls, [])
        self.assertEqual(report["summary"]["database_connections"], 0)
        self.assertEqual(report["summary"]["planned_rows"], 1)

    def test_plan_only_accepts_verified_projection_bundle_without_connecting(self):
        allowlist = crop_allowlist()
        bundle = projection_bundle({"crop": [synthetic_crop_row()]}, allowlist)
        connection_calls = []

        def connection_factory():
            connection_calls.append(True)
            raise AssertionError("verified plan mode must remain offline")

        report = run_staging_apply(
            bundle,
            allowlist,
            target="staging",
            commit=False,
            confirm_target=None,
            runtime_environment="development",
            configured_host="localhost",
            expected_target_host=None,
            database_name="kokonut_intelligence",
            connection_factory=connection_factory,
        )

        self.assertEqual(connection_calls, [])
        self.assertEqual(report["summary"]["planned_rows"], 1)
        self.assertEqual(report["summary"]["database_connections"], 0)

    def test_staging_target_guard_rejects_non_staging_runtime(self):
        with self.assertRaises(ApplyError):
            validate_apply_target_config(
                target="staging",
                commit=True,
                confirm_target="staging",
                runtime_environment="production",
                configured_host="staging-db",
                expected_target_host="staging-db",
                database_name="kokonut_intelligence",
            )

    def test_runtime_target_guard_rejects_before_opening_connection(self):
        calls = []

        def connection_factory():
            calls.append(True)
            raise AssertionError("invalid runtime must be rejected before connecting")

        with self.assertRaises(ApplyError):
            run_staging_apply(
                projection_bundle({"crop": [synthetic_crop_row()]}, crop_allowlist()),
                crop_allowlist(),
                target="staging",
                commit=True,
                confirm_target="staging",
                runtime_environment="production",
                configured_host="staging-db",
                expected_target_host="staging-db",
                database_name="kokonut_intelligence",
                connection_factory=connection_factory,
            )

        self.assertEqual(calls, [])

    def test_connected_database_mismatch_rolls_back_before_projection(self):
        store = MemoryApplyStore()
        connection = MemoryDatabaseConnection(store, database_name="unexpected_database")
        calls = []

        def connection_factory():
            calls.append(True)
            return connection

        with self.assertRaises(ApplyError):
            run_staging_apply(
                projection_bundle({"crop": [synthetic_crop_row()]}, crop_allowlist()),
                crop_allowlist(),
                target="staging",
                commit=True,
                confirm_target="staging",
                runtime_environment="staging",
                configured_host="staging-db",
                expected_target_host="staging-db",
                database_name="kokonut_intelligence",
                connection_factory=connection_factory,
                store_factory=lambda opened_connection: opened_connection.store,
            )

        self.assertEqual(calls, [True])
        self.assertTrue(store.rolled_back)
        self.assertEqual(store.rows, {})
        self.assertEqual(store.events, [])

    def test_connected_host_mismatch_rolls_back_before_projection(self):
        store = MemoryApplyStore()
        connection = WrongHostDatabaseConnection(store)

        with self.assertRaises(ApplyError):
            run_staging_apply(
                projection_bundle({"crop": [synthetic_crop_row()]}, crop_allowlist()),
                crop_allowlist(),
                target="staging",
                commit=True,
                confirm_target="staging",
                runtime_environment="staging",
                configured_host="staging-db",
                expected_target_host="staging-db",
                database_name="kokonut_intelligence",
                connection_factory=lambda: connection,
                store_factory=lambda opened_connection: opened_connection.store,
            )

        self.assertTrue(store.rolled_back)
        self.assertEqual(store.rows, {})
        self.assertEqual(store.events, [])

    def test_scratch_target_config_requires_explicit_target_confirmation(self):
        validate_apply_target_config(
            target="scratch",
            commit=True,
            confirm_target="scratch",
            runtime_environment="scratch",
            configured_host="/var/run/postgresql",
            expected_target_host="/var/run/postgresql",
            database_name="kokonut_intelligence",
        )

    def test_prepare_apply_projection_rejects_manifest_hash_mismatch(self):
        scratch_dir = Path(os.environ.get("TMPDIR", "/home/ubuntu/.hermes/cache/scratch"))
        with tempfile.TemporaryDirectory(prefix="ki21-apply-test-", dir=scratch_dir) as temporary_dir:
            paths = {name: Path(temporary_dir) / name for name in ("export.json", "manifest.json", "crosswalk.md", "allowlist.json")}
            export_bytes = json.dumps({"id": "115056", "tables": []}).encode("utf-8")
            actual_digest = hashlib.sha256(export_bytes).hexdigest()
            wrong_digest = "0" * 64 if actual_digest != "0" * 64 else "1" * 64
            manifest = {
                "applications": {
                    "database": {
                        "items": [{
                            "id": "115056",
                            "files": {"schema": f"schema_{wrong_digest}.json"},
                        }]
                    }
                }
            }
            paths["export.json"].write_bytes(export_bytes)
            paths["manifest.json"].write_text(json.dumps(manifest), encoding="utf-8")
            paths["crosswalk.md"].write_text("", encoding="utf-8")
            paths["allowlist.json"].write_text(
                json.dumps({"schema_version": 1, "target_tables": [], "relationship_tables": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ApplyError, "manifest"):
                prepare_apply_projection(
                    paths["export.json"],
                    paths["manifest.json"],
                    paths["crosswalk.md"],
                    paths["allowlist.json"],
                )

    def test_projection_bundle_accepts_only_unmodified_allowlisted_rows(self):
        allowlist = crop_allowlist()
        row = synthetic_crop_row()
        bundle = projection_bundle({"crop": [row]}, allowlist)

        validated_rows = validate_projection_bundle(bundle, allowlist)

        self.assertEqual(validated_rows, {"crop": [row]})

    def test_projection_bundle_rejects_rows_changed_after_projection(self):
        allowlist = crop_allowlist()
        bundle = projection_bundle({"crop": [synthetic_crop_row()]}, allowlist)
        bundle["rows_by_target"]["crop"][0]["name"] = "tampered after projection"

        with self.assertRaises(ApplyError):
            validate_projection_bundle(bundle, allowlist)

    def test_confirmed_staging_apply_uses_single_context_transaction(self):
        row = synthetic_crop_row()
        store = MemoryApplyStore()
        connection = MemoryDatabaseConnection(store)
        connection_calls = []

        def connection_factory():
            connection_calls.append(True)
            return connection

        report = run_staging_apply(
            projection_bundle({"crop": [row]}, crop_allowlist()),
            crop_allowlist(),
            target="staging",
            commit=True,
            confirm_target="staging",
            runtime_environment="staging",
            configured_host="staging-db",
            expected_target_host="staging-db",
            database_name="kokonut_intelligence",
            connection_factory=connection_factory,
            store_factory=lambda opened_connection: opened_connection.store,
        )

        self.assertEqual(connection_calls, [True])
        self.assertTrue(store.committed)
        self.assertEqual(report["summary"]["inserted_rows"], 1)
        self.assertEqual(report["summary"]["database_connections"], 1)

    def test_postgres_store_uses_allowlisted_parameterized_insert_only_sql(self):
        connection = RecordingConnection()
        store = PostgresApplyStore(connection)
        row = synthetic_crop_row()

        store.begin()
        self.assertEqual(store.find_matches("crop", row, IDENTITY_KEYS["crop"]), [])
        store.insert("crop", row)

        statements = [sql for sql, _params in connection.calls]
        self.assertTrue(any(sql.startswith('INSERT INTO public."crop"') for sql in statements))
        self.assertTrue(any(sql.startswith("SELECT ") for sql in statements))
        insert_sql, insert_params = next(
            (sql, params) for sql, params in connection.calls if sql.startswith("INSERT")
        )
        self.assertNotIn("synthetic crop", insert_sql)
        self.assertIn("synthetic crop", insert_params.values())
        self.assertFalse(any(sql.startswith(("UPDATE", "DELETE", "TRUNCATE")) for sql in statements))

    def test_optional_identity_component_is_skipped_when_id_is_available(self):
        row: dict[str, Any] = {column: None for column in TARGET_COLUMNS["location"]}
        row.update({
            "id": "00000000-0000-4000-8000-000000000004",
            "name": "synthetic location",
            "slug": "synthetic-location",
            "region": None,
        })
        connection = RecordingConnection()
        store = PostgresApplyStore(connection)

        self.assertEqual(store.find_matches("location", row, IDENTITY_KEYS["location"]), [])
        select_sql, params = connection.calls[-1]
        self.assertIn('"id" IS NOT DISTINCT FROM :identity_0_0', select_sql)
        self.assertIn('"slug" IS NOT DISTINCT FROM :identity_1_0', select_sql)
        self.assertNotIn("identity_2_", select_sql)
        self.assertEqual(params, {
            "identity_0_0": row["id"],
            "identity_1_0": row["slug"],
        })

    def test_exact_readback_accepts_database_uuid_and_date_types(self):
        expected = synthetic_activity_row()
        existing = copy.deepcopy(expected)
        existing["id"] = UUID(existing["id"])
        existing["location_id"] = UUID(existing["location_id"])
        existing["activity_date"] = date.fromisoformat(existing["activity_date"])
        store = FixedMatchApplyStore(existing)
        allowlist = {
            "schema_version": 1,
            "target_tables": [{"target_table": "farm_activity"}],
            "relationship_tables": [],
        }

        with store:
            result = apply_projection(
                store, {"farm_activity": [expected]}, allowlist=allowlist
            )

        self.assertEqual(result["summary"]["unchanged_rows"], 1)
        self.assertEqual(result["summary"]["inserted_rows"], 0)


if __name__ == "__main__":
    unittest.main()
