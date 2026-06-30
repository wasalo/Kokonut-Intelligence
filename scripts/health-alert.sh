#!/usr/bin/env bash
# ============================================================
# health-alert.sh — Cron wrapper for health-check.sh with alerting
#
# Quiet on success; sends webhook/email alerts on failure.
# Designed for cron: */5 * * * * /opt/Kokonut-Intelligence/scripts/health-alert.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Run health check with alerting
if "$SCRIPT_DIR/health-check.sh" --alert > /dev/null 2>&1; then
    # Healthy — suppress output for cron
    exit 0
else
    EXIT_CODE=$?
    # Failed — re-run with visible output for cron log, alerts already sent
    "$SCRIPT_DIR/health-check.sh" --alert 2>&1 || true
    exit $EXIT_CODE
fi
