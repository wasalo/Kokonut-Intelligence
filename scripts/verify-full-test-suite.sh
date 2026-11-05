#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
HEARTBEAT_INTERVAL_SECONDS="${PYTEST_HEARTBEAT_INTERVAL_SECONDS:-15}"
REPORT_FILE="$(mktemp)"
PYTEST_PID=""
HEARTBEAT_PID=""

cleanup() {
    if [ -n "$PYTEST_PID" ]; then
        kill "$PYTEST_PID" 2>/dev/null || true
        wait "$PYTEST_PID" 2>/dev/null || true
    fi
    if [ -n "$HEARTBEAT_PID" ]; then
        kill "$HEARTBEAT_PID" 2>/dev/null || true
        wait "$HEARTBEAT_PID" 2>/dev/null || true
    fi
    rm -f "$REPORT_FILE"
}
trap cleanup EXIT

run_full_test_suite() {
    set +e
    "$PYTHON_BIN" -m pytest -v -rs --durations=25 2>&1 | tee "$REPORT_FILE"
    exit "${PIPESTATUS[0]}"
}

run_full_test_suite &
PYTEST_PID=$!
(
    while kill -0 "$PYTEST_PID" 2>/dev/null; do
        sleep "$HEARTBEAT_INTERVAL_SECONDS"
        if kill -0 "$PYTEST_PID" 2>/dev/null; then
            echo "Full Python test suite is still running."
        fi
    done
) &
HEARTBEAT_PID=$!

set +e
wait "$PYTEST_PID"
TEST_STATUS=$?
kill "$HEARTBEAT_PID" 2>/dev/null || true
wait "$HEARTBEAT_PID" 2>/dev/null || true
set -e

if [ "$TEST_STATUS" -ne 0 ]; then
    exit "$TEST_STATUS"
fi

SKIPS=$(grep '^SKIPPED ' "$REPORT_FILE" || true)
if [ -n "$SKIPS" ]; then
    if [ "${CI_STRICT_DB:-0}" = "1" ]; then
        echo "ERROR: full test suite contains skipped tests in strict CI mode:" >&2
        echo "$SKIPS" >&2
        exit 1
    fi
    NON_DB_SKIPS=$(printf '%s\n' "$SKIPS" | grep -v "no database available" | grep -v "table not available" || true)
    if [ -n "$NON_DB_SKIPS" ]; then
        echo "ERROR: full test suite contains non-database skipped tests:" >&2
        echo "$NON_DB_SKIPS" >&2
        exit 1
    fi
fi
