"""Focused tests for migration discovery, tracking, and execution safety."""

import shlex
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.migration import cli


def test_malformed_tracking_query_output_is_not_echoed(monkeypatch):
    secret_diagnostic = "postgresql://operator:secret@db.internal/kokonut"
    monkeypatch.setattr(
        cli,
        "_psql",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=f"{secret_diagnostic}\n"),
    )

    with pytest.raises(cli.MigrationError, match="invalid schema_migration query output") as error:
        cli._get_applied()

    assert secret_diagnostic not in str(error.value)


def _sql_file(path: Path, content: str = "SELECT 1;") -> Path:
    path.write_text(content)
    return path


def test_clean_bootstrap_declares_locked_directus_role_for_migration_replay():
    bootstrap = Path(__file__).parents[1] / "scripts" / "bootstrap-optional-roles.sql"
    source = bootstrap.read_text()

    assert "rolname = 'kokonut_directus_runtime'" in source
    assert "CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT NOSUPERUSER " in source
    assert "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS" in source
    assert "rolname = 'kokonut_worker_login'" in source
    assert "rolname = 'kokonut_runtime'" in source


def test_schema_migrate_bootstraps_optional_roles_before_applying(monkeypatch, capsys):
    files = [{"id": "schema:475_location_solution_retirement_review.sql", "kind": "schema"}]
    operations = []
    monkeypatch.setattr(cli, "_load_state", lambda include_seeds: (files, {}))
    monkeypatch.setattr(cli, "_psql", lambda statement: operations.append(("bootstrap", statement)))
    monkeypatch.setattr(cli, "_apply_files", lambda pending: operations.append(("apply", pending)))

    cli.cmd_migrate(schemas_only=True)

    assert [operation for operation, _value in operations] == ["bootstrap", "apply"]
    assert "kokonut_directus_runtime" in operations[0][1]
    assert "NOLOGIN" in operations[0][1]
    assert "Applying 1 migration(s)" in capsys.readouterr().out


def test_schema_migration_dry_run_does_not_bootstrap_or_apply(monkeypatch, capsys):
    files = [{"id": "schema:475_location_solution_retirement_review.sql", "kind": "schema"}]
    monkeypatch.setattr(cli, "_load_state", lambda include_seeds: (files, {}))
    monkeypatch.setattr(
        cli,
        "_bootstrap_optional_roles",
        lambda: pytest.fail("dry-run must not mutate global role state"),
    )
    monkeypatch.setattr(
        cli,
        "_apply_files",
        lambda _pending: pytest.fail("dry-run must not apply migrations"),
    )

    cli.cmd_migrate(dry_run=True, schemas_only=True)

    assert "Would apply 1 migration(s)" in capsys.readouterr().out


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


def test_discovery_includes_range_prefixed_seed_file(tmp_path, monkeypatch):
    schemas = tmp_path / "postgres"
    seeds = tmp_path / "seeds"
    schemas.mkdir()
    seeds.mkdir()
    _sql_file(schemas / "001_initial.sql")
    _sql_file(seeds / "064-068_impact_network.sql")
    monkeypatch.setattr(cli, "SCHEMA_DIR", schemas)
    monkeypatch.setattr(cli, "SEED_DIR", seeds)

    files = cli._discover_files()

    assert [item["id"] for item in files] == [
        "schema:001_initial.sql",
        "seed:064-068_impact_network.sql",
    ]
    assert files[1]["version"] == "064-068"
    cli._validate_sources(files)


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


def test_psql_raises_on_query_failure_without_exposing_database_output(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, "sensitive stdout", "sensitive database error"
        ),
    )

    with pytest.raises(cli.MigrationError, match="exit status 1") as error:
        cli._psql("SELECT 1")
    assert "sensitive" not in str(error.value)


def test_psql_timeout_does_not_expose_subprocess_output(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], 5, output="sensitive stdout", stderr="sensitive stderr"
        )

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    with pytest.raises(cli.MigrationError, match="TimeoutExpired") as error:
        cli._psql("SELECT 1")
    assert "sensitive" not in str(error.value)


def test_psql_passes_values_as_variables_not_interpolated_sql(monkeypatch):
    captured = {}
    child_env = {"PATH": "/synthetic/bin"}
    monkeypatch.setattr(cli, "worker_subprocess_environment", lambda: child_env)

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cli._psql("SELECT :'value';", {"value": "name'; DROP TABLE x; --"})

    shell_command = captured["command"][2]
    assert shlex.quote("value=name'; DROP TABLE x; --") in shell_command
    assert "ON_ERROR_STOP=1" in shell_command
    assert "psql -X -q" in shell_command
    assert shell_command.count("docker compose exec") == 1
    assert "database psql" in shell_command
    assert captured["env"] == child_env


def test_psql_pins_canonical_search_path(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        tokens = shlex.split(command[2])
        input_path = Path(tokens[tokens.index("<") + 1])
        captured["sql"] = input_path.read_text()
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cli._psql("SELECT current_schema();")

    assert captured["sql"].startswith("SET search_path = public, topology, tiger;\n")
    assert captured["sql"].endswith("SELECT current_schema();")


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
    assert apply_sql.count("BEGIN;") == 1
    assert "CREATE TABLE example" in apply_sql
    assert "INSERT INTO schema_migration" in apply_sql
    assert apply_sql.count("COMMIT;") == 1
    assert apply_sql.index("INSERT INTO schema_migration") < apply_sql.index("COMMIT;")
    assert "ON CONFLICT" in apply_sql
    assert "o'hare" not in apply_sql
    assert calls[0]["variables"]["migration_id"] == "schema:001_o'hare.sql"


def test_apply_batch_folds_explicit_transaction_into_atomic_ledger_write(tmp_path, monkeypatch):
    migration = _sql_file(
        tmp_path / "001_wrapped.sql",
        "-- explicit wrapper\nBEGIN;\nCREATE TABLE example (id int);\n"
        "COMMIT;\nCREATE INDEX extra_idx ON example(id);\n",
    )
    calls = []
    monkeypatch.setattr(
        cli,
        "_psql",
        lambda sql, variables=None: calls.append({"sql": sql, "variables": variables}),
    )

    cli._apply_files([{
        "id": "schema:001_wrapped.sql",
        "name": "001_wrapped",
        "path": migration,
        "checksum": "abc",
    }])

    apply_sql = calls[0]["sql"]
    assert apply_sql.count("BEGIN;") == 1
    assert apply_sql.count("COMMIT;") == 1
    assert apply_sql.index("CREATE TABLE example") < apply_sql.index("INSERT INTO schema_migration")
    assert apply_sql.index("CREATE INDEX extra_idx") < apply_sql.index("INSERT INTO schema_migration")
    assert apply_sql.index("INSERT INTO schema_migration") < apply_sql.index("COMMIT;")


def test_mobile_form_seed_locks_and_checks_source_parity_in_its_transaction(monkeypatch):
    calls = []

    def fake_psql(sql, variables=None):
        calls.append((sql, variables))
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(cli, "_psql", fake_psql)
    cli._apply_files([{
        "id": cli.MOBILE_FORM_SEED_ID,
        "name": "140_mobile_forms",
        "path": cli.SEED_DIR / "140_mobile_forms.sql",
        "checksum": "abc",
    }])

    guarded_sql = calls[0][0]
    assert "LOCK TABLE public.mobile_form IN SHARE ROW EXCLUSIVE MODE" in guarded_sql
    assert "LOCK TABLE public.mobile_form_version IN SHARE ROW EXCLUSIVE MODE" in guarded_sql
    assert "existing mobile form or active revision differs" in guarded_sql
    assert "consent_policy_evidence" in guarded_sql
    assert guarded_sql.index("LOCK TABLE") < guarded_sql.index("INSERT INTO mobile_form")
    assert guarded_sql.index("INSERT INTO mobile_form") < guarded_sql.index("INSERT INTO schema_migration")


def test_curated_migrate_preflights_mobile_forms_before_applying_batch(monkeypatch):
    files = [
        {"id": "seed:000_reference.sql"},
        {
            "id": cli.MOBILE_FORM_SEED_ID,
            "path": cli.SEED_DIR / "140_mobile_forms.sql",
        },
    ]
    applied_files = []
    calls = []
    monkeypatch.setattr(cli, "_load_state", lambda include_seeds: (files, {}))
    monkeypatch.setattr(cli, "_apply_files", applied_files.extend)

    def fake_psql(sql, variables=None):
        calls.append((sql, variables))
        return subprocess.CompletedProcess([], 0, "mismatch\n", "")

    monkeypatch.setattr(cli, "_psql", fake_psql)

    with pytest.raises(cli.MigrationError, match="active revision differs"):
        cli.cmd_migrate(
            only_migrations=["seed:000_reference.sql", cli.MOBILE_FORM_SEED_ID]
        )

    assert applied_files == []
    assert len(calls) == 1
    assert "public.mobile_form" in calls[0][0]
    assert "public.mobile_form_version" in calls[0][0]
    assert "farm_activity_v1" in calls[0][0]
    assert calls[0][1] is None


def test_curated_migrate_allows_empty_mobile_form_state(monkeypatch, capsys):
    files = [{
        "id": cli.MOBILE_FORM_SEED_ID,
        "path": cli.SEED_DIR / "140_mobile_forms.sql",
    }]
    applied_files = []
    monkeypatch.setattr(cli, "_load_state", lambda include_seeds: (files, {}))
    monkeypatch.setattr(
        cli,
        "_psql",
        lambda sql, variables=None: subprocess.CompletedProcess([], 0, "empty\n", ""),
    )
    monkeypatch.setattr(cli, "_apply_files", applied_files.extend)

    cli.cmd_migrate(only_migrations=[cli.MOBILE_FORM_SEED_ID])

    assert [item["id"] for item in applied_files] == [cli.MOBILE_FORM_SEED_ID]
    assert "Applying 1 migration(s)" in capsys.readouterr().out


def test_curated_migrate_accepts_exact_existing_mobile_form_state(monkeypatch, capsys):
    files = [{"id": cli.MOBILE_FORM_SEED_ID, "path": cli.SEED_DIR / "140_mobile_forms.sql"}]
    applied_files = []
    monkeypatch.setattr(cli, "_load_state", lambda include_seeds: (files, {}))
    monkeypatch.setattr(
        cli,
        "_psql",
        lambda sql, variables=None: subprocess.CompletedProcess([], 0, "matched\n", ""),
    )
    monkeypatch.setattr(cli, "_apply_files", applied_files.extend)

    cli.cmd_migrate(only_migrations=[cli.MOBILE_FORM_SEED_ID])

    assert [item["id"] for item in applied_files] == [cli.MOBILE_FORM_SEED_ID]
    assert "Applying 1 migration(s)" in capsys.readouterr().out


def test_transaction_wrapper_rejects_unmatched_boundary():
    with pytest.raises(cli.MigrationError, match="unsupported transaction boundaries"):
        cli._migration_body_without_transaction("schema:001_bad.sql", "BEGIN;\nSELECT 1;\n")


def test_plan_does_not_initialize_or_reconcile_tracking(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_discover_files", lambda include_seeds=True: [])
    monkeypatch.setattr(cli, "_validate_sources", lambda files: calls.append("validate"))
    monkeypatch.setattr(cli, "_get_applied", lambda: {})
    monkeypatch.setattr(cli, "_validate_applied", lambda files, applied: calls.append("checksums"))

    cli.cmd_plan()

    assert calls == ["validate", "checksums"]


def test_migrate_applies_only_requested_ids_in_requested_order(monkeypatch, capsys):
    files = [
        {"id": "schema:001_schema.sql"},
        {"id": "seed:010_first.sql"},
        {"id": "seed:020_second.sql"},
    ]
    applied_files = []
    monkeypatch.setattr(cli, "_load_state", lambda include_seeds: (files, {}))
    monkeypatch.setattr(cli, "_apply_files", applied_files.extend)

    cli.cmd_migrate(only_migrations=["seed:020_second.sql", "seed:010_first.sql"])

    assert [item["id"] for item in applied_files] == [
        "seed:020_second.sql",
        "seed:010_first.sql",
    ]
    assert "Applying 2 migration(s)" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("selected", "error"),
    [
        (["seed:010_first.sql", "seed:010_first.sql"], "must be unique"),
        (["seed:missing.sql"], "were not discovered"),
        ([], "requires at least one"),
    ],
)
def test_migrate_rejects_invalid_selected_ids_before_apply(monkeypatch, selected, error):
    files = [{"id": "seed:010_first.sql"}]
    applied_files = []
    monkeypatch.setattr(cli, "_load_state", lambda include_seeds: (files, {}))
    monkeypatch.setattr(cli, "_apply_files", applied_files.extend)

    with pytest.raises(cli.MigrationError, match=error):
        cli.cmd_migrate(only_migrations=selected)

    assert applied_files == []


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


def test_candidate_initial_extension_history_repair_is_explicit_and_audited(monkeypatch):
    migration_id = "schema:000_extensions.sql"
    old = cli.APPROVED_CHECKSUM_REPAIRS[migration_id]
    new = cli.APPROVED_CHECKSUM_REPAIR_TARGETS[migration_id]
    calls = []
    monkeypatch.setattr(
        cli, "_discover_files", lambda: [{"id": migration_id, "checksum": new}]
    )
    monkeypatch.setattr(cli, "_ensure_tracking_table", lambda: calls.append("ensure"))
    monkeypatch.setattr(
        cli, "_validate_repair_schema", lambda value: calls.append(("validate", value))
    )

    def fake_psql(sql, variables=None):
        calls.append((sql, variables))
        if sql.lstrip().startswith("SELECT checksum"):
            return subprocess.CompletedProcess([], 0, f"{old}\tapplied\n", "")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(cli, "_psql", fake_psql)
    repair_id = cli.repair_checksum(
        migration_id,
        old,
        "candidate source history matches verified repository-base migration",
        "operator",
    )

    assert repair_id
    assert calls[0:2] == ["ensure", ("validate", migration_id)]
    repair_call = next(
        entry for entry in calls
        if isinstance(entry, tuple) and "schema_migration_repair" in entry[0]
    )
    assert repair_call[1]["old_checksum"] == old
    assert repair_call[1]["new_checksum"] == new
    assert "UPDATE schema_migration" in repair_call[0]


def test_candidate_initial_extension_history_repair_requires_all_six_extensions(monkeypatch):
    migration_id = "schema:000_extensions.sql"
    sql_calls = []

    def fake_psql(sql):
        sql_calls.append(sql)
        return subprocess.CompletedProcess([], 0, "f\n", "")

    monkeypatch.setattr(cli, "_psql", fake_psql)
    with pytest.raises(cli.MigrationError, match="all six extensions"):
        cli._validate_repair_schema(migration_id)

    assert "pg_extension" in sql_calls[0]
    for extension in (
        "uuid-ossp", "pgcrypto", "postgis", "postgis_topology", "pg_trgm",
        "pg_stat_statements",
    ):
        assert extension in sql_calls[0]


def test_candidate_initial_extension_history_repair_accepts_complete_effect(monkeypatch):
    sql_calls = []

    def fake_psql(sql):
        sql_calls.append(sql)
        return subprocess.CompletedProcess([], 0, "t\n", "")

    monkeypatch.setattr(cli, "_psql", fake_psql)

    cli._validate_repair_schema("schema:000_extensions.sql")

    assert len(sql_calls) == 1


def test_candidate_initial_extension_history_repair_rejects_another_checksum(monkeypatch):
    migration_id = "schema:000_extensions.sql"
    monkeypatch.setattr(
        cli, "_discover_files", lambda: [{"id": migration_id, "checksum": "b" * 64}]
    )

    with pytest.raises(cli.MigrationError, match="not approved"):
        cli.repair_checksum(migration_id, "a" * 64, "unapproved drift", "operator")


def test_candidate_initial_extension_history_repair_rejects_changed_current_source(monkeypatch):
    migration_id = "schema:000_extensions.sql"
    monkeypatch.setattr(
        cli, "_discover_files", lambda: [{"id": migration_id, "checksum": "b" * 64}]
    )

    with pytest.raises(cli.MigrationError, match="current source checksum is not approved"):
        cli.repair_checksum(
            migration_id,
            cli.APPROVED_CHECKSUM_REPAIRS[migration_id],
            "unreviewed current source",
            "operator",
        )
