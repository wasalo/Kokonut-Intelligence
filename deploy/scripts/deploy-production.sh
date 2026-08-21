#!/usr/bin/env bash
# Deploy Kokonut Intelligence production via SSH to the production host.
#
# SAFETY MODEL (per repo governance):
#   - Requires DEPLOY_CONFIRM=yes explicitly.
#   - Takes a verified backup checkpoint BEFORE deploying.
#   - On failed health check: prints rollback instructions; never
#     auto-rolls-back (a human decides).
#
# Usage:
#   DEPLOY_PROD_HOST=ki-prod deploy/scripts/deploy-production.sh
#
# Required environment:
#   DEPLOY_PROD_HOST   SSH alias/host of the production host
#   DEPLOY_CONFIRM     must be exactly "yes"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_REPO="${REMOTE_REPO:-https://git.kokonut.network/Kokonut-Intelligence}"
REMOTE_ROOT="${REMOTE_ROOT:-/opt/ki-prod}"
BRANCH="${DEPLOY_BRANCH:-main}"

log() { printf '[deploy-prod] %s\n' "$*"; }
fail() { printf '[deploy-prod] FATAL: %s\n' "$*" >&2; exit 1; }

[ "${DEPLOY_CONFIRM:-}" = "yes" ] || fail "DEPLOY_CONFIRM must be 'yes' — this deploys PRODUCTION."
[ -n "${DEPLOY_PROD_HOST:-}" ] || fail "DEPLOY_PROD_HOST is required (SSH host of the production server)."
command -v ssh >/dev/null 2>&1 || fail "ssh not installed."

log "Production deployment to ${DEPLOY_PROD_HOST}:${REMOTE_ROOT} (branch ${BRANCH})"
log "Step 1/5: pre-deploy backup checkpoint on the production host..."
ssh "$DEPLOY_PROD_HOST" "cd ${REMOTE_ROOT} && sudo -E ./scripts/backup.sh" \
    || fail "pre-deploy backup failed — deployment aborted. Nothing was changed."

log "Step 2/5: pulling ${BRANCH}..."
ssh "$DEPLOY_PROD_HOST" "cd ${REMOTE_ROOT} \
    && git fetch origin ${BRANCH} --quiet \
    && git reset --hard origin/${BRANCH} --quiet \
    && echo \$(git rev-parse --short HEAD)" | { read -r SHA; log "deploying commit ${SHA:-unknown}"; }

log "Step 3/5: compose up (prod overlay + traefik)..."
ssh "$DEPLOY_PROD_HOST" "cd ${REMOTE_ROOT} \
    && docker compose -p ki-prod \
        -f docker-compose.yml \
        -f docker-compose.prod.yml \
        -f docker-compose.traefik.yml \
        up -d --build --wait --wait-timeout 300" \
    || fail "compose up failed — inspect with: ssh ${DEPLOY_PROD_HOST} 'docker compose -p ki-prod logs --tail 50'"

log "Step 4/5: health verification..."
sleep 10
if ssh "$DEPLOY_PROD_HOST" "./scripts/health-check.sh --json" > /tmp/ki-health.json 2>&1; then
    log "health check: PASS"
    cat /tmp/ki-health.json
    rm -f /tmp/ki-health.json
else
    cat /tmp/ki-health.json || true
    log "health check: FAIL"
    log "─────────────────────────────────────────────────────"
    log "ROLLBACK (manual decision — run when you've confirmed):"
    log "  ssh ${DEPLOY_PROD_HOST}"
    log "  cd ${REMOTE_ROOT} && ./scripts/rollback.sh --checkpoint <id-from-step-1> --confirm"
    log "─────────────────────────────────────────────────────"
    fail "post-deploy health check failed."
fi

log "Step 5/5: done."
log "Production is running commit from ${BRANCH} (deployed $(date -u +%FT%TZ))."
