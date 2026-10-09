#!/usr/bin/env bash
# ============================================================
# lib/common.sh — shared bootstrap for Kokonut shell scripts
#
# Source after setting SCRIPT_DIR and PROJECT_DIR:
#     source "$SCRIPT_DIR/lib/common.sh"
#
# Provides:
#   source_secrets [strict|warn]  — load .env.sops (or plaintext .env fallback)
#   compose                       — docker compose with the project directory
#   wait_for_postgres             — poll pg_isready via compose exec
#   psql_exec <file>              — run a SQL file with ON_ERROR_STOP=1
# ============================================================

set -euo pipefail

# Allow this library to be sourced more than once.
if [ -n "${KOKONUT_COMMON_LIB_SOURCED:-}" ]; then
    return 0 2>/dev/null || exit 0
fi
KOKONUT_COMMON_LIB_SOURCED=1

COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
DB_SERVICE="${DB_SERVICE:-database}"
DB_WAIT_ATTEMPTS="${DB_WAIT_ATTEMPTS:-60}"

# Source secrets (SOPS encrypted .env.sops, or plaintext .env fallback).
# Mode "strict" (default) exits on missing secrets; "warn" only warns.
source_secrets() {
    local mode="${1:-strict}"
    if [ -f "$PROJECT_DIR/.env.sops" ]; then
        # shellcheck disable=SC1091
        source "$SCRIPT_DIR/load-secrets.sh"
    elif [ -f "$PROJECT_DIR/.env" ]; then
        if [ "${KOKONUT_ALLOW_PLAINTEXT_ENV:-}" = "true" ]; then
            set -a
            # shellcheck disable=SC1091
            source "$PROJECT_DIR/.env"
            set +a
        else
            if [ "$mode" = "warn" ]; then
                echo "WARNING: No .env.sops found. Set KOKONUT_ALLOW_PLAINTEXT_ENV=true to use plaintext .env." >&2
            else
                echo "ERROR: No .env.sops found. Set KOKONUT_ALLOW_PLAINTEXT_ENV=true to use plaintext .env." >&2
                exit 1
            fi
        fi
    else
        if [ "$mode" = "warn" ]; then
            echo "WARNING: No secrets found. Expected .env.sops or .env." >&2
        else
            echo "ERROR: No secrets found. Expected .env.sops or .env." >&2
            exit 1
        fi
    fi
}

compose() {
    COMPOSE_FILE="$COMPOSE_FILE" docker compose --project-directory "$PROJECT_DIR" "$@"
}

wait_for_postgres() {
    local attempt=1
    until docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" pg_isready -U kokonut -d kokonut_intelligence > /dev/null 2>&1; do
        if [ "$attempt" -ge "$DB_WAIT_ATTEMPTS" ]; then
            echo "ERROR: PostgreSQL service '$DB_SERVICE' is not ready after $((DB_WAIT_ATTEMPTS * 2)) seconds."
            return 1
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
}

# Run a SQL file against PostgreSQL with ON_ERROR_STOP=1.
psql_exec() {
    local sql_file="$1"
    docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
        psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$sql_file"
}

# Apply a seed file, optionally setting the pilot seed context first
# (used by seed-pilot.sh to tag rows with kokonut.seed_context = 'pilot').
seed_apply() {
    local seed_file="$1"
    local context="${2:-}"
    if [ -n "$context" ]; then
        local tmp
        tmp=$(mktemp)
        printf "SET kokonut.seed_context = '%s';\n" "$context" > "$tmp"
        cat "$seed_file" >> "$tmp"
        docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
            psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$tmp"
        rm -f "$tmp"
    else
        psql_exec "$seed_file"
    fi
}

