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
echo "[1/8] Python import validation..."
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
check "Import services.metrics.engine" "python3 -c 'import services.metrics.engine'"
check "Import services.metrics.calculators" "python3 -c 'import services.metrics.calculators'"
check "Import services.common.logging" "python3 -c 'import services.common.logging'"
check "Import services.migration.cli" "python3 -c 'import services.migration.cli'"
check "Import services.registry.cids_export" "python3 -c 'import services.registry.cids_export'"
check "Import services.agents.safety" "python3 -c 'import services.agents.safety'"
check "Import services.agents.tasks" "python3 -c 'import services.agents.tasks'"
check "Import services.agents.cids_agent" "python3 -c 'import services.agents.cids_agent'"
check "Import services.agents.feedback_agent" "python3 -c 'import services.agents.feedback_agent'"
check "Import services.agents.wellbeing_agent" "python3 -c 'import services.agents.wellbeing_agent'"
check "Import services.agents.resilience_agent" "python3 -c 'import services.agents.resilience_agent'"
check "Import EBF agents" "python3 -c 'import services.agents.ebf_scorecard_agent; import services.agents.ebf_evidence_gap_agent; import services.agents.ebf_calibration_agent'"
check "Import services.analytics.portfolio" "python3 -c 'import services.analytics.portfolio'"
check "Import services.export.spreadsheet_bridge" "python3 -c 'import services.export.spreadsheet_bridge'"
check "Import services.scoring" "python3 -c 'import services.scoring.export; import services.scoring.trust_graph; import services.scoring.confidence; import services.scoring.calculators; import services.scoring.rubric; import services.scoring.normalization; import services.scoring.gates; import services.scoring.equity; import services.scoring.implementation_quality; import services.scoring.equity_community'"
echo ""

# 2. CLI parsers
echo "[2/8] CLI parser validation..."
check "forecast CLI --help" "python3 -m services.forecast.cli --help"
check "analytics CLI --help" "python3 -m services.analytics.cli --help"
check "revenue_multiplier CLI --help" "python3 -m services.revenue_multiplier.cli --help"
check "fortune500 CLI --help" "python3 -m services.fortune500.cli --help"
check "report_generator CLI --help" "python3 -m services.export.report_generator --help"
check "attestation CLI --help" "python3 -m services.attestation.cli --help"
check "metrics CLI --help" "python3 -m services.metrics --help"
check "cids_export CLI --help" "python3 -m services.registry.cids_export --help"
check "agent tasks CLI --help" "python3 -m services.agents.tasks --help"
check "cids agent CLI --help" "python3 -m services.agents.cids_agent --help"
check "feedback agent CLI --help" "python3 -m services.agents.feedback_agent --help"
check "wellbeing agent CLI --help" "python3 -m services.agents.wellbeing_agent --help"
check "resilience agent CLI --help" "python3 -m services.agents.resilience_agent --help"
check "EBF scorecard agent CLI --help" "python3 -m services.agents.ebf_scorecard_agent --help"
check "EBF evidence gap agent CLI --help" "python3 -m services.agents.ebf_evidence_gap_agent --help"
check "EBF calibration agent CLI --help" "python3 -m services.agents.ebf_calibration_agent --help"
check "spreadsheet bridge CLI --help" "python3 -m services.export.spreadsheet_bridge --help"
check "EBF scoring CLI --help" "python3 -m services.scoring --help"
echo ""

# 3. TypeScript extension build (if node_modules present)
echo "[3/8] TypeScript extension build..."
if [ -d "$PROJECT_DIR/extensions/kokonut-hooks/node_modules" ]; then
    cd "$PROJECT_DIR/extensions/kokonut-hooks"
    check "npm run build" "npm run build"
    cd "$PROJECT_DIR"
else
    echo "  ⚠ node_modules not found — skipping TS build"
fi
echo ""

# 4. Seed idempotency (if DB is available)
echo "[4/8] Seed idempotency check..."
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --status running --services 2>/dev/null | grep -qx 'database'; then
    check "seed.sh idempotent" "bash $SCRIPT_DIR/seed.sh"
    check "seed-pilot.sh idempotent" "bash $SCRIPT_DIR/seed-pilot.sh"
    check "compute metrics" "bash $SCRIPT_DIR/compute-metrics.sh"
    check "MVP definition of done" "bash $SCRIPT_DIR/verify-mvp.sh"
else
    echo "  ⚠ Database not running — skipping seed checks"
fi
echo ""

# 5. Directus metadata checks
echo "[5/8] Directus metadata checks..."
check "directus metadata" "python3 -m tests.test_directus_metadata"
check "metric calculators" "python3 -m tests.test_metrics"
check "cids export" "python3 -m tests.test_cids_export"
check "agent safety" "python3 -m tests.test_agent_safety"
check "agent tasks" "python3 -m tests.test_agent_tasks"
check "portfolio analytics" "python3 -m tests.test_portfolio"
check "spreadsheet bridge" "python3 -m tests.test_spreadsheet_bridge"
check "common foundations" "python3 -m tests.test_common_foundations"
check "holistic wellbeing" "python3 -m tests.test_holistic_wellbeing"
check "financial resilience" "python3 -m tests.test_financial_resilience"
check "EBF P0 schema and rubric" "python3 -m tests.test_ebf_p0"
check "EBF P1 operations" "python3 -m tests.test_ebf_p1"
check "EBF P2 portfolio and docs" "python3 -m tests.test_ebf_p2"
check "EBF schema migrations" "python3 -m tests.test_ebf_schema"
check "EBF scoring" "python3 -m tests.test_ebf_scoring"
check "EBF rubric" "python3 -m tests.test_ebf_rubric"
check "EBF normalization" "python3 -m tests.test_ebf_normalization"
check "EBF gates" "python3 -m tests.test_ebf_gates"
check "EBF public views" "python3 -m tests.test_ebf_public_views"
check "EBF privacy" "python3 -m tests.test_ebf_privacy"
check "EBF carbon gates" "python3 -m tests.test_ebf_carbon_gates"
check "EBF agent safety" "python3 -m tests.test_ebf_agent_safety"
check "EBF CSV import" "python3 -m tests.test_ebf_csv_import"
check "EBF JSON export" "python3 -m tests.test_ebf_json_export"
check "EBF dashboard" "python3 -m tests.test_ebf_dashboard"
check "EBF calibration" "python3 -m tests.test_ebf_calibration"
check "EBF CIDS" "python3 -m tests.test_ebf_cids"
check "EBF trust graph" "python3 -m tests.test_ebf_trust_graph"
check "EBF agents" "python3 -m tests.test_ebf_agents"
check "EBF equity scoring" "python3 -m tests.test_ebf_equity_scoring"
check "EBF DB integration" "python3 -m tests.test_ebf_db_integration"
echo ""

# 6. Smoke test suite
echo "[6/8] Smoke test suite..."
check "smoke tests" "python3 -m tests.test_smoke"
echo ""

# 7. CLI smoke tests
echo "[7/8] CLI smoke tests..."
check "CLI smoke tests" "python3 -m tests.test_cli"
echo ""

# 8. Attestation tests
echo "[8/8] Attestation tests..."
check "attestation tests" "python3 -m tests.test_attestation"
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
