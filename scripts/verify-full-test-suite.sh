#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTEST_BIN="${PYTEST_BIN:-$PYTHON_BIN}"
HEARTBEAT_INTERVAL_SECONDS="${PYTEST_HEARTBEAT_INTERVAL_SECONDS:-15}"
SHARD_COUNT="${KOKONUT_PYTEST_SHARDS:-96}"
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

run_pytest_shard() {
    local shard_index="$1"
    local shard_count="$2"
    shift 2

    (
        set +e
        KOKONUT_PYTEST_SHARD_INDEX="$shard_index" "$PYTEST_BIN" -m pytest -v -rs --durations=25 "$@" 2>&1 | tee -a "$REPORT_FILE"
        exit "${PIPESTATUS[0]}"
    ) &
    PYTEST_PID=$!
    (
        while kill -0 "$PYTEST_PID" 2>/dev/null; do
            sleep "$HEARTBEAT_INTERVAL_SECONDS"
            if kill -0 "$PYTEST_PID" 2>/dev/null; then
                printf "Full Python test shard %s/%s is still running (PID %s).\n" "$((shard_index + 1))" "$shard_count" "$PYTEST_PID"
                ps -axo pid=,ppid=,rss=,etime=,comm= | awk -v root="$PYTEST_PID" '$1 == root { print; descendants[$1] = 1; next } descendants[$2] { print; descendants[$1] = 1 }' || true
                if [ -r /proc/meminfo ]; then
                    awk '/^MemTotal:|^MemAvailable:/ { print }' /proc/meminfo
                fi
            fi
        done
    ) &
    HEARTBEAT_PID=$!

    set +e
    wait "$PYTEST_PID"
    local shard_status=$?
    kill "$HEARTBEAT_PID" 2>/dev/null || true
    wait "$HEARTBEAT_PID" 2>/dev/null || true
    set -e
    PYTEST_PID=""
    HEARTBEAT_PID=""
    return "$shard_status"
}

case "$SHARD_COUNT" in
    ''|*[!0-9]*|0)
        echo "ERROR: KOKONUT_PYTEST_SHARDS must be a positive integer." >&2
        exit 2
        ;;
esac
TEST_FILE_COUNT="$($PYTHON_BIN "$SCRIPT_DIR/pytest_test_sharding.py" --repository-root "$ROOT_DIR" --test-root "$ROOT_DIR/tests" --count-only)"
case "$TEST_FILE_COUNT" in
    ''|*[!0-9]*)
        echo "ERROR: pytest test-file discovery returned an invalid count." >&2
        exit 2
        ;;
esac
if [ "$TEST_FILE_COUNT" -eq 0 ]; then
    echo "ERROR: no pytest test files were discovered under tests/." >&2
    exit 2
fi
if [ "$SHARD_COUNT" -gt "$TEST_FILE_COUNT" ]; then
    SHARD_COUNT="$TEST_FILE_COUNT"
fi

echo "Running the full Python test suite in $SHARD_COUNT sequential shards ($TEST_FILE_COUNT test files)."
OVERALL_TEST_STATUS=0
TOTAL_TEST_FILES=0
for ((shard_index = 0; shard_index < SHARD_COUNT; shard_index++)); do
    SHARD_FILES=()
    while IFS= read -r test_file; do
        [ -n "$test_file" ] || continue
        SHARD_FILES[${#SHARD_FILES[@]}]="$test_file"
    done < <("$PYTHON_BIN" "$SCRIPT_DIR/pytest_test_sharding.py" --repository-root "$ROOT_DIR" --test-root "$ROOT_DIR/tests" --shard-count "$SHARD_COUNT" --shard-index "$shard_index")

    if [ "${#SHARD_FILES[@]}" -eq 0 ]; then
        continue
    fi
    TOTAL_TEST_FILES=$((TOTAL_TEST_FILES + ${#SHARD_FILES[@]}))
    printf "=== Python test shard %s/%s (%s files) ===\n" "$((shard_index + 1))" "$SHARD_COUNT" "${#SHARD_FILES[@]}"
    if run_pytest_shard "$shard_index" "$SHARD_COUNT" "${SHARD_FILES[@]}"; then
        :
    else
        shard_status=$?
        echo "ERROR: Python test shard $((shard_index + 1))/$SHARD_COUNT exited with status $shard_status." >&2
        if [ "$OVERALL_TEST_STATUS" -eq 0 ]; then
            OVERALL_TEST_STATUS=$shard_status
        fi
    fi
done
if [ "$TOTAL_TEST_FILES" -ne "$TEST_FILE_COUNT" ]; then
    echo "ERROR: ran $TOTAL_TEST_FILES test files, expected $TEST_FILE_COUNT." >&2
    OVERALL_TEST_STATUS=1
fi
TEST_STATUS=$OVERALL_TEST_STATUS
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
