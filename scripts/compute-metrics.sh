#!/usr/bin/env bash
# ============================================================
# compute-metrics.sh — Compute all metrics for all locations
# ============================================================
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kokonut Intelligence — Metric Computation ==="

python3 -m services.metrics --compute --all-locations --json

echo ""
echo "=== Metric computation complete ==="
