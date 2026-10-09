#!/usr/bin/env bash
# Create a verified, encrypted upgrade checkpoint.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
BACKUP_ROOT="${BACKUP_DIR:-$PROJECT_DIR/backups}"
BACKUP_ID="${BACKUP_ID:-checkpoint-$(date -u +%Y%m%dT%H%M%SZ)}"
CHECKPOINT="$BACKUP_ROOT/$BACKUP_ID"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-database}"
CH_SERVICE="${CH_SERVICE:-clickhouse}"
CLICKHOUSE_DATABASE="${BACKUP_CLICKHOUSE_DATABASE:-kokonut_analytics}"
PG_DATABASES="${BACKUP_POSTGRES_DATABASES:-kokonut_intelligence}"

usage() {
    printf 'Usage: %s [--backup-id ID] [--output-dir DIR]\n' "$0"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --backup-id) BACKUP_ID="$2"; CHECKPOINT="$BACKUP_ROOT/$BACKUP_ID"; shift 2 ;;
        --output-dir) BACKUP_ROOT="$2"; CHECKPOINT="$BACKUP_ROOT/$BACKUP_ID"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! "$BACKUP_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "Invalid backup ID" >&2
    exit 2
fi

source_secrets strict

: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set}"

if [[ ! "$CLICKHOUSE_DATABASE" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "Invalid ClickHouse database name: $CLICKHOUSE_DATABASE" >&2
    exit 2
fi


checksum() {
    shasum -a 256 "$1" | cut -d ' ' -f 1
}

umask 077
mkdir -p "$CHECKPOINT/postgres" "$CHECKPOINT/clickhouse/data"
chmod 700 "$CHECKPOINT"

echo "Creating checkpoint: $BACKUP_ID"

for database in $PG_DATABASES; do
    if [[ ! "$database" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "Invalid PostgreSQL database name: $database" >&2
        exit 2
    fi
    output="$CHECKPOINT/postgres/${database}.dump.enc"
    temporary="$output.tmp"
    compose exec -T "$DB_SERVICE" pg_dump \
        -U kokonut -d "$database" --format=custom --no-owner --no-privileges \
        | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY > "$temporary"
    mv "$temporary" "$output"
    chmod 600 "$output"
done

running_services="$(compose ps --status running --services)"
if ! printf '%s\n' "$running_services" | grep -Fxq "$CH_SERVICE"; then
    echo "ClickHouse service is not running; refusing an incomplete checkpoint." >&2
    exit 1
fi

schema_tmp="$CHECKPOINT/clickhouse/schema.sql"
tables_tmp="$CHECKPOINT/clickhouse/tables.txt"
compose exec -T "$CH_SERVICE" clickhouse-client \
    --user kokonut --password "$CLICKHOUSE_PASSWORD" \
    --query "SELECT name FROM system.tables WHERE database = '$CLICKHOUSE_DATABASE' AND engine NOT IN ('View', 'MaterializedView') ORDER BY name FORMAT TSVRaw" \
    > "$tables_tmp"

: > "$schema_tmp"
while IFS= read -r table; do
    [ -z "$table" ] && continue
    if [[ ! "$table" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "Unexpected ClickHouse table name: $table" >&2
        exit 1
    fi
    compose exec -T "$CH_SERVICE" clickhouse-client \
        --user kokonut --password "$CLICKHOUSE_PASSWORD" \
        --format TSVRaw \
        --query "SHOW CREATE TABLE \`$CLICKHOUSE_DATABASE\`.\`$table\`" >> "$schema_tmp"
    printf '\n;\n' >> "$schema_tmp"
    data_output="$CHECKPOINT/clickhouse/data/${table}.csv.enc"
    data_temporary="$data_output.tmp"
    compose exec -T "$CH_SERVICE" clickhouse-client \
        --user kokonut --password "$CLICKHOUSE_PASSWORD" \
        --query "SELECT * FROM \`$CLICKHOUSE_DATABASE\`.\`$table\` FORMAT CSVWithNames" \
        | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY > "$data_temporary"
    mv "$data_temporary" "$data_output"
    chmod 600 "$data_output"
done < "$tables_tmp"

openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY \
    -in "$schema_tmp" -out "$CHECKPOINT/clickhouse/schema.sql.enc"
rm -f "$schema_tmp" "$tables_tmp"

git_sha="$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || printf 'unknown')"
version="$(tr -d '[:space:]' < "$PROJECT_DIR/VERSION" 2>/dev/null || printf 'unknown')"
python3 - "$CHECKPOINT" "$BACKUP_ID" "$git_sha" "$version" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

checkpoint, backup_id, git_sha, version = map(Path, sys.argv[1:])
files = []
for path in sorted(checkpoint.rglob("*")):
    if not path.is_file() or path.name == "manifest.json":
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    files.append({"path": str(path.relative_to(checkpoint)), "sha256": digest, "size": path.stat().st_size})

manifest = {
    "backup_id": str(backup_id),
    "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    "platform_version": str(version),
    "git_sha": str(git_sha),
    "files": files,
}
(checkpoint / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY

"$SCRIPT_DIR/verify-backup.sh" "$CHECKPOINT"
echo "Checkpoint verified: $CHECKPOINT"
