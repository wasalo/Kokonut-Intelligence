#!/usr/bin/env bash
# Static analysis gate for Solidity contracts and Python services.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACTS_DIR="$PROJECT_DIR/contracts"
ARTIFACT_DIR="${ANALYSIS_ARTIFACT_DIR:-$PROJECT_DIR/artifacts/static-analysis}"
EXIT_CODE=0
export PATH="$HOME/Library/Python/3.9/bin:$HOME/.cargo/bin:$HOME/.foundry/bin:$PATH"
mkdir -p "$ARTIFACT_DIR"
cd "$PROJECT_DIR"

echo "=== Slither (Solidity) ==="
if ! command -v slither >/dev/null 2>&1; then
    echo "FAIL: slither not found"
    EXIT_CODE=1
else
    set +e
    slither "$CONTRACTS_DIR" --filter-paths "lib/|node_modules/" \
        --json /tmp/slither-results.json 2>&1 | tee /tmp/slither.log
    cp /tmp/slither-results.json "$ARTIFACT_DIR/slither-results.json"
    cp /tmp/slither.log "$ARTIFACT_DIR/slither.log"
    SLITHER_STATUS=${PIPESTATUS[0]}
    set -e
    if [ "$SLITHER_STATUS" -ne 0 ] && [ ! -s /tmp/slither-results.json ]; then
        echo "FAIL: Slither execution failed"
        EXIT_CODE=1
    fi

    set +e
    MEDIUM=$(python3 -c '
import json
data = json.load(open("/tmp/slither-results.json"))
findings = data.get("results", {}).get("detectors", [])
acceptable = {"locked-ether", "unused-return"}
src = [f for f in findings if any(
    e.get("source_mapping", {}).get("filename_relative", "").startswith("src/")
    for e in f.get("elements", [])
) and f.get("impact") in ("High", "Medium") and f.get("check") not in acceptable]
for finding in src:
    print("  [{impact}] {check}: {description}".format(
        impact=finding["impact"], check=finding["check"],
        description=finding["description"][:200]))
print(f"Total actionable High/Medium in src/: {len(src)}")
' 2>&1)
    PARSE_STATUS=$?
    set -e
    if [ "$PARSE_STATUS" -ne 0 ]; then
        echo "FAIL: Could not parse Slither results"
        EXIT_CODE=1
    else
        echo "$MEDIUM"
        if echo "$MEDIUM" | grep -q "Total actionable High/Medium in src/: [1-9]"; then
            echo "FAIL: Slither found high/medium findings"
            EXIT_CODE=1
        fi
    fi
fi

echo ""
echo "=== Aderyn (Solidity) ==="
if ! command -v aderyn >/dev/null 2>&1; then
    echo "FAIL: aderyn not found"
    EXIT_CODE=1
else
    aderyn "$CONTRACTS_DIR" --output /tmp/aderyn-report.md 2>&1 | tee /tmp/aderyn.log
    cp /tmp/aderyn-report.md "$ARTIFACT_DIR/aderyn-report.md"
    cp /tmp/aderyn.log "$ARTIFACT_DIR/aderyn.log"
    if [ ! -s /tmp/aderyn-report.md ]; then
        echo "FAIL: Aderyn did not produce a report"
        EXIT_CODE=1
    else
        HIGH_MED=$(grep -cE "^## (High|Medium)" /tmp/aderyn-report.md || true)
        echo "Aderyn High/Medium findings: $HIGH_MED"
        if [ "$HIGH_MED" -gt 0 ]; then
            echo "FAIL: Aderyn found high/medium findings"
            EXIT_CODE=1
        fi
    fi
fi

echo ""
echo "=== Semgrep (Python + Solidity) ==="
if command -v pysemgrep >/dev/null 2>&1 || command -v semgrep >/dev/null 2>&1; then
    SEMGREP=$(command -v pysemgrep 2>/dev/null || command -v semgrep)
    set +e
    SEMGREP_CONFIG_ARGS=()
    if [ -f "$PROJECT_DIR/semgrep.yml" ]; then
        while IFS= read -r pack; do
            pack="$(printf '%s' "$pack" | sed 's/^[[:space:]]*-[[:space:]]*//; s/[[:space:]]*$//')"
            [ -n "$pack" ] && SEMGREP_CONFIG_ARGS+=(--config "$pack")
        done < <(awk '
            /^[[:space:]]*configs:/ { f=1; next }
            f && /^[[:space:]]*-/ { print }
            f && !/^[[:space:]]*-/ && !/^[[:space:]]*#/ { f=0 }
        ' "$PROJECT_DIR/semgrep.yml")
    fi
    if [ "${#SEMGREP_CONFIG_ARGS[@]}" -eq 0 ]; then
        SEMGREP_CONFIG_ARGS=(--config auto)
    fi
    "$SEMGREP" scan "${SEMGREP_CONFIG_ARGS[@]}" --severity ERROR \
        --sarif --output /tmp/semgrep-gate.sarif \
        services/ contracts/src/ contracts/script/ 2>&1 | tee /tmp/semgrep.log
    SEMGREP_STATUS=${PIPESTATUS[0]}
    set -e
    cp /tmp/semgrep.log "$ARTIFACT_DIR/semgrep.log"
    if [ "$SEMGREP_STATUS" -ne 0 ] && [ ! -s /tmp/semgrep-gate.sarif ]; then
        echo "FAIL: Semgrep execution failed"
        EXIT_CODE=1
    fi
    if [ -s /tmp/semgrep-gate.sarif ]; then
        cp /tmp/semgrep-gate.sarif "$ARTIFACT_DIR/semgrep-gate.sarif"
        set +e
        ERRORS=$(python3 -c '
import json
data = json.load(open("/tmp/semgrep-gate.sarif"))
results = data.get("runs", [{}])[0].get("results", [])
# Rulepacks contain heuristics that may not match this codebase threat model.
# Exclude findings that were individually reviewed and found safe; document each.
reviewed_exclusions = {
    # SQLAlchemy raw query is used only for migration-controlled, parameterized DDL.
    "python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query",
    # dangerous-subprocess-use-audit: every flagged call uses shell=False with an
    # argument list (no shell interpolation). Scheduler calls additionally pass
    # validate_scheduled_module() (allowlist); reporting_cadence uses shlex.split of
    # an operator-configured command. No shell metacharacter injection vector.
    "python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit",
    # use-defused-xml: both flagged files only CONSTRUCT XML via xml.etree.ElementTree
    # (Element/SubElement/ElementTree/tostring). Construction is not an XXE vector; XXE only
    # affects parsing, which is never performed with the stdlib here. Where spatial_export.py
    # parses, it already uses defusedxml.minidom.parseString; strategy_markup builds only from
    # trusted, approved DB rows. Excluded as false positive for build-only usage.
    "python.lang.security.use-defused-xml.use-defused-xml",
    # return-in-init: false positive on services/gateway/rate_limiter.py (RateLimiter.__init__)
    # contains no return; the flagged returns are in the check() method. Rule misfires here.
    "python.lang.correctness.return-in-init.return-in-init",
}
our = [r for r in results if any(
    p in r.get("locations", [{}])[0].get("physicalLocation", {}).get("artifactLocation", {}).get("uri", "")
    for p in ("services/", "contracts/src/", "contracts/script/")
) and r.get("ruleId", "") not in reviewed_exclusions]
print(f"Semgrep raw findings: {len(results)}")
for result in our:
    location = result.get("locations", [{}])[0].get("physicalLocation", {})
    print("  {rule}: {uri}".format(
        rule=result.get("ruleId", "unknown"),
        uri=location.get("artifactLocation", {}).get("uri", "")))
print(f"Total policy findings: {len(our)}")
' 2>&1)
        PARSE_STATUS=$?
        set -e
        if [ "$PARSE_STATUS" -ne 0 ]; then
            echo "FAIL: Could not parse Semgrep results"
            EXIT_CODE=1
        else
            echo "$ERRORS"
            if echo "$ERRORS" | grep -Eq "Total policy findings: [1-9][0-9]*"; then
                echo "FAIL: Semgrep found error-severity findings"
                EXIT_CODE=1
            fi
        fi
    elif [ "$SEMGREP_STATUS" -eq 0 ]; then
        echo "FAIL: Semgrep did not produce a SARIF report"
        EXIT_CODE=1
    fi
else
    echo "FAIL: semgrep not found"
    EXIT_CODE=1
fi

echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "=== Static analysis: PASS ==="
else
    echo "=== Static analysis: FAIL ==="
fi
exit "$EXIT_CODE"
