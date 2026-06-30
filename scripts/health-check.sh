#!/usr/bin/env bash
# ============================================================
# health-check.sh — Verify all platform services are healthy
#
# Usage:
#   ./scripts/health-check.sh              # Human-readable output
#   ./scripts/health-check.sh --json       # JSON output for monitoring
#   ./scripts/health-check.sh --alert      # Send alerts on failure
#   ./scripts/health-check.sh --json --alert  # Both
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse flags
ALERT=false
JSON_OUTPUT=false
for arg in "$@"; do
    case "$arg" in
        --alert) ALERT=true ;;
        --json)  JSON_OUTPUT=true ;;
    esac
done

# Source environment
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
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

# Alert config
ALERT_WEBHOOK_URL="${ALERT_WEBHOOK_URL:-}"
ALERT_SMTP_HOST="${ALERT_SMTP_HOST:-}"
ALERT_SMTP_PORT="${ALERT_SMTP_PORT:-587}"
ALERT_SMTP_USER="${ALERT_SMTP_USER:-}"
ALERT_SMTP_PASSWORD="${ALERT_SMTP_PASSWORD:-}"
ALERT_EMAIL_FROM="${ALERT_EMAIL_FROM:-alerts@kokonut.network}"
ALERT_EMAIL_TO="${ALERT_EMAIL_TO:-}"

# Disk threshold (percent)
DISK_THRESHOLD="${DISK_THRESHOLD:-90}"
# Memory threshold (percent)
MEM_THRESHOLD="${MEM_THRESHOLD:-90}"

PASS=0
FAIL=0
FAILURES=""

check() {
    local name="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        if [ "$JSON_OUTPUT" = "false" ]; then
            echo "  ✓ $name"
        fi
        PASS=$((PASS + 1))
    else
        if [ "$JSON_OUTPUT" = "false" ]; then
            echo "  ✗ $name"
        fi
        FAIL=$((FAIL + 1))
        FAILURES="${FAILURES}${name};"
    fi
}

# ── PostgreSQL ──
if [ "$JSON_OUTPUT" = "false" ]; then echo "PostgreSQL ($PG_HOST:$PG_PORT):"; fi
check "pg_connection" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT 1'"
check "pg_location_table" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM location'"
check "pg_forecast_table" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM forecast_scenario'"
check "pg_report_table" "PGPASSWORD='$PG_PASSWORD' psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM report_snapshot'"
if [ "$JSON_OUTPUT" = "false" ]; then echo ""; fi

# ── Directus ──
if [ "$JSON_OUTPUT" = "false" ]; then echo "Directus ($DIRECTUS_URL):"; fi
check "directus_ping" "curl -sf ${DIRECTUS_URL}/server/ping"
check "directus_health" "curl -sf ${DIRECTUS_URL}/server/health"
if [ "$JSON_OUTPUT" = "false" ]; then echo ""; fi

# ── ClickHouse ──
if [ "$JSON_OUTPUT" = "false" ]; then echo "ClickHouse ($CLICKHOUSE_URL):"; fi
check "clickhouse_ping" "curl -sf '${CLICKHOUSE_URL}/ping'"
check "clickhouse_query" "curl -sf '${CLICKHOUSE_URL}/?query=SELECT%201'"
if [ "$JSON_OUTPUT" = "false" ]; then echo ""; fi

# ── Metabase ──
if [ "$JSON_OUTPUT" = "false" ]; then echo "Metabase ($METABASE_URL):"; fi
check "metabase_health" "curl -sf ${METABASE_URL}/api/health"
if [ "$JSON_OUTPUT" = "false" ]; then echo ""; fi

# ── Docker containers ──
if [ "$JSON_OUTPUT" = "false" ]; then echo "Docker containers:"; fi
check "container_database" "docker ps --format '{{.Names}}' | grep -q 'database'"
check "container_directus" "docker ps --format '{{.Names}}' | grep -q 'directus'"
check "container_clickhouse" "docker ps --format '{{.Names}}' | grep -q 'clickhouse'"
check "container_metabase" "docker ps --format '{{.Names}}' | grep -q 'metabase'"

# Check for exited (crashed) containers
EXITED=$(docker ps -a --filter "status=exited" --filter "status=dead" --format '{{.Names}}' 2>/dev/null | head -5 || true)
if [ -n "$EXITED" ]; then
    check "containers_no_crashes" "false"
    FAILURES="${FAILURES}crashed_containers:${EXITED};"
else
    check "containers_no_crashes" "true"
fi
if [ "$JSON_OUTPUT" = "false" ]; then echo ""; fi

# ── Disk usage ──
if [ "$JSON_OUTPUT" = "false" ]; then echo "System resources:"; fi
DISK_PCT=$(df / 2>/dev/null | awk 'NR==2{gsub(/%/,""); print $5}' || echo "0")
if [ "$DISK_PCT" -ge "$DISK_THRESHOLD" ] 2>/dev/null; then
    check "disk_usage" "false"
    FAILURES="${FAILURES}disk_usage:${DISK_PCT}%;"
else
    check "disk_usage" "true"
fi
if [ "$JSON_OUTPUT" = "false" ]; then echo "  Disk: ${DISK_PCT}% (threshold: ${DISK_THRESHOLD}%)"; fi

# ── Memory usage ──
MEM_PCT=$(free 2>/dev/null | awk '/Mem:/{printf "%.0f", $3/$2*100}' || echo "0")
if [ "$MEM_PCT" -ge "$MEM_THRESHOLD" ] 2>/dev/null; then
    check "memory_usage" "false"
    FAILURES="${FAILURES}memory_usage:${MEM_PCT}%;"
else
    check "memory_usage" "true"
fi
if [ "$JSON_OUTPUT" = "false" ]; then echo "  Memory: ${MEM_PCT}% (threshold: ${MEM_THRESHOLD}%)"; fi
if [ "$JSON_OUTPUT" = "false" ]; then echo ""; fi

# ── Summary ──
HOSTNAME=$(hostname -f 2>/dev/null || hostname || echo "unknown")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ "$JSON_OUTPUT" = "true" ]; then
    echo "{\"hostname\":\"$HOSTNAME\",\"timestamp\":\"$TIMESTAMP\",\"pass\":$PASS,\"fail\":$FAIL,\"failures\":\"${FAILURES}\",\"disk_pct\":${DISK_PCT:-0},\"mem_pct\":${MEM_PCT:-0}}"
else
    echo "=== Results ==="
    echo "  Pass: $PASS"
    echo "  Fail: $FAIL"
    if [ $FAIL -eq 0 ]; then
        echo ""
        echo "  All systems healthy ✓"
    else
        echo ""
        echo "  $FAIL check(s) failed — review services above"
    fi
fi

# ── Alerting ──
if [ "$FAIL" -gt 0 ] && [ "$ALERT" = "true" ]; then
    ALERT_MSG="Kokonut Health Alert: $FAIL check(s) failed on $HOSTNAME at $TIMESTAMP. Failed: ${FAILURES}"

    # Webhook (Slack/Discord/Teams)
    if [ -n "$ALERT_WEBHOOK_URL" ]; then
        curl -sf -X POST "$ALERT_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"$ALERT_MSG\"}" > /dev/null 2>&1 || true
    fi

    # Email via SMTP (Python helper for portability)
    if [ -n "$ALERT_SMTP_HOST" ] && [ -n "$ALERT_EMAIL_TO" ]; then
        python3 -c "
import smtplib
from email.mime.text import MIMEText
import os
msg = MIMEText('''$ALERT_MSG''')
msg['Subject'] = 'Kokonut Health Alert — $HOSTNAME'
msg['From'] = os.environ.get('ALERT_EMAIL_FROM', 'alerts@kokonut.network')
msg['To'] = os.environ.get('ALERT_EMAIL_TO', '')
try:
    server = smtplib.SMTP(os.environ.get('ALERT_SMTP_HOST', ''), int(os.environ.get('ALERT_SMTP_PORT', '587')))
    server.starttls()
    user = os.environ.get('ALERT_SMTP_USER', '')
    pw = os.environ.get('ALERT_SMTP_PASSWORD', '')
    if user and pw:
        server.login(user, pw)
    server.send_message(msg)
    server.quit()
except Exception:
    pass
" 2>/dev/null || true
    fi
fi

if [ $FAIL -eq 0 ]; then
    exit 0
else
    exit 1
fi
