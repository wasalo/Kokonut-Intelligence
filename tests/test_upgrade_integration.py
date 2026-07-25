"""Disposable PostgreSQL/ClickHouse checkpoint integration coverage."""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.ci.yml")


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    command = ["docker", "compose"]
    for compose_file in COMPOSE_FILES:
        command.extend(["-f", compose_file])
    command.extend(args)
    return subprocess.run(command, cwd=ROOT, check=check, capture_output=True, text=True)


def _exec(service: str, *args: str, check: bool = True) -> None:
    _compose("exec", "-T", service, *args, check=check)


@pytest.mark.skipif(os.environ.get("CI_STRICT_DB") != "1", reason="no database available")
def test_checkpoint_restores_disposable_postgres_and_clickhouse():
    suffix = uuid.uuid4().hex[:10]
    pg_database = f"upgrade_restore_{suffix}"
    ch_database = f"upgrade_restore_{suffix}"
    backup_id = f"integration-{suffix}"
    checkpoint_root = ROOT / "backups" / "integration-tests"
    checkpoint = checkpoint_root / backup_id

    env = os.environ.copy()
    env.update({
        "COMPOSE_FILE": ":".join(COMPOSE_FILES),
        "BACKUP_DIR": str(checkpoint_root),
        "BACKUP_ID": backup_id,
        "BACKUP_POSTGRES_DATABASES": pg_database,
        "BACKUP_CLICKHOUSE_DATABASE": ch_database,
        "BACKUP_ENCRYPTION_KEY": os.environ.get("BACKUP_ENCRYPTION_KEY", "ci-backup-key"),
        "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", "ci-placeholder"),
        "CLICKHOUSE_PASSWORD": os.environ.get("CLICKHOUSE_PASSWORD", "ci-placeholder"),
        "KOKONUT_ALLOW_PLAINTEXT_ENV": "true",
    })

    try:
        _exec("database", "createdb", "-U", "kokonut", pg_database)
        _exec("database", "psql", "-U", "kokonut", "-d", pg_database, "-v", "ON_ERROR_STOP=1",
              "-c", "CREATE TABLE checkpoint_sentinel (value TEXT NOT NULL)",
              "-c", "INSERT INTO checkpoint_sentinel VALUES ('before-restore')")
        clickhouse_password = os.environ.get("CLICKHOUSE_PASSWORD", "ci-placeholder")
        _exec("clickhouse", "clickhouse-client", "--user", "kokonut", "--password", clickhouse_password,
              "--query", f"CREATE DATABASE {ch_database}")
        _exec("clickhouse", "clickhouse-client", "--user", "kokonut", "--password", clickhouse_password,
              "--query", f"CREATE TABLE {ch_database}.checkpoint_sentinel (value String) ENGINE = MergeTree ORDER BY value")
        _exec("clickhouse", "clickhouse-client", "--user", "kokonut", "--password", clickhouse_password,
              "--query", f"INSERT INTO {ch_database}.checkpoint_sentinel VALUES ('before-restore')")

        subprocess.run([str(ROOT / "scripts" / "backup.sh")], cwd=ROOT, env=env, check=True)

        _compose("exec", "-T", "database", "dropdb", "-U", "kokonut", pg_database)
        _exec("database", "createdb", "-U", "kokonut", pg_database)
        _exec("clickhouse", "clickhouse-client", "--user", "kokonut", "--password", clickhouse_password,
              "--query", f"DROP DATABASE {ch_database}")
        _exec("clickhouse", "clickhouse-client", "--user", "kokonut", "--password", clickhouse_password,
              "--query", f"CREATE DATABASE {ch_database}")

        env["ROLLBACK_SERVICES"] = "gateway grpc"
        env["ROLLBACK_VERIFY_CMD"] = "/bin/true"
        subprocess.run(
            [str(ROOT / "scripts" / "rollback.sh"), "--checkpoint", str(checkpoint), "--confirm"],
            cwd=ROOT,
            env=env,
            check=True,
        )

        _exec("database", "psql", "-U", "kokonut", "-d", pg_database, "-v", "ON_ERROR_STOP=1",
              "-c", "SELECT 1 FROM checkpoint_sentinel WHERE value = 'before-restore'")
        _exec("clickhouse", "clickhouse-client", "--user", "kokonut", "--password", clickhouse_password,
              "--query", f"SELECT 1 FROM {ch_database}.checkpoint_sentinel WHERE value = 'before-restore'")
    finally:
        _compose("exec", "-T", "database", "dropdb", "--if-exists", "-U", "kokonut", pg_database, check=False)
        _exec("clickhouse", "clickhouse-client", "--user", "kokonut", "--password", os.environ.get("CLICKHOUSE_PASSWORD", "ci-placeholder"),
              "--query", f"DROP DATABASE IF EXISTS {ch_database}", check=False)
        shutil.rmtree(checkpoint, ignore_errors=True)
