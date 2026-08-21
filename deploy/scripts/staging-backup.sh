#!/usr/bin/env bash
# Nightly staging backup for Kokonut Intelligence (cerberus host).
# Keeps the last 7 checkpoints; older ones are pruned.
# Cron: 30 3 * * *  /opt/ki-staging/deploy/scripts/staging-backup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGING_ROOT="${STAGING_ROOT:-/opt/ki-staging}"
BACKUP_ROOT="${BACKUP_DIR:-$STAGING_ROOT/backups}"
COMPOSE_PROJECT="ki-staging"
KEEP="${STAGING_BACKUP_KEEP:-7}"
export BACKUP_DIR="$BACKUP_ROOT"

log() { printf '[staging-backup] %s\n' "$*"; }

mkdir -p "$BACKUP_ROOT"
cd "$STAGING_ROOT"

log "checkpoint start $(date -u +%FT%TZ)"
BACKUP_ID="staging-$(date -u +%Y%m%dT%H%M%SZ)" \
    ./scripts/backup.sh

NEWEST="$(ls -1dt "$BACKUP_ROOT"/staging-* 2>/dev/null | head -1 || true)"
[ -n "$NEWEST" ] || { log "FATAL: no checkpoint directory created"; exit 1; }

# Verify the checkpoint is restorable before considering it a backup.
if [ -x "$SCRIPT_DIR/../../scripts/verify-backup.sh" ]; then
    log "verifying $NEWEST"
    ./scripts/verify-backup.sh "$NEWEST"
fi

# Prune old checkpoints (keep $KEEP newest)
PRUNED=0
while [ "$(ls -1dt "$BACKUP_ROOT"/staging-* 2>/dev/null | wc -l)" -gt "$KEEP" ]; do
    OLDEST="$(ls -1dt "$BACKUP_ROOT"/staging-* | tail -1)"
    rm -rf "$OLDEST"
    PRUNED=$((PRUNED+1))
done

log "checkpoint complete: $NEWEST (pruned $PRUNED old)"
log "disk usage: $(du -sh "$BACKUP_ROOT" | cut -f1)"
