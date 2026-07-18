#!/usr/bin/env bash
# ============================================================
# backup.sh — Backup PostgreSQL and ClickHouse databases
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
DB_SERVICE="${DB_SERVICE:-database}"
CH_SERVICE="${CH_SERVICE:-clickhouse}"

umask 077
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

echo "=== Kokonut Intelligence Platform — Backup ==="
echo "Timestamp: $TIMESTAMP"
echo ""

# Source only encrypted secrets. A plaintext .env is deliberately rejected.
if [ -f "$PROJECT_DIR/.env.sops" ]; then
    source "$SCRIPT_DIR/load-secrets.sh"
elif [ -f "$PROJECT_DIR/.env" ]; then
    echo "Refusing to source plaintext $PROJECT_DIR/.env" >&2
    exit 1
fi

# Backups must never silently use an empty or known default credential.
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the environment or SOPS environment}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set in the environment or SOPS environment}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be set in the environment or SOPS environment}"

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
PG_BACKUP="$BACKUP_DIR/postgres_$TIMESTAMP.sql.gz.enc"
PG_TMP="$PG_BACKUP.tmp"
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
    pg_dump -U kokonut -d kokonut_intelligence \
    --clean --if-exists --no-owner --no-privileges \
    | gzip \
    | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY > "$PG_TMP"
mv "$PG_TMP" "$PG_BACKUP"
chmod 600 "$PG_BACKUP"

echo "  PostgreSQL backup: $PG_BACKUP"

# Backup ClickHouse when the service is running. A running service that cannot
# be authenticated or dumped is an error, not a successful partial backup.
RUNNING_SERVICES=$(docker compose -f "$COMPOSE_FILE" ps --status running --services)
if printf '%s\n' "$RUNNING_SERVICES" | grep -Fxq "$CH_SERVICE"; then
    docker compose -f "$COMPOSE_FILE" exec -T "$CH_SERVICE" \
        clickhouse-client --user kokonut --password "$CLICKHOUSE_PASSWORD" \
        --query "SELECT 1" > /dev/null
    echo "Backing up ClickHouse..."
    CH_BACKUP="$BACKUP_DIR/clickhouse_$TIMESTAMP.sql.gz.enc"
    CH_TMP="$CH_BACKUP.tmp"

    # Dump data from all user tables
    {
        echo "-- ClickHouse backup: $TIMESTAMP"
        echo "-- Schema and data for kokonut_analytics database"
        echo ""

        # List and dump each user table
        for TABLE in $(docker compose -f "$COMPOSE_FILE" exec -T "$CH_SERVICE" \
            clickhouse-client --user kokonut --password "$CLICKHOUSE_PASSWORD" \
            --query "SELECT name FROM system.tables WHERE database = 'kokonut_analytics' AND engine != 'MaterializedView' AND engine != 'View'"); do
            echo "-- Table: $TABLE"
            docker compose -f "$COMPOSE_FILE" exec -T "$CH_SERVICE" \
                clickhouse-client --user kokonut --password "$CLICKHOUSE_PASSWORD" \
                --query "SELECT * FROM kokonut_analytics.$TABLE FORMAT CSVWithNames"
            echo ""
        done
    } | gzip \
      | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY > "$CH_TMP"
    mv "$CH_TMP" "$CH_BACKUP"
    chmod 600 "$CH_BACKUP"

    echo "  ClickHouse backup: $CH_BACKUP"
fi

# Cleanup old backups (keep last 30 days)
echo ""
echo "Cleaning up backups older than 30 days..."
find "$BACKUP_DIR" -name "*.sql.gz.enc" -mtime +30 -delete

echo ""
echo "=== Backup Complete ==="
ls -lh "$BACKUP_DIR"/*_$TIMESTAMP*
