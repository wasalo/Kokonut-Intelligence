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

NON_DB_SKIPS=$(grep '^SKIPPED ' "$REPORT_FILE" | grep -v "no database available" || true)
if [ -n "$NON_DB_SKIPS" ]; then
    echo "ERROR: full test suite contains non-database skipped tests:" >&2
    echo "$NON_DB_SKIPS" >&2
    exit 1
fi
