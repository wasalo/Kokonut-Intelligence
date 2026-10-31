from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/directus-polymorphic-lineage-preflight.py"
SPEC = importlib.util.spec_from_file_location("directus_polymorphic_lineage_preflight", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)
SCHEMA_CHECK_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/check-directus-polymorphic-lineage-schema-disposable.py"
)
SCHEMA_SPEC = importlib.util.spec_from_file_location(
    "directus_polymorphic_lineage_schema_check", SCHEMA_CHECK_PATH,
)
assert SCHEMA_SPEC is not None and SCHEMA_SPEC.loader is not None
schema_check = importlib.util.module_from_spec(SCHEMA_SPEC)
SCHEMA_SPEC.loader.exec_module(schema_check)


class FakeCursor:
    def __init__(self, result_sets):
        self.result_sets = iter(result_sets)
        self.statements: list[str] = []
        self.current_rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement):
        self.statements.append(statement)
        if statement.lstrip().startswith("WITH source_rows"):
            self.current_rows = next(self.result_sets)

    def fetchall(self):
        return self.current_rows


class FakeConnection:
    def __init__(self, result_sets):
        self.fake_cursor = FakeCursor(result_sets)
        self.rollback = Mock()
        self.close = Mock()

    def cursor(self):
        return self.fake_cursor


def test_allowlist_is_static_and_lineage_paths_are_explicit():
    workflow_sql = preflight.build_workflow_history_query()
    approval_sql = preflight.build_approval_query()
    for source in preflight.DIRECT_LOCATION_SOURCES:
        assert f"FROM public.{source} AS source_row" in workflow_sql
        assert f"FROM public.{source} AS source_row" in approval_sql
    assert "public.protocol_execution_intent" in approval_sql
    assert "public.protocol_project_location" in approval_sql
    assert "mapping.id = intent.mapping_id" in approval_sql
    assert "location.id = source.location_id" in workflow_sql
    assert "location.id = source.location_id" in approval_sql
    assert "CASE WHEN history.collection IS NOT NULL" in workflow_sql
    assert "ELSE 'unsupported' END AS collection" in workflow_sql
    assert "history.collection IS NULL" in workflow_sql
    assert "approval.collection IS NULL" in approval_sql
    assert "approval.action IS NOT NULL" in approval_sql
    assert "COUNT(*)::bigint AS row_count" in workflow_sql
    assert "COUNT(*)::bigint AS row_count" in approval_sql
    assert "SELECT *" not in workflow_sql.upper()
    assert "SELECT *" not in approval_sql.upper()


def test_aggregate_output_contains_only_static_groups_and_counts():
    connection = FakeConnection([
        [
            ("farm_activity", "resolved", 2),
            ("unsupported", "unsupported", 3),
            ("expense_event", "unresolved", 1),
            # Simulate an unexpected driver/source label; never echo it.
            ("SECRET_COLLECTION private row marker", "SECRET_CLASS", 4),
            (None, "unsupported", 6),
        ],
        [
            ("protocol_execution_intent", "approve", "resolved", 1),
            ("unsupported", "other", "unsupported", 2),
            ("SECRET_COLLECTION private row marker", "SECRET_ACTION", "SECRET_CLASS", 5),
            (None, None, "unsupported", 7),
        ],
    ])

    result = preflight.get_aggregate_counts(connection)
    encoded = json.dumps(result, sort_keys=True)
    assert "SECRET" not in encoded
    assert "private row marker" not in encoded
    assert result["workflow_history"]["totals"] == {
        "resolved": 2,
        "unresolved": 1,
        "unsupported": 13,
    }
    assert result["approval"]["totals"] == {
        "resolved": 1,
        "unresolved": 0,
        "unsupported": 14,
    }
    assert connection.fake_cursor.statements[0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    )
    assert len(connection.fake_cursor.statements) == 3


def test_missing_dsn_blocks_without_connecting(monkeypatch, capsys):
    connect = Mock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(preflight.psycopg2, "connect", connect)
    monkeypatch.delenv("DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN", raising=False)

    assert preflight.main() == 2
    assert json.loads(capsys.readouterr().out) == {
        "result": "blocked",
        "reason": "DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN must select the read-only target",
    }
    connect.assert_not_called()


def test_schema_replay_diagnostic_exposes_only_sqlstate():
    assert schema_check.extract_sqlstate(
        "ERROR:  42703: column missing_field does not exist\nLINE 1: ..."
    ) == "42703"
    assert schema_check.extract_sqlstate(
        "SQL state: 42P01\nprivate database diagnostic"
    ) == "42P01"
    assert schema_check.extract_sqlstate("private row text without a SQLSTATE") is None


def test_schema_replay_failure_metadata_keeps_only_allowlisted_aggregates():
    metadata = schema_check.extract_safe_aggregate_metadata(
        "catalog\t30\t30\t70\t70\nworkflow_history\t0\n"
        "private row text\tprivate record id\n"
    )
    assert metadata == {
        "catalog": {
            "relations_expected": 30,
            "relations_present": 30,
            "columns_expected": 70,
            "columns_present": 70,
        },
        "workflow_history": {"aggregate_group_count": 0},
    }


def test_schema_catalog_projection_names_are_defined_for_validation_wrapper():
    catalog_sql = schema_check.expected_catalog_sql()
    assert "AS expected_relations" in catalog_sql
    assert "AS present_relations" in catalog_sql
    assert "AS expected_columns" in catalog_sql
    assert "AS present_columns" in catalog_sql
    validation_sql = schema_check.sql_validation()
    assert "expected_relations, present_relations" in validation_sql
    assert "expected_columns, present_columns" in validation_sql


def test_cli_rolls_back_closes_and_never_prints_dsn_or_database_errors(monkeypatch, capsys):
    dsn = "postgresql://secret-user:secret-password@host/private-db"
    connection = FakeConnection([[], []])
    monkeypatch.setenv("DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN", dsn)
    monkeypatch.setattr(preflight.psycopg2, "connect", Mock(return_value=connection))

    assert preflight.main() == 0
    output = capsys.readouterr().out
    assert dsn not in output
    assert "secret-password" not in output
    assert json.loads(output)["result"] == "completed"
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_cli_sanitizes_connection_failure(monkeypatch, capsys):
    dsn = "postgresql://private:password@host/private"
    monkeypatch.setenv("DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN", dsn)
    monkeypatch.setattr(
        preflight.psycopg2,
        "connect",
        Mock(side_effect=RuntimeError(f"database private text: {dsn}")),
    )

    assert preflight.main() == 1
    output = capsys.readouterr().out
    assert dsn not in output
    assert "private text" not in output
    assert json.loads(output) == {
        "error_type": "RuntimeError",
        "result": "failed",
        "sqlstate": None,
    }
