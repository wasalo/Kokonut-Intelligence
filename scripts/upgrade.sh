#!/usr/bin/env bash
# Apply a checked-out Kokonut Intelligence release.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
UPGRADE_OPERATOR="${KOKONUT_OPERATOR:-$(id -un)}"
TARGET_VERSION="$(tr -d '[:space:]' < "$PROJECT_DIR/VERSION")"
TARGET_SHA="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
PLAN_ONLY=false
CONFIRM=false
SKIP_BACKUP=false
SKIP_REFERENCE_SEEDS=false
SKIP_METRICS=false
CHECKPOINT=""
UPGRADE_ROW_CREATED=false

usage() {
    cat <<'EOF'
Usage: scripts/upgrade.sh [options]

Options:
  --plan                    Validate and show pending migrations only
  --yes                     Confirm the upgrade after the plan is displayed
  --skip-backup --confirm-risk
                            Skip the checkpoint (unsafe and explicit)
  --skip-reference-seeds   Skip curated reference seed application
  --skip-metrics            Do not recompute metrics
  --checkpoint ID           Use this checkpoint identifier
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --plan) PLAN_ONLY=true; shift ;;
        --yes) CONFIRM=true; shift ;;
        --skip-backup)
            if [ "${2:-}" != "--confirm-risk" ]; then
                echo "--skip-backup requires --confirm-risk" >&2
                exit 2
            fi
            SKIP_BACKUP=true; shift 2 ;;
        --skip-reference-seeds) SKIP_REFERENCE_SEEDS=true; shift ;;
        --skip-metrics) SKIP_METRICS=true; shift ;;
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

if [ -f "$PROJECT_DIR/.env.sops" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/load-secrets.sh"
elif [ "${KOKONUT_ALLOW_PLAINTEXT_ENV:-}" != "true" ]; then
    echo "Encrypted .env.sops is required; set KOKONUT_ALLOW_PLAINTEXT_ENV=true for local fallback." >&2
    exit 1
fi

compose() {
    COMPOSE_FILE="$COMPOSE_FILE" docker compose --project-directory "$PROJECT_DIR" "$@"
}

db_query() {
    compose exec -T database psql -X -U kokonut -d kokonut_intelligence \
        -v ON_ERROR_STOP=1 -A -t "$@"
}

record_upgrade() {
    local status="$1"
    local backup_id="${2:-}"
    local failure_reason="${3:-}"
    db_query \
        -v target_version="$TARGET_VERSION" \
        -v target_sha="$TARGET_SHA" \
        -v operator="$UPGRADE_OPERATOR" \
        -v backup_id="$backup_id" \
        -v status="$status" \
        -v failure_reason="$failure_reason" \
        -c "INSERT INTO platform_upgrade
            (target_version, target_git_sha, backup_id, status, operator, failure_reason)
            VALUES (:'target_version', :'target_sha', NULLIF(:'backup_id', ''), :'status', :'operator', NULLIF(:'failure_reason', ''))"
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

if [ "$SKIP_BACKUP" = "true" ]; then
    echo "WARNING: checkpoint backup skipped by explicit operator request."
else
    if [ -n "$CHECKPOINT" ]; then
        export BACKUP_ID="$CHECKPOINT"
    else
        CHECKPOINT="checkpoint-${TARGET_VERSION}-$(date -u +%Y%m%dT%H%M%SZ)"
        export BACKUP_ID="$CHECKPOINT"
    fi
    "$SCRIPT_DIR/backup.sh"
fi

if [ -f "$PROJECT_DIR/schemas/postgres/351_platform_upgrade.sql" ]; then
    # The history table is created by the migration itself on first upgrade.
    if db_query -c "SELECT to_regclass('public.platform_upgrade')" | grep -q platform_upgrade; then
        record_upgrade started "$CHECKPOINT"
        UPGRADE_ROW_CREATED=true
    fi
fi

on_error() {
    local exit_code="$1"
    if [ "$UPGRADE_ROW_CREATED" = "true" ]; then
        record_upgrade failed "$CHECKPOINT" "upgrade command failed with exit code $exit_code" || true
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
    record_upgrade started "$CHECKPOINT"
    UPGRADE_ROW_CREATED=true
fi

if [ "$SKIP_REFERENCE_SEEDS" != "true" ]; then
    echo "Applying idempotent reference setup..."
    KOKONUT_RUN_CURATED_SEEDS=true "$SCRIPT_DIR/seed.sh" --reference-only
fi

if [ "$SKIP_METRICS" != "true" ]; then
    echo "Metric recomputation remains operator-controlled; skipping by default." 
fi

echo "Restarting services in the Compose maintenance window..."
compose up -d --no-build

VERIFY_CMD="${UPGRADE_VERIFY_CMD:-$SCRIPT_DIR/health-check.sh}"
for attempt in $(seq 1 30); do
    if "$VERIFY_CMD" >/dev/null 2>&1; then
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "Post-upgrade health verification failed." >&2
        exit 1
    fi
    sleep 10
done

"$SCRIPT_DIR/verify-platform.sh"

if db_query -c "SELECT to_regclass('public.platform_upgrade')" | grep -q platform_upgrade; then
    db_query -v target_version="$TARGET_VERSION" -v target_sha="$TARGET_SHA" -v backup_id="$CHECKPOINT" \
        -c "UPDATE platform_upgrade SET status = 'succeeded', completed_at = NOW(),
            target_version = :'target_version', target_git_sha = :'target_sha'
            WHERE id = (SELECT id FROM platform_upgrade WHERE status = 'started' ORDER BY started_at DESC LIMIT 1)"
fi

trap - ERR
echo "Upgrade complete: $TARGET_VERSION"
