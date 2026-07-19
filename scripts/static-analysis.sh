#!/usr/bin/env bash
# Static analysis gate for Solidity contracts and Python services.
set -euo pipefail

CONTRACTS_DIR="contracts"
EXIT_CODE=0
export PATH="$HOME/Library/Python/3.9/bin:$HOME/.cargo/bin:$PATH"

echo "=== Slither (Solidity) ==="
if ! command -v slither >/dev/null 2>&1; then
    echo "FAIL: slither not found"
    EXIT_CODE=1
else
    set +e
    slither "$CONTRACTS_DIR" --filter-paths "lib/|node_modules/" \
        --json /tmp/slither-results.json 2>&1 | tee /tmp/slither.log
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
    "$SEMGREP" scan --config auto --severity ERROR \
        --sarif --output /tmp/semgrep-gate.sarif \
        services/ contracts/src/ contracts/script/ 2>&1 | tee /tmp/semgrep.log
    SEMGREP_STATUS=${PIPESTATUS[0]}
    set -e
    if [ "$SEMGREP_STATUS" -ne 0 ] && [ ! -s /tmp/semgrep-gate.sarif ]; then
        echo "FAIL: Semgrep execution failed"
        EXIT_CODE=1
    fi
    if [ -s /tmp/semgrep-gate.sarif ]; then
        set +e
        ERRORS=$(python3 -c '
import json
data = json.load(open("/tmp/semgrep-gate.sarif"))
results = data.get("runs", [{}])[0].get("results", [])
false_positives = {"python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query"}
our = [r for r in results if any(
    p in r.get("locations", [{}])[0].get("physicalLocation", {}).get("artifactLocation", {}).get("uri", "")
    for p in ("services/", "contracts/src/", "contracts/script/")
) and r.get("ruleId", "") not in false_positives]
for result in our:
    location = result.get("locations", [{}])[0].get("physicalLocation", {})
    print("  {rule}: {uri}".format(
        rule=result.get("ruleId", "unknown"),
        uri=location.get("artifactLocation", {}).get("uri", "")))
print(f"Total true-positive findings: {len(our)}")
' 2>&1)
        PARSE_STATUS=$?
        set -e
        if [ "$PARSE_STATUS" -ne 0 ]; then
            echo "FAIL: Could not parse Semgrep results"
            EXIT_CODE=1
        else
            echo "$ERRORS"
            if echo "$ERRORS" | grep -q "Total true-positive findings: [1-9]"; then
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
