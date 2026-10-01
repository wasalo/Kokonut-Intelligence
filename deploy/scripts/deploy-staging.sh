#!/usr/bin/env bash
# Deploy Kokonut Intelligence staging on the cerberus host.
# Idempotent: safe to re-run; converges to the state of origin/main.
#
# Usage:
#   deploy/scripts/deploy-staging.sh [--skip-seed] [--skip-build]
#
# Requires:
#   - /opt/ki-staging git checkout (branch main)
#   - sops + age key at /opt/ki-staging/.age-key
#   - deploy/staging/.env.staging.sops committed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Defaults to this checkout. On the staging host, set STAGING_ROOT=/opt/ki-staging.
# In CI, the job's own checkout is used and git reset is skipped (the job
# checkout already IS the commit being deployed).
STAGING_ROOT="${STAGING_ROOT:-$PROJECT_DIR}"
COMPOSE_PROJECT="ki-staging"
BRANCH="main"
AGE_KEY_FILE="$STAGING_ROOT/.age-key"
ENV_FILE="$STAGING_ROOT/deploy/staging/.env.staging.sops"
COMPOSE_FILES=(-f "$PROJECT_DIR/docker-compose.yml" -f "$PROJECT_DIR/deploy/staging/docker-compose.staging.yml")
SKIP_SEED=false
SKIP_BUILD=false

usage() {
    printf 'Usage: %s [--skip-seed] [--skip-build]\n' "$(basename "$0")"
    printf '  --skip-seed   Skip seed.sh / seed-pilot.sh\n'
    printf '  --skip-build  Pass --no-build to compose up\n'
    exit 0
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-seed) SKIP_SEED=true; shift ;;
        --skip-build) SKIP_BUILD=true; shift ;;
        --help|-h) usage ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

log() { printf '[deploy-staging] %s\n' "$*"; }
fail() { printf '[deploy-staging] FATAL: %s\n' "$*" >&2; exit 1; }

[ -d "$STAGING_ROOT/.git" ] || fail "no git checkout at $STAGING_ROOT"
[ -f "$AGE_KEY_FILE" ] || fail "age key missing at $AGE_KEY_FILE"
[ -f "$ENV_FILE" ] || fail "encrypted env missing at $ENV_FILE (commit it first)"
command -v sops >/dev/null 2>&1 || fail "sops not installed"
command -v docker >/dev/null 2>&1 || fail "docker not installed"

# ── 1. Pull latest main (host checkout only — CI checkout is pinned) ────
cd "$STAGING_ROOT"
if [ "${STAGING_SKIP_PULL:-}" = "1" ]; then
    log "STAGING_SKIP_PULL=1 — using this checkout as-is"
elif [ "$STAGING_ROOT" = "$PROJECT_DIR" ] && [ -n "${CI:-}" ]; then
    log "CI context: skipping git pull (checkout is the deployed commit)"
else
    CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    [ "$CURRENT_BRANCH" = "$BRANCH" ] || fail "staging checkout is on '$CURRENT_BRANCH', expected '$BRANCH'"
    log "Pulling origin/$BRANCH..."
    git fetch origin "$BRANCH" --quiet
    git reset --hard "origin/$BRANCH" --quiet
fi
DEPLOYED_SHA="$(git rev-parse --short HEAD)"
log "Deploying commit $DEPLOYED_SHA"

# ── 2. Decrypt environment (plaintext only in a temp pipe file, 0600) ──
ENV_PLAIN="$STAGING_ROOT/.env"
umask 077
cleanup() { rm -f "$ENV_PLAIN"; }
trap cleanup EXIT
export SOPS_AGE_KEY_FILE="$AGE_KEY_FILE"
# No --input-type/--output-type on decrypt: sops stores the original format
# in metadata and auto-detects it. Forcing dotenv here makes sops re-parse
# its own JSON envelope as dotenv and fail with "invalid dotenv input".
sops -d "$ENV_FILE" > "$ENV_PLAIN"
log "Environment decrypted ($(grep -c '=' "$ENV_PLAIN") vars)"

# Regenerate root .env.sops for runtime tooling (services.migration, CLIs)
# encrypted to THIS host's key. The committed root .env.sops is encrypted to
# dev keys only and git reset restores it on every deploy, so re-wrap here.
# The plaintext env carries a comment-free copy for sops dotenv input.
grep -v '^#' "$ENV_PLAIN" > "$ENV_PLAIN.nocomment"
if [ -f /opt/ki-staging/.age-key ]; then
    STAGING_PUBKEY="$(age-keygen -y /opt/ki-staging/.age-key 2>/dev/null)"
    if [ -n "$STAGING_PUBKEY" ]; then
        # Run from a config-free dir: a .sops.yaml in CWD must match the
        # input path or sops aborts before --age is considered. Encrypting
        # to an explicit --age key needs no creation rules.
        REWRAP_DIR="$(mktemp -d)"
        cp "$ENV_PLAIN.nocomment" "$REWRAP_DIR/.env"
        sops -e --input-type dotenv --output-type dotenv \
            --age "$STAGING_PUBKEY" \
            "$REWRAP_DIR/.env" > "$STAGING_ROOT/.env.sops"
        rm -rf "$REWRAP_DIR"
        # Preserve root ownership, but let the age-key group read the encrypted
        # file so the Staging backup cron can decrypt it without broader access.
        bash "$SCRIPT_DIR/set-staging-env-permissions.sh" \
            "$AGE_KEY_FILE" "$STAGING_ROOT/.env.sops"
        log "Root .env.sops re-wrapped to host key; age-key group has read-only access"
    fi
fi
rm -f "$ENV_PLAIN.nocomment"

# ── 3. Compose up ───────────────────────────────────────────────────────
UP_ARGS=(up -d)
if [ "$SKIP_BUILD" = true ]; then UP_ARGS+=(--no-build); else UP_ARGS+=(--build); fi
UP_ARGS+=(--wait --wait-timeout 300)
log "Composing project $COMPOSE_PROJECT..."
docker compose -p "$COMPOSE_PROJECT" "${COMPOSE_FILES[@]}" "${UP_ARGS[@]}"
log "All services healthy."

# ── 4. Seed (idempotent: ON CONFLICT guards) ───────────────────────────
if [ "$SKIP_SEED" = false ]; then
    log "Applying schema seeds..."
    docker compose -p "$COMPOSE_PROJECT" "${COMPOSE_FILES[@]}" \
        exec -T database psql -X -U kokonut -d kokonut_intelligence \
        -v ON_ERROR_STOP=1 -q < "$PROJECT_DIR/schemas/postgres/000_extensions.sql" 2>/dev/null || true
    log "Seeds are applied by migrations on first boot; skipping explicit seed scripts."
    log "(Run ./scripts/seed.sh + ./scripts/seed-pilot.sh manually if a fresh DB needs pilot data.)"
fi

# ── 5. Health verification ──────────────────────────────────────────────
log "Verifying health..."
sleep 5
UNHEALTHY=0
for svc in database clickhouse cache directus gateway grpc; do
    STATE="$(docker inspect -f '{{.State.Health.Status}}' "${COMPOSE_PROJECT}-${svc}-1" 2>/dev/null || echo missing)"
    case "$STATE" in
        healthy|none) log "  $svc: $STATE" ;;
        *) log "  $svc: $STATE (UNHEALTHY)"; UNHEALTHY=$((UNHEALTHY+1)) ;;
    esac
done
if [ "$UNHEALTHY" -gt 0 ]; then
    fail "$UNHEALTHY service(s) unhealthy — check: docker compose -p $COMPOSE_PROJECT logs"
fi

# ── 6. Summary ──────────────────────────────────────────────────────────
log "─────────────────────────────────────────────"
log "Staging deployed: commit $DEPLOYED_SHA"
log "Directus : http://127.0.0.1:18056"
log "Metabase : http://127.0.0.1:13001"
log "Gateway  : http://127.0.0.1:18098"
log "Backups  : nightly 03:30 → $STAGING_ROOT/backups"
log "─────────────────────────────────────────────"
