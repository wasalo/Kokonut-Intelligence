#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${KOKONUT_BOOTSTRAP_COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
if [[ "$COMPOSE_FILE" != /* ]]; then
    COMPOSE_FILE="$PROJECT_DIR/$COMPOSE_FILE"
fi
COMPOSE_PROJECT="${KOKONUT_BOOTSTRAP_COMPOSE_PROJECT:-}"
DB_SERVICE="${DB_SERVICE:-database}"
DB_NAME="kokonut_bootstrap_${$}"
START_DATABASE="${KOKONUT_BOOTSTRAP_START_DATABASE:-false}"
REMOVE_PROJECT="${KOKONUT_BOOTSTRAP_REMOVE_PROJECT:-false}"

if [[ -n "$COMPOSE_PROJECT" && ! "$COMPOSE_PROJECT" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
    echo "Invalid bootstrap Compose project name: $COMPOSE_PROJECT" >&2
    exit 2
fi
if [[ -z "$COMPOSE_PROJECT" && "$COMPOSE_FILE" != "$PROJECT_DIR/docker-compose.yml" ]]; then
    echo "A custom bootstrap Compose file requires KOKONUT_BOOTSTRAP_COMPOSE_PROJECT" >&2
    exit 2
fi

COMPOSE_BASE=(docker compose)
if [[ -n "$COMPOSE_PROJECT" ]]; then
    COMPOSE_BASE+=(--project-directory "$PROJECT_DIR" --env-file /dev/null -p "$COMPOSE_PROJECT")
fi
COMPOSE_BASE+=(-f "$COMPOSE_FILE")

compose() {
    "${COMPOSE_BASE[@]}" "$@"
}

if [[ -n "$COMPOSE_PROJECT" ]]; then
    MIGRATION_ARGS=(--compose-project "$COMPOSE_PROJECT" --compose-file "$COMPOSE_FILE")
else
    MIGRATION_ARGS=()
fi

cleanup() {
    compose exec -T "$DB_SERVICE" \
        psql -X -U kokonut -d postgres -v ON_ERROR_STOP=1 \
        -c "DROP DATABASE IF EXISTS \"$DB_NAME\"" >/dev/null 2>&1 || true
    if [[ "$REMOVE_PROJECT" == "true" && -n "$COMPOSE_PROJECT" ]]; then
        compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

if [[ "$START_DATABASE" == "true" ]]; then
    if [[ -z "$COMPOSE_PROJECT" ]]; then
        echo "Starting the database requires KOKONUT_BOOTSTRAP_COMPOSE_PROJECT" >&2
        exit 2
    fi
    compose up -d --wait "$DB_SERVICE"
fi

# These optional deployment identities are referenced by REVOKE statements in
# signed-worker migrations. Fresh schema replay must have the role names even
# when the deployment has not enabled their logins yet. Keep placeholders
# locked and leave any already-provisioned role attributes untouched.
compose exec -T "$DB_SERVICE" \
    psql -X -U kokonut -d postgres -v ON_ERROR_STOP=1 <<'SQL'
DO $bootstrap_roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER '
            || 'NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_login') THEN
        EXECUTE 'CREATE ROLE kokonut_worker_login NOLOGIN NOINHERIT NOSUPERUSER '
            || 'NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
END;
$bootstrap_roles$;
SQL

compose exec -T "$DB_SERVICE" \
    psql -X -U kokonut -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"$DB_NAME\""

PG_DB="$DB_NAME" python3 -m services.migration migrate --schemas-only "${MIGRATION_ARGS[@]}"
