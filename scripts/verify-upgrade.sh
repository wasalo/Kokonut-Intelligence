#!/usr/bin/env bash
# Verify services from inside the Compose network after an upgrade.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
EXPECTED_VERSION="${KOKONUT_EXPECTED_VERSION:-$(tr -d '[:space:]' < "$PROJECT_DIR/VERSION")}"
EXPECTED_GIT_SHA="${KOKONUT_EXPECTED_GIT_SHA:-$(git -C "$PROJECT_DIR" rev-parse HEAD)}"


running() {
    [ -n "$(compose ps --status running --services "$1")" ]
}

for service in database clickhouse directus gateway grpc; do
    running "$service"
done

compose exec -T database pg_isready -U kokonut -d kokonut_intelligence >/dev/null
compose exec -T clickhouse clickhouse-client \
    --user kokonut --password "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set}" \
    --query "SELECT 1" >/dev/null
compose exec -T directus curl -fsS http://127.0.0.1:8055/server/ping >/dev/null
compose exec -T gateway curl -fsS http://127.0.0.1:8099/health >/dev/null

compose exec -T gateway python3 - "$EXPECTED_VERSION" "$EXPECTED_GIT_SHA" <<'PY'
import sys
import services

expected_version, expected_sha = sys.argv[1:]
if services.__version__ != expected_version:
    raise SystemExit(f"version mismatch: {services.__version__} != {expected_version}")
if services.__git_sha__ != expected_sha:
    raise SystemExit(f"git SHA mismatch: {services.__git_sha__} != {expected_sha}")
PY

echo "Upgrade verification passed: $EXPECTED_VERSION ($EXPECTED_GIT_SHA)"
