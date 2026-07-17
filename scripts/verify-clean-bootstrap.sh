#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
DB_SERVICE="${DB_SERVICE:-database}"
DB_NAME="kokonut_bootstrap_${$}"

cleanup() {
    docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
        psql -X -U kokonut -d postgres -v ON_ERROR_STOP=1 \
        -c "DROP DATABASE IF EXISTS \"$DB_NAME\"" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
    psql -X -U kokonut -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"$DB_NAME\""

PG_DB="$DB_NAME" python3 -m services.migration migrate --schemas-only
