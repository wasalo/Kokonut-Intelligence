#!/usr/bin/env bash
# ============================================================
# backup.sh — Backup PostgreSQL and ClickHouse databases
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "=== Kokonut Intelligence Platform — Backup ==="
echo "Timestamp: $TIMESTAMP"
echo ""

# Source environment
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
PG_BACKUP="$BACKUP_DIR/postgres_$TIMESTAMP.sql.gz"
docker exec kokonut-intelligence-database-1 \
    pg_dump -U kokonut -d kokonut_intelligence \
    --clean --if-exists --no-owner --no-privileges \
    | gzip > "$PG_BACKUP"

echo "  PostgreSQL backup: $PG_BACKUP"

# Backup ClickHouse (if running)
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps clickhouse | grep -q "Up"; then
    echo "Backing up ClickHouse..."
    CH_BACKUP="$BACKUP_DIR/clickhouse_$TIMESTAMP.sql.gz"
    docker exec kokonut-intelligence-clickhouse-1 \
        clickhouse-client --query "SHOW TABLES" \
        > /dev/null 2>&1 && \
    docker exec kokonut-intelligence-clickhouse-1 \
        clickhouse-client --multiquery \
        --query "SELECT * FROM system.tables" \
        | gzip > "$CH_BACKUP" || true
    echo "  ClickHouse backup: $CH_BACKUP"
fi

# Cleanup old backups (keep last 30 days)
echo ""
echo "Cleaning up backups older than 30 days..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete 2>/dev/null || true

echo ""
echo "=== Backup Complete ==="
ls -lh "$BACKUP_DIR"/*_$TIMESTAMP* 2>/dev/null || true
