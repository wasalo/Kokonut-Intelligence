#!/usr/bin/env bash
# Restore an explicit encrypted upgrade checkpoint.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
CHECKPOINT=""
CONFIRM=false
PREFLIGHT=false
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-database}"
CH_SERVICE="${CH_SERVICE:-clickhouse}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --checkpoint) CHECKPOINT="$2"; shift 2 ;;
        --confirm) CONFIRM=true; shift ;;
        --preflight) PREFLIGHT=true; shift ;;
        --help) echo "Usage: $0 --checkpoint DIR [--confirm | --preflight]"; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$CHECKPOINT" ] || { [ "$CONFIRM" != "true" ] && [ "$PREFLIGHT" != "true" ]; } || { [ "$CONFIRM" = "true" ] && [ "$PREFLIGHT" = "true" ]; }; then
    echo "Require --checkpoint and exactly one of --confirm or --preflight." >&2
    exit 2
fi

source_secrets strict

CLICKHOUSE_DATABASE="${BACKUP_CLICKHOUSE_DATABASE:-kokonut_analytics}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"

"$SCRIPT_DIR/verify-backup.sh" "$CHECKPOINT"

CLICKHOUSE_INCLUDED="$(python3 - "$CHECKPOINT" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads((Path(sys.argv[1]) / "manifest.json").read_text(encoding="utf-8"))
providers = manifest.get("providers")
if providers is None:
    print("true")
else:
    print("true" if providers["clickhouse"]["included"] else "false")
PY
)"

if [ "$CLICKHOUSE_INCLUDED" = "true" ]; then
    : "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set when restoring ClickHouse data}"
    if [[ ! "$CLICKHOUSE_DATABASE" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "Invalid ClickHouse database name: $CLICKHOUSE_DATABASE" >&2
        exit 2
    fi
fi

running_services="$(compose ps --status running --services)"
if ! printf '%s\n' "$running_services" | grep -Fxq "$DB_SERVICE"; then
    echo "PostgreSQL service '$DB_SERVICE' is not running; refusing restore." >&2
    exit 1
fi
if [ "$CLICKHOUSE_INCLUDED" = "true" ] && ! printf '%s\n' "$running_services" | grep -Fxq "$CH_SERVICE"; then
    echo "ClickHouse service '$CH_SERVICE' is required by this checkpoint but is not running." >&2
    exit 1
fi

if [ "$PREFLIGHT" = "true" ]; then
    echo "Restore preflight passed: $CHECKPOINT"
    exit 0
fi

for archive in "$CHECKPOINT"/postgres/*.dump.enc; do
    [ -e "$archive" ] || continue
    database="$(basename "$archive" .dump.enc)"
    temporary="$(mktemp)"
    trap 'rm -f "$temporary"' EXIT
    openssl enc -d -aes-256-cbc -pbkdf2 -in "$archive" \
        -out "$temporary" -pass env:BACKUP_ENCRYPTION_KEY
    compose exec -T "$DB_SERVICE" pg_restore \
        -U kokonut -d "$database" --clean --if-exists --no-owner --no-privileges < "$temporary"
    rm -f "$temporary"
    trap - EXIT
done

if [ "$CLICKHOUSE_INCLUDED" = "true" ]; then
    schema_tmp="$(mktemp)"
    trap 'rm -f "$schema_tmp"' EXIT
    openssl enc -d -aes-256-cbc -pbkdf2 \
        -in "$CHECKPOINT/clickhouse/schema.sql.enc" -out "$schema_tmp" \
        -pass env:BACKUP_ENCRYPTION_KEY
    compose exec -T "$CH_SERVICE" clickhouse-client \
        --user kokonut --password "$CLICKHOUSE_PASSWORD" --multiquery < "$schema_tmp"
    rm -f "$schema_tmp"
    trap - EXIT

    for archive in "$CHECKPOINT"/clickhouse/data/*.csv.enc; do
        [ -e "$archive" ] || continue
        table="$(basename "$archive" .csv.enc)"
        if [[ ! "$table" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            echo "Unexpected ClickHouse table name: $table" >&2
            exit 1
        fi
        temporary="$(mktemp)"
        trap 'rm -f "$temporary"' EXIT
        openssl enc -d -aes-256-cbc -pbkdf2 -in "$archive" \
            -out "$temporary" -pass env:BACKUP_ENCRYPTION_KEY
        compose exec -T "$CH_SERVICE" clickhouse-client \
            --user kokonut --password "$CLICKHOUSE_PASSWORD" \
            --query "INSERT INTO \`$CLICKHOUSE_DATABASE\`.\`$table\` FORMAT CSVWithNames" < "$temporary"
        rm -f "$temporary"
        trap - EXIT
    done
fi

echo "Restore complete: $CHECKPOINT"
