"""Focused tests for migration discovery, tracking, and execution safety."""

import shlex
import subprocess
from pathlib import Path

import pytest

from services.migration import cli


def _sql_file(path: Path, content: str = "SELECT 1;") -> Path:
    path.write_text(content)
    return path


def test_discovery_uses_kind_and_full_filename_and_orders_schema_first(tmp_path, monkeypatch):
    schemas = tmp_path / "postgres"
    seeds = tmp_path / "seeds"
    schemas.mkdir()
    seeds.mkdir()
    _sql_file(schemas / "000_extensions.sql")
    _sql_file(schemas / "010_second.sql")
    _sql_file(schemas / "002_first.sql")
    _sql_file(seeds / "001_seed.sql")
    monkeypatch.setattr(cli, "SCHEMA_DIR", schemas)
    monkeypatch.setattr(cli, "SEED_DIR", seeds)

    files = cli._discover_files()

    assert [item["id"] for item in files] == [
        "schema:000_extensions.sql",
        "schema:002_first.sql",
        "schema:010_second.sql",
        "seed:001_seed.sql",
    ]

    schema_files = cli._discover_files(include_seeds=False)
    assert [item["id"] for item in schema_files] == [
        "schema:000_extensions.sql",
        "schema:002_first.sql",
        "schema:010_second.sql",
    ]


def test_discovery_rejects_duplicate_ids(tmp_path, monkeypatch):
    directory = tmp_path / "sql"
    directory.mkdir()
    migration = _sql_file(directory / "001_same.sql")

    class DuplicateDirectory:
        def glob(self, pattern):
            return [migration, migration]

    monkeypatch.setattr(cli, "SCHEMA_DIR", DuplicateDirectory())
    monkeypatch.setattr(cli, "SEED_DIR", tmp_path / "empty")

    with pytest.raises(cli.MigrationError, match="duplicate migration ID"):
        cli._discover_files()


def test_source_validation_rejects_duplicate_versions(tmp_path):
    first = _sql_file(tmp_path / "001_first.sql")
    second = _sql_file(tmp_path / "001_second.sql")
    files = [
        {"id": "schema:001_first.sql", "kind": "schema", "version": "001", "path": first},
        {"id": "schema:001_second.sql", "kind": "schema", "version": "001", "path": second},
    ]

    with pytest.raises(cli.MigrationError, match="duplicate migration version"):
        cli._validate_sources(files)


def test_source_validation_rejects_database_switch(tmp_path):
    migration = _sql_file(tmp_path / "001_connect.sql", "\\connect another_db;")
    files = [{
        "id": "schema:001_connect.sql",
        "kind": "schema",
        "version": "001",
        "path": migration,
    }]

    with pytest.raises(cli.MigrationError, match="cannot change databases"):
        cli._validate_sources(files)


def test_psql_raises_on_query_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "bad query"),
    )

    with pytest.raises(cli.MigrationError, match="bad query"):
        cli._psql("SELECT 1")


def test_psql_passes_values_as_variables_not_interpolated_sql(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cli._psql("SELECT :'value';", {"value": "name'; DROP TABLE x; --"})

    shell_command = captured["command"][2]
    assert shlex.quote("value=name'; DROP TABLE x; --") in shell_command
    assert "ON_ERROR_STOP=1" in shell_command
    assert shell_command.count("docker compose exec") == 1
    assert "database psql" in shell_command


def test_legacy_reconciliation_requires_exact_version_and_name(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_psql", lambda sql, variables=None: calls.append((sql, variables)))
    file_info = {
        "id": "schema:008_governance.sql",
        "version": "008",
        "name": "008_governance",
    }

    cli._reconcile_legacy([file_info])

    sql, variables = calls[0]
    assert "tracked.migration_id IS NULL" in sql
    assert "tracked.version = candidates.legacy_version" in sql
    assert "tracked.name = candidates.name" in sql
    assert variables == {
        "migration_id_0": "schema:008_governance.sql",
        "legacy_version_0": "008",
        "name_0": "008_governance",
    }


def test_tracking_initialization_uses_advisory_lock(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_psql", lambda sql, variables=None: calls.append(sql))

    cli._ensure_tracking_table()

    assert "pg_advisory_lock(777204681)" in calls[0]
    assert "pg_advisory_unlock(777204681)" in calls[0]


def test_apply_batch_locks_and_rechecks_before_applying(tmp_path, monkeypatch):
    migration = _sql_file(tmp_path / "001_o'hare.sql", "CREATE TABLE example (id int);")
    calls = []

    def fake_psql(sql, variables=None):
        calls.append({"sql": sql, "variables": variables})
        return type("Result", (), {"stdout": ""})()

    monkeypatch.setattr(cli, "_psql", fake_psql)
    cli._apply_files([{
        "id": "schema:001_o'hare.sql",
        "name": "001_o'hare",
        "path": migration,
        "checksum": "abc",
    }])

    assert len(calls) == 1

    apply_sql = calls[0]["sql"]
    assert "pg_advisory_lock(777204681)" in apply_sql
    assert "migration_applied" in apply_sql
    assert "\\if :check_migration_applied" in apply_sql
    assert "CREATE TABLE example" in apply_sql
    assert "INSERT INTO schema_migration" in apply_sql
    assert "ON CONFLICT" in apply_sql
    assert "o'hare" not in apply_sql
    assert calls[0]["variables"]["migration_id"] == "schema:001_o'hare.sql"


def test_plan_does_not_initialize_or_reconcile_tracking(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_discover_files", lambda include_seeds=True: [])
    monkeypatch.setattr(cli, "_validate_sources", lambda files: calls.append("validate"))
    monkeypatch.setattr(cli, "_get_applied", lambda: {})
    monkeypatch.setattr(cli, "_validate_applied", lambda files, applied: calls.append("checksums"))

    cli.cmd_plan()

    assert calls == ["validate", "checksums"]


def test_modified_applied_migration_is_rejected():
    files = [{"id": "schema:001_a.sql", "checksum": "new"}]
    applied = {"schema:001_a.sql": {"status": "applied", "checksum": "old"}}

    with pytest.raises(cli.MigrationError, match="was modified"):
        cli._validate_applied(files, applied)


def test_checksum_repair_requires_approved_migration(monkeypatch):
    monkeypatch.setattr(cli, "_discover_files", lambda: [])

    with pytest.raises(cli.MigrationError, match="migration not found"):
        cli.repair_checksum("schema:001_example.sql", "old", "reason", "operator")


def test_checksum_repair_rejects_unapproved_historical_checksum(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_discover_files",
        lambda: [{"id": "schema:046_ecological_modeling.sql", "checksum": "b" * 64}],
    )

    with pytest.raises(cli.MigrationError, match="not approved"):
        cli.repair_checksum("schema:046_ecological_modeling.sql", "a" * 64, "reason", "operator")


def test_checksum_repair_validates_state_and_records_audit(monkeypatch):
    old = cli.APPROVED_CHECKSUM_REPAIRS["schema:046_ecological_modeling.sql"]
    new = "b" * 64
    calls = []
    monkeypatch.setattr(
        cli,
        "_discover_files",
        lambda: [{"id": "schema:046_ecological_modeling.sql", "checksum": new}],
    )
    monkeypatch.setattr(cli, "_ensure_tracking_table", lambda: calls.append("ensure"))
    monkeypatch.setattr(cli, "_validate_repair_schema", lambda migration_id: calls.append(migration_id))

    def fake_psql(sql, variables=None):
        calls.append((sql, variables))
        if sql.lstrip().startswith("SELECT checksum"):
            return subprocess.CompletedProcess([], 0, f"{old}\tapplied\n", "")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(cli, "_psql", fake_psql)
    repair_id = cli.repair_checksum(
        "schema:046_ecological_modeling.sql", old, "repair historical drift", "operator"
    )

    assert repair_id
    assert calls[0:2] == ["ensure", "schema:046_ecological_modeling.sql"]
    repair_sql = next(
        entry[0] for entry in calls
        if isinstance(entry, tuple) and "schema_migration_repair" in entry[0]
    )
    assert "UPDATE schema_migration" in repair_sql
