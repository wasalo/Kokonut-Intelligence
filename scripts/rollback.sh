#!/usr/bin/env bash
# Restore a named checkpoint after an operator-confirmed failed upgrade.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
CHECKPOINT=""
CONFIRM=false
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
ROLLBACK_SERVICES="${ROLLBACK_SERVICES:-gateway grpc directus caddy}"
read -r -a ROLLBACK_SERVICE_ARGS <<< "$ROLLBACK_SERVICES"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --checkpoint) CHECKPOINT="$2"; shift 2 ;;
        --confirm) CONFIRM=true; shift ;;
        --help) echo "Usage: $0 --checkpoint DIR --confirm"; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ "$CONFIRM" != "true" ] || [ -z "$CHECKPOINT" ]; then
    echo "Refusing rollback without --checkpoint and --confirm." >&2
    exit 2
fi

source_secrets strict

db_query() {
    COMPOSE_FILE="$COMPOSE_FILE" docker compose --project-directory "$PROJECT_DIR" \
        exec -T database psql -X -U kokonut -d kokonut_intelligence \
        -v ON_ERROR_STOP=1 -A -t "$@"
}

echo "Stopping application services..."
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}" \
    docker compose --project-directory "$PROJECT_DIR" stop "${ROLLBACK_SERVICE_ARGS[@]}"

"$SCRIPT_DIR/restore.sh" --checkpoint "$CHECKPOINT" --confirm

echo "Restarting services..."
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}" \
    docker compose --project-directory "$PROJECT_DIR" up -d "${ROLLBACK_SERVICE_ARGS[@]}"

VERIFY_CMD="${ROLLBACK_VERIFY_CMD:-$SCRIPT_DIR/health-check.sh}"
for attempt in $(seq 1 30); do
    if "$VERIFY_CMD" >/dev/null 2>&1; then
        if db_query -c "SELECT to_regclass('public.platform_upgrade')" | grep -q platform_upgrade; then
            db_query -c "UPDATE platform_upgrade SET status = 'rolled_back', completed_at = NOW()
                WHERE id = (SELECT id FROM platform_upgrade WHERE status = 'failed'
                ORDER BY started_at DESC LIMIT 1)"
        fi
        echo "Rollback complete: $CHECKPOINT"
        exit 0
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "Rollback verification failed; manual intervention required." >&2
        exit 1
    fi
    sleep 10
done
