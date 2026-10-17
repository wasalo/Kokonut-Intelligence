#!/usr/bin/env bash
# Verify checkpoint manifest and encrypted backup artifacts.
set -euo pipefail

CHECKPOINT="${1:-}"
if [ -z "$CHECKPOINT" ] || [ ! -f "$CHECKPOINT/manifest.json" ]; then
    echo "Usage: $0 <checkpoint-directory>" >&2
    exit 2
fi

PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib${PYTHONPATH:+:$PYTHONPATH}" python3 - "$CHECKPOINT" <<'PY'
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from backup_manifest import verify_manifest_signature

checkpoint = Path(sys.argv[1])
checkpoint_root = checkpoint.resolve()
manifest = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
if not isinstance(manifest, dict):
    raise SystemExit("Invalid checkpoint manifest")
try:
    verify_manifest_signature(manifest, os.environ.get("BACKUP_ENCRYPTION_KEY", ""))
except ValueError as error:
    raise SystemExit(str(error)) from error
records = manifest.get("files")
if not isinstance(records, list):
    raise SystemExit("Missing checkpoint file inventory")

listed_paths = set()
for item in records:
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        raise SystemExit("Invalid checkpoint file inventory entry")
    relative = Path(item["path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in item["path"] or item["path"] == "manifest.json":
        raise SystemExit(f"Unsafe checkpoint file path: {item['path']}")
    if item["path"] in listed_paths:
        raise SystemExit(f"Duplicate checkpoint file: {item['path']}")
    listed_paths.add(item["path"])
    path = checkpoint / relative
    if not path.resolve().is_relative_to(checkpoint_root):
        raise SystemExit(f"Checkpoint file escapes its directory: {item['path']}")
    if path.is_symlink():
        raise SystemExit(f"Checkpoint file must not be a symlink: {item['path']}")
    if not path.is_file():
        raise SystemExit(f"Missing checkpoint file: {item['path']}")
    if path.stat().st_size == 0:
        raise SystemExit(f"Empty checkpoint file: {item['path']}")
    if "size" in item and item["size"] != path.stat().st_size:
        raise SystemExit(f"Size mismatch: {item['path']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit(f"Checksum mismatch: {item['path']}")

disk_paths = {
    path.relative_to(checkpoint).as_posix()
    for path in checkpoint.rglob("*")
    if path.is_file() and path.name != "manifest.json"
}
if disk_paths != listed_paths:
    missing = sorted(disk_paths - listed_paths)
    absent = sorted(listed_paths - disk_paths)
    raise SystemExit(f"Checkpoint inventory mismatch: unlisted={missing}, missing={absent}")

providers = manifest.get("providers")
if providers is None:
    if "clickhouse/schema.sql.enc" not in listed_paths:
        raise SystemExit("Legacy checkpoint is missing its required ClickHouse schema archive")
else:
    if not isinstance(providers, dict):
        raise SystemExit("Invalid provider inventory")
    postgres = providers.get("postgres")
    clickhouse = providers.get("clickhouse")
    if not isinstance(postgres, dict) or postgres.get("included") is not True:
        raise SystemExit("Checkpoint must include PostgreSQL")
    databases = postgres.get("databases")
    if not isinstance(databases, list) or not databases or any(
        not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
        for name in databases
    ) or len(set(databases)) != len(databases):
        raise SystemExit("Invalid PostgreSQL database inventory")
    expected_postgres = {f"postgres/{name}.dump.enc" for name in databases}
    actual_postgres = {name for name in listed_paths if name.startswith("postgres/")}
    if actual_postgres != expected_postgres:
        raise SystemExit("PostgreSQL archives do not match the provider inventory")
    if not isinstance(clickhouse, dict) or not isinstance(clickhouse.get("included"), bool):
        raise SystemExit("Invalid ClickHouse provider inventory")
    clickhouse_paths = {name for name in listed_paths if name.startswith("clickhouse/")}
    if clickhouse["included"]:
        database = clickhouse.get("database")
        if not isinstance(database, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
            raise SystemExit("Invalid ClickHouse database inventory")
        if "clickhouse/schema.sql.enc" not in clickhouse_paths:
            raise SystemExit("ClickHouse provider is included but its schema archive is missing")
        if any(
            not re.fullmatch(r"clickhouse/data/[A-Za-z_][A-Za-z0-9_]*\.csv\.enc", name)
            for name in clickhouse_paths - {"clickhouse/schema.sql.enc"}
        ):
            raise SystemExit("Invalid ClickHouse data archive path")
    elif clickhouse.get("database") is not None or clickhouse_paths:
        raise SystemExit("ClickHouse artifacts exist while provider is marked excluded")
PY

echo "Backup checkpoint is valid: $CHECKPOINT"
