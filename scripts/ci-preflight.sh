#!/usr/bin/env bash
# Fast, dependency-free checks that should gate the expensive CI jobs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_preflight() {
    local description="$1"
    shift
    printf '[preflight] %s\n' "$description"
    "$@"
}

run_preflight "Python runtime" python3 scripts/check-python-runtime.py
run_preflight "Dependency group alignment" python3 scripts/check-requirement-groups.py
run_preflight "Capability matrix integrity" python3 scripts/check-capability-matrix.py
run_preflight "Kernel release input lock" python3 scripts/check-kernel-release-inputs.py
run_preflight "Report-generator source inventory" \
    python3 scripts/report_generator_inventory.py --check docs/refactor/report-generator-source-inventory.json
run_preflight "Report-generator query-scope inventory" \
    python3 scripts/report_generator_query_scope_inventory.py --check docs/refactor/report-generator-query-scope-inventory.json
run_preflight "Report-generator helper-scope inventory" \
    python3 scripts/report_generator_helper_scope_inventory.py --check docs/refactor/report-generator-helper-scope-inventory.json
run_preflight "Runtime SQL inventory" \
    python3 scripts/runtime_sql_inventory.py --check docs/refactor/runtime-sql-inventory.json

echo 'CI preflight passed; starting source, integration, and image checks.'
