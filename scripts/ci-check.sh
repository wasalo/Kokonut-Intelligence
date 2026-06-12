#!/usr/bin/env bash
# ============================================================
# ci-check.sh — Continuous Integration validation
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kokonut Intelligence — CI Check ==="
echo ""

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  ✓ $name"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name"
        FAIL=$((FAIL + 1))
    fi
}

# 1. Python imports
echo "[1/6] Python import validation..."
check "Import services.ingestion.base" "python3 -c 'import services.ingestion.base'"
check "Import services.forecast.engine" "python3 -c 'import services.forecast.engine'"
check "Import services.forecast.cli" "python3 -c 'import services.forecast.cli'"
check "Import services.analytics.ecology" "python3 -c 'import services.analytics.ecology'"
check "Import services.fortune500.calculator" "python3 -c 'import services.fortune500.calculator'"
check "Import services.revenue_multiplier.analyzer" "python3 -c 'import services.revenue_multiplier.analyzer'"
check "Import services.export.report_generator" "python3 -c 'import services.export.report_generator'"
check "Import services.attestation.cli" "python3 -c 'import services.attestation.cli'"
check "Import services.attestation.eas_client" "python3 -c 'import services.attestation.eas_client'"
check "Import services.attestation.schema_encoder" "python3 -c 'import services.attestation.schema_encoder'"
echo ""

# 2. CLI parsers
echo "[2/6] CLI parser validation..."
check "forecast CLI --help" "python3 -m services.forecast.cli --help"
check "analytics CLI --help" "python3 -m services.analytics.cli --help"
check "revenue_multiplier CLI --help" "python3 -m services.revenue_multiplier.cli --help"
check "fortune500 CLI --help" "python3 -m services.fortune500.cli --help"
check "report_generator CLI --help" "python3 -m services.export.report_generator --help"
check "attestation CLI --help" "python3 -m services.attestation.cli --help"
echo ""

# 3. TypeScript extension build (if node_modules present)
echo "[3/6] TypeScript extension build..."
if [ -d "$PROJECT_DIR/extensions/kokonut-hooks/node_modules" ]; then
    cd "$PROJECT_DIR/extensions/kokonut-hooks"
    check "npm run build" "npm run build"
    cd "$PROJECT_DIR"
else
    echo "  ⚠ node_modules not found — skipping TS build"
fi
echo ""

# 4. Seed idempotency (if DB is available)
echo "[4/6] Seed idempotency check..."
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --status running --services 2>/dev/null | grep -qx 'database'; then
    check "seed.sh idempotent" "bash $SCRIPT_DIR/seed.sh"
    check "seed-pilot.sh idempotent" "bash $SCRIPT_DIR/seed-pilot.sh"
else
    echo "  ⚠ Database not running — skipping seed checks"
fi
echo ""

# 5. Directus metadata checks
echo "[5/6] Directus metadata checks..."
check "directus metadata" "python3 -m tests.test_directus_metadata"
echo ""

# 6. Smoke test suite
echo "[6/6] Smoke test suite..."
check "smoke tests" "python3 -m tests.test_smoke"
echo ""

# Summary
echo "=== Results ==="
echo "  Pass: $PASS"
echo "  Fail: $FAIL"

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "  All CI checks passed ✓"
    exit 0
else
    echo ""
    echo "  $FAIL check(s) failed"
    exit 1
fi
