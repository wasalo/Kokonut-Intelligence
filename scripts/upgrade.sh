#!/usr/bin/env bash
# Apply a checked-out Kokonut Intelligence release.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
UPGRADE_OPERATOR="${KOKONUT_OPERATOR:-$(id -un)}"
TARGET_VERSION="$(tr -d '[:space:]' < "$PROJECT_DIR/VERSION")"
TARGET_SHA="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
export KOKONUT_GIT_SHA="$TARGET_SHA"
export KOKONUT_EXPECTED_VERSION="$TARGET_VERSION"
export KOKONUT_EXPECTED_GIT_SHA="$TARGET_SHA"
PLAN_ONLY=false
CONFIRM=false
SKIP_REFERENCE_SEEDS=false
CHECKPOINT=""
UPGRADE_ROW_CREATED=false
UPGRADE_ROW_ID=""

usage() {
    cat <<'EOF'
Usage: scripts/upgrade.sh [options]

Options:
  --plan                    Validate and show pending migrations only
  --yes                     Confirm the upgrade after the plan is displayed
  --skip-reference-seeds   Skip curated reference seed application
  --checkpoint ID           Use this checkpoint identifier
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --plan) PLAN_ONLY=true; shift ;;
        --yes) CONFIRM=true; shift ;;
        --skip-reference-seeds) SKIP_REFERENCE_SEEDS=true; shift ;;
        --checkpoint) CHECKPOINT="$2"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! "$TARGET_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
    echo "VERSION is not valid SemVer: $TARGET_VERSION" >&2
    exit 1
fi

if [ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]; then
    echo "Refusing upgrade with a dirty working tree." >&2
    exit 1
fi

source_secrets strict


db_query() {
    compose exec -T database psql -X -U kokonut -d kokonut_intelligence \
        -v ON_ERROR_STOP=1 -A -t "$@"
}

record_upgrade_started() {
    local backup_id="$1"
    db_query \
        -v target_version="$TARGET_VERSION" \
        -v target_sha="$TARGET_SHA" \
        -v operator="$UPGRADE_OPERATOR" \
        -v backup_id="$backup_id" \
        -c "INSERT INTO platform_upgrade
            (target_version, target_git_sha, backup_id, status, operator, failure_reason)
            VALUES (:'target_version', :'target_sha', NULLIF(:'backup_id', ''), 'started', :'operator', NULL)
            RETURNING id"
}

finish_upgrade() {
    local status="$1"
    local failure_reason="${2:-}"
    local updated_id
    updated_id="$(db_query \
        -v upgrade_id="$UPGRADE_ROW_ID" \
        -v status="$status" \
        -v failure_reason="$failure_reason" \
        -c "UPDATE platform_upgrade
            SET status = :'status', completed_at = NOW(),
                failure_reason = NULLIF(:'failure_reason', '')
            WHERE id = :'upgrade_id' AND status = 'started'
            RETURNING id")"
    if [ "$updated_id" != "$UPGRADE_ROW_ID" ]; then
        echo "Could not update the active platform upgrade record." >&2
        return 1
    fi
}

latest_version() {
    db_query -c "SELECT target_version || E'|' || target_git_sha
        FROM platform_upgrade WHERE status = 'succeeded'
        ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1" 2>/dev/null || true
}

echo "Target release: $TARGET_VERSION ($TARGET_SHA)"

if ! compose ps --status running database >/dev/null 2>&1; then
    echo "Database service is not running; start Compose before upgrading." >&2
    exit 1
fi

if [ "$PLAN_ONLY" = "true" ]; then
    python3 -m services.migration validate
    python3 -m services.migration plan
    exit 0
fi

echo "Checking current platform release..."
CURRENT="$(latest_version)"
if [ -n "$CURRENT" ]; then
    echo "Current release: $CURRENT"
fi

echo "Validating migration sources..."
python3 -m services.migration validate
echo "Pending migration plan:"
python3 -m services.migration plan

if [ "$CONFIRM" != "true" ]; then
    echo "Re-run with --yes to apply this release." >&2
    exit 1
fi

if [ -n "$CHECKPOINT" ]; then
    export BACKUP_ID="$CHECKPOINT"
else
    CHECKPOINT="checkpoint-${TARGET_VERSION}-$(date -u +%Y%m%dT%H%M%SZ)"
    export BACKUP_ID="$CHECKPOINT"
fi
"$SCRIPT_DIR/backup.sh"

if [ -f "$PROJECT_DIR/schemas/postgres/351_platform_upgrade.sql" ]; then
    # The history table is created by the migration itself on first upgrade.
    if db_query -c "SELECT to_regclass('public.platform_upgrade')" | grep -q platform_upgrade; then
        UPGRADE_ROW_ID="$(record_upgrade_started "$CHECKPOINT")"
        UPGRADE_ROW_CREATED=true
    fi
fi

on_error() {
    local exit_code="$1"
    if [ "$UPGRADE_ROW_CREATED" = "false" ] && \
        db_query -c "SELECT to_regclass('public.platform_upgrade')" | grep -q platform_upgrade; then
        # The migration may have created the history table before a later
        # migration failed on a first-time upgrade.
        if UPGRADE_ROW_ID="$(record_upgrade_started "$CHECKPOINT")"; then
            UPGRADE_ROW_CREATED=true
        fi
    fi
    if [ "$UPGRADE_ROW_CREATED" = "true" ]; then
        finish_upgrade failed "upgrade command failed with exit code $exit_code" || true
    fi
    echo "Upgrade failed; inspect logs and use rollback.sh with the checkpoint." >&2
    exit "$exit_code"
}
trap 'on_error $?' ERR

echo "Building target images..."
compose build
echo "Applying migrations..."
python3 -m services.migration migrate

if [ "$UPGRADE_ROW_CREATED" = "false" ] && db_query -c "SELECT to_regclass('public.platform_upgrade')" | grep -q platform_upgrade; then
    # The history table may itself be introduced by this first upgrade.
    UPGRADE_ROW_ID="$(record_upgrade_started "$CHECKPOINT")"
    UPGRADE_ROW_CREATED=true
fi

if [ "$SKIP_REFERENCE_SEEDS" != "true" ]; then
    echo "Applying idempotent reference setup..."
    KOKONUT_RUN_CURATED_SEEDS=true "$SCRIPT_DIR/seed.sh" --reference-only
fi

echo "Metric recomputation remains operator-controlled; skipping."

echo "Restarting services in the Compose maintenance window..."
compose up -d --no-build

VERIFY_CMD="${UPGRADE_VERIFY_CMD:-$SCRIPT_DIR/verify-upgrade.sh}"
for attempt in $(seq 1 30); do
    if "$VERIFY_CMD" >/dev/null 2>&1; then
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "Post-upgrade health verification failed." >&2
        on_error 1
    fi
    sleep 10
done

"$SCRIPT_DIR/verify-platform.sh"

if db_query -c "SELECT to_regclass('public.platform_upgrade')" | grep -q platform_upgrade; then
    if [ "$UPGRADE_ROW_CREATED" = "false" ]; then
        UPGRADE_ROW_ID="$(record_upgrade_started "$CHECKPOINT")"
        UPGRADE_ROW_CREATED=true
    fi
    finish_upgrade succeeded
fi

trap - ERR
echo "Upgrade complete: $TARGET_VERSION"
