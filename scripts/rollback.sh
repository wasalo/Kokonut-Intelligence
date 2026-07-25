#!/usr/bin/env bash
# Restore a named checkpoint after an operator-confirmed failed upgrade.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CHECKPOINT=""
CONFIRM=false

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

echo "Stopping application services..."
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}" \
    docker compose --project-directory "$PROJECT_DIR" stop gateway grpc directus metabase caddy

"$SCRIPT_DIR/restore.sh" --checkpoint "$CHECKPOINT" --confirm

echo "Restarting services..."
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}" \
    docker compose --project-directory "$PROJECT_DIR" up -d

VERIFY_CMD="${ROLLBACK_VERIFY_CMD:-$SCRIPT_DIR/health-check.sh}"
for attempt in $(seq 1 30); do
    if "$VERIFY_CMD" >/dev/null 2>&1; then
        echo "Rollback complete: $CHECKPOINT"
        exit 0
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "Rollback verification failed; manual intervention required." >&2
        exit 1
    fi
    sleep 10
done
