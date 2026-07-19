#!/usr/bin/env bash
# Run the full host-side test suite against the local Compose databases.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
if [ -z "${PYTHON_BIN:-}" ] && [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

COMPOSE=(
    docker compose
    -f "$PROJECT_DIR/docker-compose.yml"
    -f "$PROJECT_DIR/docker-compose.ci.yml"
)

echo "=== Starting local test databases ==="
"${COMPOSE[@]}" up -d database clickhouse

for _ in $(seq 1 30); do
    if "${COMPOSE[@]}" exec -T database pg_isready -U kokonut -d kokonut_intelligence >/dev/null 2>&1 \
        && "${COMPOSE[@]}" exec -T clickhouse sh -c 'clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --query "SELECT 1"' >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

if ! "${COMPOSE[@]}" exec -T database pg_isready -U kokonut -d kokonut_intelligence >/dev/null 2>&1; then
    echo "ERROR: PostgreSQL did not become ready on localhost:5432" >&2
    exit 1
fi

if ! "${COMPOSE[@]}" exec -T clickhouse sh -c 'clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --query "SELECT 1"' >/dev/null 2>&1; then
    echo "ERROR: ClickHouse did not become ready on localhost:8123" >&2
    exit 1
fi

echo "=== Running strict local test suite ==="
PG_HOST=127.0.0.1 \
PG_PORT=5432 \
CH_HOST=127.0.0.1 \
CH_PORT=8123 \
CI_STRICT_DB=1 \
PYTHON_BIN="$PYTHON_BIN" \
    "$SCRIPT_DIR/verify-full-test-suite.sh"
