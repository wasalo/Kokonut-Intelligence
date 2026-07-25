#!/usr/bin/env bash
# Restore an explicit encrypted upgrade checkpoint.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CHECKPOINT=""
CONFIRM=false
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-database}"
CH_SERVICE="${CH_SERVICE:-clickhouse}"
CLICKHOUSE_DATABASE="${BACKUP_CLICKHOUSE_DATABASE:-kokonut_analytics}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --checkpoint) CHECKPOINT="$2"; shift 2 ;;
        --confirm) CONFIRM=true; shift ;;
        --help) echo "Usage: $0 --checkpoint DIR --confirm"; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ "$CONFIRM" != "true" ] || [ -z "$CHECKPOINT" ]; then
    echo "Refusing restore without --checkpoint and --confirm." >&2
    exit 2
fi

if [ -f "$PROJECT_DIR/.env.sops" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/load-secrets.sh"
elif [ "${KOKONUT_ALLOW_PLAINTEXT_ENV:-}" != "true" ]; then
    echo "Encrypted .env.sops is required; set KOKONUT_ALLOW_PLAINTEXT_ENV=true for local fallback." >&2
    exit 1
fi

: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set}"

if [[ ! "$CLICKHOUSE_DATABASE" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "Invalid ClickHouse database name: $CLICKHOUSE_DATABASE" >&2
    exit 2
fi

compose() {
    COMPOSE_FILE="$COMPOSE_FILE" docker compose --project-directory "$PROJECT_DIR" "$@"
}

"$SCRIPT_DIR/verify-backup.sh" "$CHECKPOINT"

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

echo "Restore complete: $CHECKPOINT"
