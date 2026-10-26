"""Regression coverage for partial progress in ARM64 schema replay evidence."""

import runpy
from pathlib import Path

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
