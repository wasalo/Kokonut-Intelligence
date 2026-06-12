#!/usr/bin/env bash
# ============================================================
# health-check.sh — Verify all platform services are healthy
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source environment
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
else
    echo "WARNING: .env file not found. Using defaults."
fi

# Service endpoints
DIRECTUS_URL="${DIRECTUS_URL:-http://localhost:8055}"
METABASE_URL="${METABASE_URL:-http://localhost:3001}"
CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://localhost:8123}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_DB="${PG_DB:-kokonut_intelligence}"
PG_USER="${PG_USER:-kokonut}"
PG_PASSWORD="${PG_PASSWORD:-dev-kokonut-postgres-2026}"

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  ✓ $name"
        ((PASS++))
    else
        echo "  ✗ $name"
        ((FAIL++))
    fi
}

echo "=== Kokonut Intelligence Platform — Health Check ==="
echo ""

# PostgreSQL
echo "PostgreSQL ($PG_HOST:$PG_PORT):"
check "Connection" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT 1'"
check "location table" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM location'"
check "forecast_scenario table" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM forecast_scenario'"
check "report_snapshot table" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM report_snapshot'"
echo ""

# Directus
echo "Directus ($DIRECTUS_URL):"
check "Server ping" "curl -sf ${DIRECTUS_URL}/server/ping"
check "Health endpoint" "curl -sf ${DIRECTUS_URL}/server/health"
echo ""

# ClickHouse
echo "ClickHouse ($CLICKHOUSE_URL):"
check "HTTP ping" "curl -sf '${CLICKHOUSE_URL}/ping'"
check "Query" "curl -sf '${CLICKHOUSE_URL}/?query=SELECT%201'"
echo ""

# Metabase
echo "Metabase ($METABASE_URL):"
check "Health endpoint" "curl -sf ${METABASE_URL}/api/health"
echo ""

# Docker containers
echo "Docker containers:"
check "Database container" "docker ps --format '{{.Names}}' | grep -q 'database'"
check "Directus container" "docker ps --format '{{.Names}}' | grep -q 'directus'"
check "ClickHouse container" "docker ps --format '{{.Names}}' | grep -q 'clickhouse'"
check "Metabase container" "docker ps --format '{{.Names}}' | grep -q 'metabase'"
echo ""

# Summary
echo "=== Results ==="
echo "  Pass: $PASS"
echo "  Fail: $FAIL"

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "  All systems healthy ✓"
    exit 0
else
    echo ""
    echo "  $FAIL check(s) failed — review services above"
    exit 1
fi
