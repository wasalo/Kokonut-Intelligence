#!/usr/bin/env bash
# ============================================================
# ci-check.sh — Fast-fail CI validation (imports, CLIs, TS build)
# ============================================================
# Full test coverage is handled by verify-full-test-suite.sh.
# Static analysis is handled by static-analysis.sh.
# Security tooling (ruff, pip-audit) runs as standalone buildspec steps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kokonut Intelligence — CI Check (fast-fail gate) ==="
echo ""

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    local output
    if output=$(eval "$cmd" 2>&1); then
        echo "  ✓ $name"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name"
        if [ -n "$output" ]; then
            echo "    $output" | head -200
        fi
        FAIL=$((FAIL + 1))
    fi
}

# 1. Python runtime and imports
echo "[1/3] Python import validation..."
check "Supported Python runtime" "python3 $SCRIPT_DIR/check-python-runtime.py"
check "FastAPI dependencies" "python3 -c 'import fastapi; from fastapi.testclient import TestClient; print(fastapi.__version__)'"
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
check "Migration source validation" "python3 -m services.migration validate"
check "Clean PostgreSQL bootstrap" "bash $SCRIPT_DIR/verify-clean-bootstrap.sh"
check "Import services.registry.cids_export" "python3 -c 'import services.registry.cids_export'"
check "Import services.agents.safety" "python3 -c 'import services.agents.safety'"
check "Import services.agents.tasks" "python3 -c 'import services.agents.tasks'"
check "Import services.agents.cids_agent" "python3 -c 'import services.agents.cids_agent'"
check "Import services.agents.feedback_agent" "python3 -c 'import services.agents.feedback_agent'"
check "Import services.agents.wellbeing_agent" "python3 -c 'import services.agents.wellbeing_agent'"
check "Import services.agents.resilience_agent" "python3 -c 'import services.agents.resilience_agent'"
check "Import services.agents.capital_efficiency_agent" "python3 -c 'import services.agents.capital_efficiency_agent'"
check "Import services.agents.commons_agent" "python3 -c 'import services.agents.commons_agent'"
check "Import services.agents.gnh_agent" "python3 -c 'import services.agents.gnh_agent'"
check "Import services.agents.regenerator_agent" "python3 -c 'import services.agents.regenerator_agent'"
check "Import services.agents.open_source_capitalist_agent" "python3 -c 'import services.agents.open_source_capitalist_agent'"
check "Import services.agents.kokonut_commons_agent" "python3 -c 'import services.agents.kokonut_commons_agent'"
check "Import services.agents.bio_factory_agent" "python3 -c 'import services.agents.bio_factory_agent'"
check "Import EBF agents" "python3 -c 'import services.agents.ebf_scorecard_agent; import services.agents.ebf_evidence_gap_agent; import services.agents.ebf_calibration_agent'"
check "Import services.analytics.portfolio" "python3 -c 'import services.analytics.portfolio'"
check "Import services.export.spreadsheet_bridge" "python3 -c 'import services.export.spreadsheet_bridge'"
check "Import services.scoring" "python3 -c 'import services.scoring.export; import services.scoring.trust_graph; import services.scoring.confidence; import services.scoring.calculators; import services.scoring.rubric; import services.scoring.normalization; import services.scoring.gates; import services.scoring.equity; import services.scoring.implementation_quality; import services.scoring.equity_community'"
check "Import workflow specifications" "python3 -c 'import services.workflow_specs'"
echo ""

# 2. CLI parsers
echo "[2/3] CLI parser validation..."
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
check "capital efficiency agent CLI --help" "python3 -m services.agents.capital_efficiency_agent --help"
check "commons agent CLI --help" "python3 -m services.agents.commons_agent --help"
check "GNH agent CLI --help" "python3 -m services.agents.gnh_agent --help"
check "regenerator agent CLI --help" "python3 -m services.agents.regenerator_agent --help"
check "open source capitalist agent CLI --help" "python3 -m services.agents.open_source_capitalist_agent --help"
check "kokonut commons agent CLI --help" "python3 -m services.agents.kokonut_commons_agent --help"
check "bio factory agent CLI --help" "python3 -m services.agents.bio_factory_agent --help"
check "EBF scorecard agent CLI --help" "python3 -m services.agents.ebf_scorecard_agent --help"
check "EBF evidence gap agent CLI --help" "python3 -m services.agents.ebf_evidence_gap_agent --help"
check "EBF calibration agent CLI --help" "python3 -m services.agents.ebf_calibration_agent --help"
check "spreadsheet bridge CLI --help" "python3 -m services.export.spreadsheet_bridge --help"
check "EBF scoring CLI --help" "python3 -m services.scoring --help"
check "workflow specs CLI --help" "python3 -m services.workflow_specs --help"
echo ""

# 3. TypeScript extension build
echo "[3/3] TypeScript extension build..."
if ! command -v npm >/dev/null 2>&1; then
    echo "  ✗ npm is required for the TypeScript extension build"
    FAIL=$((FAIL + 1))
else
    cd "$PROJECT_DIR/extensions/kokonut-hooks"
    check "npm ci" "npm ci --no-audit --no-fund"
    check "npm run build" "npm run build"
    cd "$PROJECT_DIR"
fi
echo ""

# Summary
echo "=== Results ==="
echo "  Pass: $PASS"
echo "  Fail: $FAIL"

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "  All fast-fail CI checks passed ✓"
    exit 0
else
    echo ""
    echo "  $FAIL check(s) failed"
    exit 1
fi
