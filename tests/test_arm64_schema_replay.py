"""Regression coverage for partial progress in ARM64 schema replay evidence."""

import json
import runpy
from pathlib import Path

import pytest

replay_module = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "check-arm64-schema-replay.py"),
    run_name="arm64_schema_replay_test_module",
)
started_schema_migrations = replay_module["started_schema_migrations"]
failed_batch_progress = replay_module["failed_batch_progress"]
migration_command = replay_module["migration_command"]
safe_error_summary = replay_module["safe_error_summary"]
ReplayCommandFailure = replay_module["ReplayCommandFailure"]
run = replay_module["run"]
operator_scope_probe_command = replay_module["operator_scope_probe_command"]
parse_operator_scope_probe = replay_module["parse_operator_scope_probe"]
ensure_disposable_project_unused = replay_module["ensure_disposable_project_unused"]

probe_module = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "fixtures" / "sprint_operator_scope_probe.py"),
    run_name="sprint_operator_scope_probe_test_module",
)


def test_started_schema_migrations_extracts_ordered_ids_from_runner_log():
    output = """
2026-10-23 09:02:11 [kokonut.migration] INFO Applying migration schema:121_capability_tokens.sql...
2026-10-23 09:02:05 [kokonut.migration] INFO Applying migration schema:122_federation.sql...
2026-10-23 09:02:11 [kokonut.migration] INFO Applying migration schema:123_analysis_environments.sql...
2026-10-23 09:02:29 [kokonut.migration] ERROR Migration failed: psql execution failed with exit status 2
"""

    assert started_schema_migrations(output) == [
        "schema:121_capability_tokens.sql",
        "schema:122_federation.sql",
        "schema:123_analysis_environments.sql",
    ]


def test_started_schema_migrations_returns_empty_for_no_apply_log():
    assert started_schema_migrations("database startup failed") == []


def test_failed_batch_progress_tracks_the_failed_migration_and_applied_prefix():
    output = """
INFO Applying migration schema:642_first.sql...
INFO Applying migration schema:643_second.sql...
ERROR Migration failed: database error
"""

    assert failed_batch_progress(output, already_applied=540, total=639) == {
        "schema_files_applied": 541,
        "schema_files_pending": 97,
        "schema_files_failed": 1,
        "failed_migration": "schema:643_second.sql",
        "latest_applied_migration": "schema:642_first.sql",
    }


def test_failed_batch_progress_uses_prior_checkpoint_when_first_migration_fails():
    output = "INFO Applying migration schema:642_first.sql...\nERROR Migration failed"

    assert failed_batch_progress(output, already_applied=541, total=639) == {
        "schema_files_applied": 541,
        "schema_files_pending": 97,
        "schema_files_failed": 1,
        "failed_migration": "schema:642_first.sql",
    }


def test_failed_batch_progress_returns_none_when_cli_has_no_migration_marker():
    assert failed_batch_progress("database startup failed", already_applied=541, total=639) is None


def test_migration_command_preserves_batch_order_and_exact_migration_ids():
    command = migration_command(
        "test-project",
        "test-database",
        ["schema:642_first.sql", "schema:648_last.sql"],
    )

    assert command.count("--only-migration") == 2
    assert command[-4:] == [
        "--only-migration",
        "schema:642_first.sql",
        "--only-migration",
        "schema:648_last.sql",
    ]


def test_safe_error_summary_keeps_only_bounded_postgres_diagnostics():
    output = (
        "connection details should be omitted\n"
        "ERROR:  42704: role \\\"directus\\\" does not exist\n"
        "DETAIL: migration permission boundary\n"
        "password=must-not-appear\n"
    )

    summary = safe_error_summary(output)

    assert summary is not None
    assert "ERROR:" in summary
    assert "DETAIL:" in summary
    assert "password=must-not-appear" not in summary


def test_captured_failure_retains_output_for_migration_diagnostics(monkeypatch):
    def failed_process(*_args, **_kwargs):
        return replay_module["subprocess"].CompletedProcess(
            args=["migration"],
            returncode=2,
            stdout="applying schema:002",
            stderr="database error",
        )

    monkeypatch.setattr(replay_module["subprocess"], "run", failed_process)

    try:
        run(["migration"], capture=True)
    except ReplayCommandFailure as error:
        assert error.returncode == 2
        assert error.stdout == "applying schema:002"
        assert error.stderr == "database error"
    else:
        raise AssertionError("captured command failure should be raised")


def test_operator_probe_shares_only_the_disposable_database_network():
    command = operator_scope_probe_command("a" * 64, "local-kernel-client:test")

    assert command[command.index("--network") + 1] == "container:" + "a" * 64
    assert "--pull=never" in command and "--read-only" in command
    assert command.count("--volume") == 3
    assert all(
        command[index + 1].endswith(":ro")
        for index, value in enumerate(command) if value == "--volume"
    )
    assert "SPRINT_ADMIN_PASSWORD" in command
    assert not any(value.startswith("SPRINT_ADMIN_PASSWORD=") for value in command)
    assert "--publish" not in command


@pytest.mark.parametrize("container_id", ["", "../outside", "a" * 11, "g" * 64])
def test_operator_probe_rejects_non_container_ids(container_id):
    with pytest.raises(ValueError, match="container ID"):
        operator_scope_probe_command(container_id, "local-kernel-client:test")


def test_operator_probe_requires_both_tenants_and_a_success_result():
    good = {
        "result": "passed", "checks": list(replay_module["OPERATOR_PROBE_CHECKS"]),
        "synthetic_tenant_count": 2, "synthetic_location_count": 2,
        "synthetic_operator_count": 2, "runtime_public_tables_with_dml_and_rls_disabled": 4,
        "runtime_scoped_write_policy": {
            "private_relations_expected": 79,
            "mutation_denied_relations_expected": 12,
            "private_relations_verified": 79,
            "mutation_denied_relations_verified": 12,
            "direct_table_privilege_violations": 0,
            "direct_column_privilege_violations": 0,
            "farm_activity_ledger_readable": 1,
        },
    }
    assert parse_operator_scope_probe(json.dumps(good))["result"] == "passed"
    with pytest.raises(ValueError):
        parse_operator_scope_probe(json.dumps({**good, "synthetic_operator_count": 1}))
    with pytest.raises(ValueError):
        parse_operator_scope_probe(json.dumps({**good, "result": "failed"}))
    with pytest.raises(ValueError):
        parse_operator_scope_probe(json.dumps({**good, "checks": good["checks"][:-1]}))
    with pytest.raises(ValueError):
        parse_operator_scope_probe(json.dumps({**good, "runtime_public_tables_with_dml_and_rls_disabled": -1}))
    with pytest.raises(ValueError, match="scoped-write boundary"):
        parse_operator_scope_probe(json.dumps({**good, "runtime_scoped_write_policy": None}))
    with pytest.raises(ValueError, match="scoped-write ACL"):
        parse_operator_scope_probe(json.dumps({
            **good,
            "runtime_scoped_write_policy": {
                **good["runtime_scoped_write_policy"],
                "direct_column_privilege_violations": 1,
            },
        }))


def test_operator_probe_rejects_non_disposable_database_before_connecting(monkeypatch):
    monkeypatch.setenv("SPRINT_DISPOSABLE", "yes")
    monkeypatch.setenv("SPRINT_DATABASE", "kokonut_intelligence")

    def unexpected_connection(*_args, **_kwargs):
        raise AssertionError("the probe opened a database connection")

    monkeypatch.setitem(probe_module, "_connection", unexpected_connection)
    with pytest.raises(ValueError, match="isolated schema replay"):
        probe_module["run_probe"]()


@pytest.mark.parametrize("collision_index", range(5))
def test_schema_replay_rejects_existing_project_resources_before_start(collision_index):
    outputs = ["", "", "", "", ""]
    outputs[collision_index] = (
        "example_schema-bootstrap-data\n" if collision_index == 3
        else "example-database-1\n" if collision_index == 4
        else "existing-resource\n"
    )
    commands = []

    def fake_run(command, **_kwargs):
        index = len(commands)
        commands.append(command)
        return replay_module["subprocess"].CompletedProcess(command, 0, outputs[index], "")

    with pytest.raises(RuntimeError, match="already"):
        ensure_disposable_project_unused("example", command_runner=fake_run)
    assert not any("down" in command or "up" in command for command in commands)


def test_schema_replay_accepts_an_unused_project():
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        return replay_module["subprocess"].CompletedProcess(command, 0, "unrelated\n" if len(commands) > 3 else "", "")

    ensure_disposable_project_unused("example", command_runner=fake_run)
    assert len(commands) == 5
