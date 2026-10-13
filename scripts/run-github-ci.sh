#!/usr/bin/env bash
# Full GitHub Actions CI gate migrated from the former OneDev buildspec.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export COMPOSE_PROJECT_NAME=ki-ci
export CI_PG_HOST_PORT="${CI_PG_HOST_PORT:-127.0.0.1:15432}"
export CI_CH_HOST_PORT="${CI_CH_HOST_PORT:-127.0.0.1:18123}"
export PG_HOST=127.0.0.1
export PG_PORT=15432
export PG_DB=kokonut_intelligence
export PG_USER=kokonut
export PG_PASSWORD=ci-placeholder
export POSTGRES_PASSWORD=ci-placeholder
export CH_HOST=127.0.0.1
export CH_PORT=18123
export CH_USER=kokonut
export CH_DB=kokonut_analytics
export CLICKHOUSE_PASSWORD=ci-placeholder
export REDIS_PASSWORD=ci-placeholder
export KOKONUT_ENV=ci
export KOKONUT_ALLOW_PLAINTEXT_ENV=true
export CI_STRICT_DB=1

# Refuse to share or tear down an existing Compose namespace. GitHub-hosted
# runners start clean; this guard protects local use and persistent runners.
CI_PROJECT_CONTAINERS="$(docker ps -aq --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME")"
CI_PROJECT_VOLUMES="$(docker volume ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME")"
CI_PROJECT_NETWORKS="$(docker network ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME")"
if [ -n "$CI_PROJECT_CONTAINERS$CI_PROJECT_VOLUMES$CI_PROJECT_NETWORKS" ]; then
    echo "Refusing to use existing Compose namespace '$COMPOSE_PROJECT_NAME'; inspect it before retrying." >&2
    exit 1
fi

umask 077
CI_STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kokonut-github-ci.XXXXXX")"
ORIGINAL_ENV_PRESENT=false
ORIGINAL_SOPS_PRESENT=false
if [ -f .env ]; then
    cp -p .env "$CI_STATE_DIR/original.env"
    ORIGINAL_ENV_PRESENT=true
fi
if [ -f .env.sops ]; then
    cp -p .env.sops "$CI_STATE_DIR/original.env.sops"
    ORIGINAL_SOPS_PRESENT=true
fi

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if [ "$status" -ne 0 ]; then
        docker compose -f docker-compose.yml -f docker-compose.ci.yml \
            logs --no-color --tail=120 database clickhouse cache directus gateway grpc 2>/dev/null || true
    fi
    docker compose -f docker-compose.yml -f docker-compose.ci.yml down -v --remove-orphans 2>/dev/null || true

    rm -f .env .env.sops
    if [ "$ORIGINAL_ENV_PRESENT" = true ]; then
        cp -p "$CI_STATE_DIR/original.env" .env || status=1
    fi
    if [ "$ORIGINAL_SOPS_PRESENT" = true ]; then
        cp -p "$CI_STATE_DIR/original.env.sops" .env.sops || status=1
    fi
    rm -rf "$CI_STATE_DIR" || status=1
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Seed and app startup must use disposable CI values. Preserve the original
# local env files and restore them even if a later gate fails. Keep the tracked
# encrypted file present through the source scan below.
cat > .env <<'EOF'
KOKONUT_ENV=ci
KOKONUT_ALLOW_PLAINTEXT_ENV=true
POSTGRES_PASSWORD=ci-placeholder
PG_HOST=database
PG_DB=kokonut_intelligence
PG_USER=kokonut
PG_PASSWORD=ci-placeholder
CLICKHOUSE_PASSWORD=ci-placeholder
BACKUP_ENCRYPTION_KEY=ci-backup-key
REDIS_PASSWORD=ci-placeholder
DIRECTUS_SECRET=ci-secret
ADMIN_EMAIL=ci@kokonut.network
ADMIN_PASSWORD=ci-password
PUBLIC_URL=http://localhost:8055
METABASE_EMBEDDING_SECRET_KEY=ci-embedding-secret
CI_PG_HOST_PORT=127.0.0.1:15432
CI_CH_HOST_PORT=127.0.0.1:18123
DIRECTUS_HOST_PORT=127.0.0.1:18055
GATEWAY_HOST_PORT=127.0.0.1:18099
GRPC_HOST_PORT=127.0.0.1:50052
EOF

echo '=== Compose namespace isolation ==='
test "$COMPOSE_PROJECT_NAME" = ki-ci

echo '=== Supply-chain gates ==='
./scripts/check-tracked-secrets.sh
rm -f .env.sops
./scripts/check-image-digests.sh

echo '=== Kernel release-input and multi-architecture build gates ==='
bash scripts/build-kernel-multiarch.sh

echo '=== Clean bootstrap check ==='
docker compose -f docker-compose.yml up -d database
for _ in $(seq 1 30); do
    docker compose -f docker-compose.yml exec -T database pg_isready -q && break
    sleep 1
done
docker compose -f docker-compose.yml exec -T database pg_isready -q

echo '=== Installing Python and system build dependencies ==='
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates gcc libpq-dev python3-dev python3-venv xz-utils >/dev/null
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install slither-analyzer==0.11.5 semgrep==1.170.0 ruff pip-audit
npm install --global --no-audit --no-fund @cyfrin/aderyn@0.6.8
# GitHub Actions installs a pinned Foundry action/toolchain before this script.
# Local runs must provide forge on PATH; the CI script never downloads a moving
# installer or toolchain release itself.
./scripts/verify-ci-toolchain.sh

echo '=== Ruff security scan ==='
ruff check --select S,BLE --ignore S101,S104,S105,S110,S112,S310,S311,S404,S603,S607,S608,RUF012,BLE001 services/

echo '=== pip-audit ==='
pip-audit -r requirements.txt

echo '=== Fast-fail CI checks ==='
./scripts/ci-check.sh

echo '=== Starting isolated CI infrastructure ==='
export KOKONUT_GIT_SHA="$(git rev-parse HEAD)"
docker compose -f docker-compose.yml -f docker-compose.ci.yml down -v --remove-orphans 2>/dev/null || true
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d database clickhouse cache

echo '=== Waiting for PostgreSQL ==='
for _ in $(seq 1 30); do
    docker compose -f docker-compose.yml -f docker-compose.ci.yml exec -T database pg_isready -q && break
    sleep 1
done
docker compose -f docker-compose.yml -f docker-compose.ci.yml exec -T database pg_isready -q

echo '=== Applying required database extensions and schema ==='
docker compose -f docker-compose.yml -f docker-compose.ci.yml \
    exec -T database psql -U kokonut -d kokonut_intelligence \
    -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' \
    -c 'CREATE EXTENSION IF NOT EXISTS "pgcrypto"' \
    -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm' \
    -c 'CREATE SCHEMA IF NOT EXISTS kokonut' \
    -c 'GRANT USAGE ON SCHEMA kokonut TO kokonut' \
    -c 'GRANT ALL ON SCHEMA public TO kokonut' \
    -c 'ALTER DATABASE kokonut_intelligence SET search_path TO public, kokonut'

echo '=== Starting Directus and seeding ==='
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d --wait directus
./scripts/seed.sh
./scripts/seed-pilot.sh

echo '=== Starting application services ==='
if ! docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d --build --wait gateway grpc; then
    docker compose -f docker-compose.yml -f docker-compose.ci.yml ps || true
    docker compose -f docker-compose.yml -f docker-compose.ci.yml logs --no-color --tail=200 gateway grpc || true
    exit 1
fi

echo '=== Verifying running application version and commit ==='
EXPECTED_VERSION="$(cat VERSION)"
docker compose -f docker-compose.yml -f docker-compose.ci.yml \
    exec -T gateway python3 - "$EXPECTED_VERSION" "$KOKONUT_GIT_SHA" <<'PY'
import sys
import services

expected_version, expected_sha = sys.argv[1:]
if services.__version__ != expected_version:
    raise SystemExit(f"version mismatch: {services.__version__} != {expected_version}")
if services.__git_sha__ != expected_sha:
    raise SystemExit(f"git SHA mismatch: {services.__git_sha__} != {expected_sha}")
print(f"Upgrade verification passed: {expected_version} ({expected_sha})")
PY

echo '=== Computing metrics ==='
./scripts/compute-metrics.sh

echo '=== Full Python suite (strict database mode) ==='
./scripts/verify-full-test-suite.sh

echo '=== Static analysis ==='
./scripts/static-analysis.sh

echo '=== Unified CLI smoke checks ==='
python3 -m services.cli --help >/dev/null
python3 -m services.cli metrics --help >/dev/null

echo '=== Solidity checks ==='
(cd contracts && forge fmt --check && forge build --sizes && forge test)

echo '=== Directus hook checks ==='
(cd extensions/kokonut-hooks && npm ci --no-audit --no-fund && npm run build && npm test)

echo 'All CI checks completed successfully.'
