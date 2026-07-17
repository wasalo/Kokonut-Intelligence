#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
REPORT_FILE="$(mktemp)"
trap 'rm -f "$REPORT_FILE"' EXIT

set +e
"$PYTHON_BIN" -m pytest -q -rs 2>&1 | tee "$REPORT_FILE"
TEST_STATUS=${PIPESTATUS[0]}
set -e

if [ "$TEST_STATUS" -ne 0 ]; then
    exit "$TEST_STATUS"
fi

if grep -q '^SKIPPED ' "$REPORT_FILE"; then
    echo "ERROR: full test suite contains skipped tests." >&2
    exit 1
fi
