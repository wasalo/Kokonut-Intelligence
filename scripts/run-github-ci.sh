#!/usr/bin/env bash
# Full GitHub Actions CI gate migrated from the former OneDev buildspec.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_MODE="${1:-all}"
case "$RUN_MODE" in
    all|--source-only|--integration-only) ;;
    *)
        echo "Usage: $0 [--source-only|--integration-only]" >&2
        exit 2
        ;;
esac

export COMPOSE_PROJECT_NAME=ki-ci
export CI_PG_HOST_PORT="${CI_PG_HOST_PORT:-127.0.0.1:15432}"
export CI_CH_HOST_PORT="${CI_CH_HOST_PORT:-127.0.0.1:18123}"
export PG_HOST=127.0.0.1
export PG_PORT=15432
export PG_DB=kokonut_intelligence
export PG_USER=kokonut
export PG_PASSWORD=ci-placeholder
export POSTGRES_PASSWORD=ci-placeholder
# CI runs host-side database checks against its published loopback ports. Keep
# metric computation on that configured connection instead of resolving the
# local one-shot worker profile and requiring production runtime credentials.
export KOKONUT_METRICS_EXECUTION=host
export CH_HOST=127.0.0.1
export CH_PORT=18123
export CH_USER=kokonut
export CH_DB=kokonut_analytics
export CLICKHOUSE_PASSWORD=ci-placeholder
export REDIS_PASSWORD=ci-placeholder
export KOKONUT_ENV=ci
export KOKONUT_ALLOW_PLAINTEXT_ENV=true
export CI_STRICT_DB=1
export PIP_DEFAULT_TIMEOUT=60
export PIP_RETRIES=5
export PIP_DISABLE_PIP_VERSION_CHECK=1
export npm_config_fetch_retries=5
export npm_config_fetch_retry_factor=2
export npm_config_fetch_retry_mintimeout=10000
export npm_config_fetch_retry_maxtimeout=120000

CI_COMPOSE=(docker compose --progress plain -f docker-compose.yml -f docker-compose.ci.yml)
CI_DIAGNOSTICS_DIR="${CI_DIAGNOSTICS_DIR:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}/kokonut-ci-diagnostics-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}}"
CI_PHASE=
CI_PHASE_STARTED=$SECONDS
CI_GROUP_OPEN=false

ci_finish_phase() {
    local result="$1"
    local duration=$((SECONDS - CI_PHASE_STARTED))
    if [ "$CI_GROUP_OPEN" = true ]; then
        echo '::endgroup::'
        CI_GROUP_OPEN=false
    fi
    printf '[CI phase] %s: %ss (%s)\n' "$CI_PHASE" "$duration" "$result"
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        if [ ! -f "$GITHUB_STEP_SUMMARY" ] || ! grep -q '^## CI phase timings$' "$GITHUB_STEP_SUMMARY"; then
            printf '## CI phase timings\n\n| Phase | Result | Duration |\n| --- | --- | ---: |\n' >> "$GITHUB_STEP_SUMMARY"
        fi
        printf '| %s | %s | %ss |\n' "$CI_PHASE" "$result" "$duration" >> "$GITHUB_STEP_SUMMARY"
    fi
}

ci_phase_start() {
    local next_phase="$1"
    if [ -n "$CI_PHASE" ]; then
        ci_finish_phase passed
    fi
    CI_PHASE="$next_phase"
    CI_PHASE_STARTED=$SECONDS
    echo "::group::CI phase: $CI_PHASE"
    CI_GROUP_OPEN=true
}

run_ci_timeout() {
    local duration="$1"
    shift
    local timeout_bin
    if command -v timeout >/dev/null 2>&1; then
        timeout_bin="$(command -v timeout)"
    elif command -v gtimeout >/dev/null 2>&1; then
        timeout_bin="$(command -v gtimeout)"
    else
        echo "Warning: no timeout utility found; running without the ${duration} outer bound." >&2
        "$@"
        return
    fi
    "$timeout_bin" --kill-after=30s "$duration" "$@"
}

# Refuse to share or tear down an existing Compose namespace. GitHub-hosted
# runners start clean; this guard protects local use and persistent runners.
if [ "$RUN_MODE" != --source-only ]; then
    CI_PROJECT_CONTAINERS="$(docker ps -aq --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME")"
    CI_PROJECT_VOLUMES="$(docker volume ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME")"
    CI_PROJECT_NETWORKS="$(docker network ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME")"
    if [ -n "$CI_PROJECT_CONTAINERS$CI_PROJECT_VOLUMES$CI_PROJECT_NETWORKS" ]; then
        echo "Refusing to use existing Compose namespace '$COMPOSE_PROJECT_NAME'; inspect it before retrying." >&2
        exit 1
    fi
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
    if [ "$status" -eq 0 ]; then
        if [ -n "$CI_PHASE" ]; then ci_finish_phase passed; fi
    else
        if [ -n "$CI_PHASE" ]; then ci_finish_phase failed; fi
        printf '::error title=CI runner failed::Mode "%s", phase "%s", failed after %ss (exit %s). See the phase summary and uploaded diagnostics.\n' \
            "$RUN_MODE" "$CI_PHASE" "$((SECONDS - CI_PHASE_STARTED))" "$status"
        mkdir -p "$CI_DIAGNOSTICS_DIR" 2>/dev/null || true
        if [ -n "${DB_PULL_PID:-}" ]; then
            kill "$DB_PULL_PID" 2>/dev/null || true
            wait "$DB_PULL_PID" 2>/dev/null || true
        fi
        if [ -s "${DB_PULL_LOG:-}" ]; then
            cp "$DB_PULL_LOG" "$CI_DIAGNOSTICS_DIR/postgis-image-pull.log" 2>/dev/null || true
        fi
        if [ "$RUN_MODE" != --source-only ]; then
            {
                printf 'phase=%s\nexit_code=%s\n' "$CI_PHASE" "$status"
                run_ci_timeout 30s "${CI_COMPOSE[@]}" ps --all || true
            } > "$CI_DIAGNOSTICS_DIR/compose-state.txt" 2>&1
            run_ci_timeout 2m "${CI_COMPOSE[@]}" logs --no-color --tail=500 database clickhouse cache directus gateway grpc \
                > "$CI_DIAGNOSTICS_DIR/compose-logs.txt" 2>&1 || true
            if [ -s "$CI_DIAGNOSTICS_DIR/compose-logs.txt" ]; then
                tail -n 160 "$CI_DIAGNOSTICS_DIR/compose-logs.txt"
            fi
        fi
    fi
    if [ "$status" -ne 0 ]; then
        printf 'CI runner mode "%s" failed during phase "%s" after %ss (exit %s).\n' \
            "$RUN_MODE" "$CI_PHASE" "$((SECONDS - CI_PHASE_STARTED))" "$status" >&2
    fi
    if [ "$RUN_MODE" != --source-only ]; then
        run_ci_timeout 2m "${CI_COMPOSE[@]}" down -v --remove-orphans 2>/dev/null || true
    fi

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

if [ "$RUN_MODE" != --source-only ]; then
    echo '=== Compose namespace isolation ==='
    test "$COMPOSE_PROJECT_NAME" = ki-ci
fi

if [ "$RUN_MODE" != --integration-only ]; then
    ci_phase_start 'Supply-chain gates'
    echo '=== Supply-chain gates ==='
    ./scripts/check-tracked-secrets.sh
    rm -f .env.sops
    ./scripts/check-image-digests.sh
fi

if [ "$RUN_MODE" != --source-only ]; then
    ci_phase_start 'PostGIS image pull and dependencies'
    DB_PULL_LOG="$CI_STATE_DIR/postgis-image-pull.log"
    "${CI_COMPOSE[@]}" pull database > >(tee "$DB_PULL_LOG") 2>&1 &
    DB_PULL_PID=$!
else
    ci_phase_start 'Source dependencies'
fi
echo '=== Installing Python and system build dependencies ==='
if [ "${GITHUB_ACTIONS:-false}" != true ] && command -v apt-get >/dev/null 2>&1; then
    APT_PREFIX=()
    if [ "$(id -u)" -ne 0 ]; then APT_PREFIX=(sudo); fi
    APT_OPTIONS=(
        -o Acquire::Retries=2
        -o Acquire::http::Timeout=30
        -o Acquire::https::Timeout=30
        -o Dpkg::Use-Pty=0
    )
    echo 'Installing optional host build tools (10-minute bound; apt output is visible)...'
    if ! run_ci_timeout 10m "${APT_PREFIX[@]}" apt-get "${APT_OPTIONS[@]}" update; then
        echo 'Host package index update failed or exceeded 10 minutes.' >&2
        exit 1
    fi
    if ! run_ci_timeout 10m "${APT_PREFIX[@]}" apt-get "${APT_OPTIONS[@]}" install -y --no-install-recommends \
        ca-certificates gcc libpq-dev python3-dev python3-venv xz-utils; then
        echo 'Host build-tool installation failed or exceeded 10 minutes.' >&2
        exit 1
    fi
else
    echo 'Skipping apt bootstrap: hosted runners and non-apt hosts use Python wheels.'
fi
APP_VENV="$CI_STATE_DIR/app"
python3 -m venv "$APP_VENV"
. "$APP_VENV/bin/activate"
python -m pip --version
if ! run_ci_timeout 10m python -m pip install --upgrade --only-binary=:all: --retries 5 --timeout 60 pip setuptools; then
    echo 'Application bootstrap dependency installation failed or exceeded 10 minutes.' >&2
    exit 1
fi
if ! run_ci_timeout 25m python -m pip install --only-binary=:all: --retries 5 --timeout 60 -r requirements.txt; then
    echo 'Application dependency installation failed or exceeded 25 minutes.' >&2
    exit 1
fi
python -m pip check
APP_SITE_PACKAGES="$(python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
if [ "$RUN_MODE" != --integration-only ]; then
    CI_TOOLS_VENV="$CI_STATE_DIR/ci-tools"
    python3 -m venv "$CI_TOOLS_VENV"
    if ! run_ci_timeout 20m "$CI_TOOLS_VENV/bin/python" -m pip install --only-binary=:all: --retries 5 --timeout 60 -r requirements/ci-tools.txt; then
        echo 'CI tool installation failed or exceeded 20 minutes.' >&2
        exit 1
    fi
    "$CI_TOOLS_VENV/bin/python" -m pip check
    CI_TOOLS_BIN="$CI_TOOLS_VENV/bin"
    if ! run_ci_timeout 15m npm install --global --no-audit --no-fund \
        --fetch-retries=5 --fetch-retry-factor=2 @cyfrin/aderyn@0.6.8; then
        echo 'Aderyn installation failed or exceeded 15 minutes.' >&2
        exit 1
    fi
    # GitHub Actions installs a pinned Foundry action/toolchain before this script.
    # Local runs must provide forge on PATH; the CI script never downloads a moving
    # installer or toolchain release itself.
    PATH="$CI_TOOLS_BIN:$PATH" ./scripts/verify-ci-toolchain.sh
fi

if [ "$RUN_MODE" != --integration-only ]; then
    ci_phase_start 'Python supply-chain and security checks'
    echo '=== Ruff security scan ==='
    "$CI_TOOLS_BIN/ruff" check --select S,BLE --ignore S101,S104,S105,S110,S112,S310,S311,S404,S603,S607,S608,RUF012,BLE001 services/

    echo '=== pip-audit ==='
    PIPAPI_PYTHON_LOCATION="$APP_VENV/bin/python" "$CI_TOOLS_BIN/pip-audit" --path "$APP_SITE_PACKAGES"

    ci_phase_start 'Fast-fail source, import, CLI, and hook checks'
    echo '=== Fast-fail source checks ==='
    ./scripts/ci-check.sh --source-only
fi

if [ "$RUN_MODE" = --source-only ]; then
    ci_phase_start 'Static analysis'
    echo '=== Static analysis ==='
    PATH="$CI_TOOLS_BIN:$PATH" ./scripts/static-analysis.sh

    ci_phase_start 'Solidity checks'
    echo '=== Solidity checks ==='
    (cd contracts && forge fmt --check && forge build --sizes && forge test)

    ci_phase_start 'Directus hook tests'
    echo '=== Directus hook checks ==='
    make hooks-test
    echo 'All source and contract CI checks completed successfully.'
    exit 0
fi

if [ "$RUN_MODE" = --integration-only ]; then
    # Do not inherit a tracked encrypted developer environment in CI. The
    # disposable plaintext file above is the only configuration this runner
    # should load after the original has been preserved for cleanup.
    rm -f .env.sops
fi

ci_phase_start 'Clean PostgreSQL bootstrap'
if ! wait "$DB_PULL_PID"; then
    exit 1
fi
DB_PULL_PID=
echo '=== Starting PostgreSQL and running clean bootstrap ==='
"${CI_COMPOSE[@]}" up -d database
for _ in $(seq 1 90); do
    "${CI_COMPOSE[@]}" exec -T database pg_isready -h 127.0.0.1 -U kokonut -d kokonut_intelligence -q && break
    sleep 1
done
"${CI_COMPOSE[@]}" exec -T database pg_isready -h 127.0.0.1 -U kokonut -d kokonut_intelligence -q

ci_phase_start 'Disposable PostgreSQL bootstrap checks'
echo '=== Disposable PostgreSQL bootstrap check ==='
./scripts/ci-check.sh --database-only

ci_phase_start 'Disposable database authorization checks'
echo '=== Agent lifecycle worker/admin boundary ==='
python3 scripts/check-agent-safety-superuser-disposable.py

echo '=== Signed credit-adjustment worker boundary ==='
python3 scripts/check-credit-adjustment-worker-disposable.py

ci_phase_start 'ClickHouse and Redis startup'
echo '=== Starting isolated CI infrastructure ==='
export KOKONUT_GIT_SHA="$(git rev-parse HEAD)"
"${CI_COMPOSE[@]}" up -d clickhouse cache

ci_phase_start 'Database extensions and schema setup'
echo '=== Applying required database extensions and schema ==='
"${CI_COMPOSE[@]}" \
    exec -T database psql -U kokonut -d kokonut_intelligence \
    -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' \
    -c 'CREATE EXTENSION IF NOT EXISTS "pgcrypto"' \
    -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm' \
    -c 'CREATE SCHEMA IF NOT EXISTS kokonut' \
    -c 'GRANT USAGE ON SCHEMA kokonut TO kokonut' \
    -c 'GRANT ALL ON SCHEMA public TO kokonut' \
    -c 'ALTER DATABASE kokonut_intelligence SET search_path TO public, kokonut'

ci_phase_start 'Directus extension build'
echo '=== Building Directus extension hooks ==='
make hooks-build

ci_phase_start 'Directus startup and data seed'
echo '=== Starting Directus and seeding ==='
"${CI_COMPOSE[@]}" up -d --wait directus
./scripts/seed.sh
./scripts/seed-pilot.sh

ci_phase_start 'Gateway and gRPC integration startup'
echo '=== Starting application services ==='
if ! "${CI_COMPOSE[@]}" up -d --build --wait gateway grpc; then
    "${CI_COMPOSE[@]}" ps || true
    "${CI_COMPOSE[@]}" logs --no-color --tail=200 gateway grpc || true
    exit 1
fi

ci_phase_start 'Application version and commit verification'
echo '=== Verifying running application version and commit ==='
EXPECTED_VERSION="$(cat VERSION)"
"${CI_COMPOSE[@]}" \
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

ci_phase_start 'Metrics computation smoke check'
echo '=== Computing metrics ==='
./scripts/compute-metrics.sh

ci_phase_start 'Full Python test suite'
echo '=== Full Python suite (strict database mode) ==='
./scripts/verify-full-test-suite.sh

if [ "$RUN_MODE" = all ]; then
    ci_phase_start 'Static analysis'
    echo '=== Static analysis ==='
    PATH="$CI_TOOLS_BIN:$PATH" ./scripts/static-analysis.sh

    ci_phase_start 'Unified CLI smoke checks'
    echo '=== Unified CLI smoke checks ==='
    python3 -m services.cli --help >/dev/null
    python3 -m services.cli metrics --help >/dev/null

    ci_phase_start 'Solidity checks'
    echo '=== Solidity checks ==='
    (cd contracts && forge fmt --check && forge build --sizes && forge test)

    ci_phase_start 'Directus hook tests'
    echo '=== Directus hook checks ==='
    make hooks-test
fi

echo 'All CI checks completed successfully.'
