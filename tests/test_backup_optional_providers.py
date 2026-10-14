"""Provider-aware backup and restore behavior with an isolated fake Compose CLI."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _isolated_scripts(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "scripts", project / "scripts")
    shutil.copy2(ROOT / "VERSION", project / "VERSION")
    (project / ".env").write_text(
        "BACKUP_ENCRYPTION_KEY=test-encryption-key\n"
        "POSTGRES_PASSWORD=test-postgres-password\n"
        "KOKONUT_FEATURE_CLICKHOUSE=false\n",
        encoding="utf-8",
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_path = tmp_path / "docker-calls.jsonl"
    docker = fake_bin / "docker"
    docker.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            with Path(os.environ["FAKE_DOCKER_LOG"]).open("a", encoding="utf-8") as log:
                log.write(json.dumps(args) + "\\n")

            if "ps" in args:
                print(os.environ.get("FAKE_COMPOSE_SERVICES", "database"))
                raise SystemExit(0)

            if "exec" not in args:
                raise SystemExit("unexpected fake docker command")
            command = args[args.index("exec") + 1:]
            command = [value for value in command if value != "-T"]
            operation = command[1] if len(command) > 1 else ""
            if operation == "pg_dump":
                sys.stdout.write("synthetic pg dump")
            elif operation == "pg_restore":
                sys.stdin.read()
            elif operation == "clickhouse-client":
                query = command[command.index("--query") + 1] if "--query" in command else ""
                if "SELECT name FROM system.tables" in query:
                    print("sentinel_table")
                elif query.startswith("SHOW CREATE TABLE"):
                    print("CREATE TABLE kokonut_analytics.sentinel_table (value String) ENGINE = MergeTree ORDER BY value")
                elif "FORMAT CSVWithNames" in query:
                    print("value")
                    print("sentinel")
                else:
                    sys.stdin.read()
            else:
                raise SystemExit(f"unexpected fake Compose operation: {operation}")
            """
        ),
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "COMPOSE_FILE": str(project / "compose.yml"),
            "BACKUP_DIR": str(tmp_path / "checkpoints"),
            "BACKUP_POSTGRES_DATABASES": "testdb",
            "BACKUP_ENCRYPTION_KEY": "test-encryption-key",
            "POSTGRES_PASSWORD": "test-postgres-password",
            "KOKONUT_ALLOW_PLAINTEXT_ENV": "true",
            "FAKE_COMPOSE_SERVICES": "database",
            "FAKE_DOCKER_LOG": str(log_path),
        }
    )
    return project, env


def _enable_clickhouse(project: Path) -> None:
    with (project / ".env").open("a", encoding="utf-8") as stream:
        stream.write("KOKONUT_FEATURE_CLICKHOUSE=true\n")


def _commands(log_path: str) -> list[list[str]]:
    path = Path(log_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _run(project: Path, env: dict[str, str], script: str, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(project / "scripts" / script), *arguments],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_postgres_only_checkpoint_does_not_require_clickhouse(tmp_path):
    project, env = _isolated_scripts(tmp_path)
    env.pop("KOKONUT_FEATURE_CLICKHOUSE", None)
    env.pop("CLICKHOUSE_PASSWORD", None)
    checkpoint = Path(env["BACKUP_DIR"]) / "postgres-only"

    backup = _run(project, env, "backup.sh", "--backup-id", "postgres-only")

    assert backup.returncode == 0, backup.stderr
    manifest = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["providers"] == {
        "postgres": {"included": True, "databases": ["testdb"]},
        "clickhouse": {"included": False, "database": None},
    }
    assert {item["path"] for item in manifest["files"]} == {"postgres/testdb.dump.enc"}
    assert not (checkpoint / "clickhouse").exists()

    preflight = _run(project, env, "restore.sh", "--checkpoint", str(checkpoint), "--preflight")
    assert preflight.returncode == 0, preflight.stderr
    restore = _run(project, env, "restore.sh", "--checkpoint", str(checkpoint), "--confirm")
    assert restore.returncode == 0, restore.stderr
    logged = " ".join(" ".join(command) for command in _commands(env["FAKE_DOCKER_LOG"]))
    assert "pg_dump" in logged and "pg_restore" in logged
    assert "clickhouse-client" not in logged


def test_enabled_clickhouse_must_be_running_before_backup_artifacts_are_created(tmp_path):
    project, env = _isolated_scripts(tmp_path)
    _enable_clickhouse(project)
    env["CLICKHOUSE_PASSWORD"] = "test-clickhouse-password"
    checkpoint = Path(env["BACKUP_DIR"]) / "needs-clickhouse"

    result = _run(project, env, "backup.sh", "--backup-id", "needs-clickhouse")

    assert result.returncode != 0
    assert "ClickHouse service 'clickhouse' is not running" in result.stderr
    assert not checkpoint.exists()
    assert not any("pg_dump" in command for command in _commands(env["FAKE_DOCKER_LOG"]))


def test_checkpoint_including_clickhouse_restores_its_encrypted_archives(tmp_path):
    project, env = _isolated_scripts(tmp_path)
    _enable_clickhouse(project)
    env.update(
        {
            "CLICKHOUSE_PASSWORD": "test-clickhouse-password",
            "FAKE_COMPOSE_SERVICES": "database\nclickhouse",
        }
    )
    checkpoint = Path(env["BACKUP_DIR"]) / "with-clickhouse"

    backup = _run(project, env, "backup.sh", "--backup-id", "with-clickhouse")

    assert backup.returncode == 0, backup.stderr
    manifest = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["providers"]["clickhouse"] == {"included": True, "database": "kokonut_analytics"}
    assert "clickhouse/schema.sql.enc" in {item["path"] for item in manifest["files"]}
    assert "clickhouse/data/sentinel_table.csv.enc" in {item["path"] for item in manifest["files"]}

    restore = _run(project, env, "restore.sh", "--checkpoint", str(checkpoint), "--confirm")
    assert restore.returncode == 0, restore.stderr
    assert any("clickhouse-client" in command for command in _commands(env["FAKE_DOCKER_LOG"]))

    manifest.pop("providers")
    (checkpoint / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    legacy_preflight = _run(project, env, "restore.sh", "--checkpoint", str(checkpoint), "--preflight")
    assert legacy_preflight.returncode == 0, legacy_preflight.stderr


def test_restore_preflights_clickhouse_before_postgres_restore(tmp_path):
    project, env = _isolated_scripts(tmp_path)
    _enable_clickhouse(project)
    env.update(
        {
            "CLICKHOUSE_PASSWORD": "test-clickhouse-password",
            "FAKE_COMPOSE_SERVICES": "database\nclickhouse",
        }
    )
    checkpoint = Path(env["BACKUP_DIR"]) / "clickhouse-required"
    backup = _run(project, env, "backup.sh", "--backup-id", "clickhouse-required")
    assert backup.returncode == 0, backup.stderr

    Path(env["FAKE_DOCKER_LOG"]).write_text("", encoding="utf-8")
    env["FAKE_COMPOSE_SERVICES"] = "database"
    restore = _run(project, env, "restore.sh", "--checkpoint", str(checkpoint), "--confirm")

    assert restore.returncode != 0
    assert "required by this checkpoint but is not running" in restore.stderr
    logged = " ".join(" ".join(command) for command in _commands(env["FAKE_DOCKER_LOG"]))
    assert "pg_restore" not in logged
    assert "clickhouse-client" not in logged


def test_rollback_preflights_restore_before_stopping_application_services():
    source = (ROOT / "scripts" / "rollback.sh").read_text(encoding="utf-8")

    assert source.index('restore.sh" --checkpoint "$CHECKPOINT" --preflight') < source.index(
        'stop "${ROLLBACK_SERVICE_ARGS[@]}"'
    )


def test_legacy_manifest_without_clickhouse_schema_is_rejected(tmp_path):
    artifact = tmp_path / "postgres" / "testdb.dump.enc"
    artifact.parent.mkdir()
    artifact.write_bytes(b"synthetic PostgreSQL archive")
    manifest = {
        "backup_id": "legacy-incomplete",
        "files": [
            {
                "path": "postgres/testdb.dump.enc",
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "size": artifact.stat().st_size,
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [str(ROOT / "scripts" / "verify-backup.sh"), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Legacy checkpoint is missing its required ClickHouse schema archive" in result.stderr
