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
HEALTH_OUTPUT=$("$SCRIPT_DIR/health-check.sh" --alert 2>&1) && HEALTH_EXIT=0 || HEALTH_EXIT=$?

if [ "$HEALTH_EXIT" -eq 0 ]; then
    # Healthy — suppress output for cron
    exit 0
else
    # Failed — show output for cron log, alerts already sent by --alert
    echo "$HEALTH_OUTPUT"
    exit "$HEALTH_EXIT"
fi
