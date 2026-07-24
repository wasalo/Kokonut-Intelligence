#!/usr/bin/env bash
# ============================================================
# compute-metrics.sh — Compute all metrics for all locations
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kokonut Intelligence — Metric Computation ==="

run_metrics() {
    python3 -m services.metrics --compute --all-locations --json
}

if [ "${KOKONUT_METRICS_EXECUTION:-auto}" = "host" ]; then
    run_metrics
elif [ -n "${PG_HOST:-}" ] && [ "${PG_HOST}" != "localhost" ] && [ "${PG_HOST}" != "127.0.0.1" ]; then
    run_metrics
elif docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --status running --services 2>/dev/null | grep -qx 'database'; then
    docker compose \
        -f "$PROJECT_DIR/docker-compose.yml" \
        -f "$PROJECT_DIR/docker-compose.worker.yml" \
        run --build --rm --no-deps kokonut-worker \
        python3 -m services.metrics --compute --all-locations --json
else
    run_metrics
fi

echo ""
echo "=== Metric computation complete ==="
