#!/usr/bin/env bash
# Fork rehearsal — simulates deployment on a Chiado fork.
# Requires: foundry, CHIADO_RPC_URL or defaults to public Chiado RPC.
set -euo pipefail

export PATH="$HOME/.foundry/bin:$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONTRACTS_DIR="$REPO_ROOT/contracts"
REPORT_DIR="$REPO_ROOT/rehearsal-reports"
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT="$REPORT_DIR/rehearsal-$TIMESTAMP.md"

CHIADO_RPC="${CHIADO_RPC_URL:-https://rpc.chiadochain.net}"
BLOCK_TAG="${BLOCK_TAG:-latest}"

echo "# Fork Rehearsal Report" > "$REPORT"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$REPORT"
echo "RPC: $CHIADO_RPC" >> "$REPORT"
echo "" >> "$REPORT"

EXIT_CODE=0

echo "=== Forking Chiado at $BLOCK_TAG ==="
echo "RPC: $CHIADO_RPC"

# 1. Fork and run all Solidity tests
echo "" >> "$REPORT"
echo "## Solidity Tests on Fork" >> "$REPORT"
echo "" >> "$REPORT"

echo "--- Running forge test on Chiado fork ---"
cd "$CONTRACTS_DIR"
if forge test --fork-url "$CHIADO_RPC" --fork-block-number "$BLOCK_TAG" \
    -vv --gas-report 2>&1 | tee /tmp/fork-test.log; then
    echo "PASS: All tests passed on fork" | tee -a "$REPORT"
else
    echo "FAIL: Tests failed on fork" | tee -a "$REPORT"
    EXIT_CODE=1
fi

# 2. Check deployment script compilation
echo "" >> "$REPORT"
echo "## Deployment Script Compilation" >> "$REPORT"
echo "" >> "$REPORT"

echo "--- Building deployment scripts ---"
if forge build --sizes 2>&1 | tee /tmp/fork-build.log; then
    echo "PASS: Build succeeded" | tee -a "$REPORT"
else
    echo "FAIL: Build failed" | tee -a "$REPORT"
    EXIT_CODE=1
fi

# 3. Dry-run deployment script (check linking, no state changes)
echo "" >> "$REPORT"
echo "## Deployment Dry Run" >> "$REPORT"
echo "" >> "$REPORT"

echo "--- Checking DeployKokonutGuildProtocol ---"
if forge script script/DeployKokonutGuildProtocol.s.sol \
    --fork-url "$CHIADO_RPC" \
    --sender 0x0000000000000000000000000000000000000001 \
    --resume 2>&1 | tee /tmp/fork-deploy.log; then
    echo "PASS: DeployKokonutGuildProtocol dry run succeeded" | tee -a "$REPORT"
else
    echo "FAIL: DeployKokonutGuildProtocol dry run failed" | tee -a "$REPORT"
    EXIT_CODE=1
fi

echo "--- Checking DeployKokonutGuildPoints ---"
if forge script script/DeployKokonutGuildPoints.s.sol \
    --fork-url "$CHIADO_RPC" \
    --sender 0x0000000000000000000000000000000000000001 \
    --resume 2>&1 | tee -a /tmp/fork-deploy.log; then
    echo "PASS: DeployKokonutGuildPoints dry run succeeded" | tee -a "$REPORT"
else
    echo "FAIL: DeployKokonutGuildPoints dry run failed" | tee -a "$REPORT"
    EXIT_CODE=1
fi

echo "--- Checking DeployKokonutResolver ---"
if forge script script/DeployKokonutResolver.s.sol \
    --fork-url "$CHIADO_RPC" \
    --sender 0x0000000000000000000000000000000000000001 \
    --resume 2>&1 | tee -a /tmp/fork-deploy.log; then
    echo "PASS: DeployKokonutResolver dry run succeeded" | tee -a "$REPORT"
else
    echo "FAIL: DeployKokonutResolver dry run failed" | tee -a "$REPORT"
    EXIT_CODE=1
fi

# 4. Gas snapshot
echo "" >> "$REPORT"
echo "## Gas Snapshot" >> "$REPORT"
echo "" >> "$REPORT"

echo "--- Generating gas snapshot ---"
if forge snapshot --fork-url "$CHIADO_RPC" 2>&1 | tee /tmp/fork-gas.log; then
    echo "PASS: Gas snapshot generated" >> "$REPORT"
else
    echo "WARN: Gas snapshot failed" >> "$REPORT"
fi

# Summary
echo "" >> "$REPORT"
echo "## Summary" >> "$REPORT"
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "Result: **PASS**" >> "$REPORT"
    echo ""
    echo "=== Fork rehearsal: PASS ==="
else
    echo "Result: **FAIL**" >> "$REPORT"
    echo ""
    echo "=== Fork rehearsal: FAIL ==="
fi

echo "Report saved to: $REPORT"
exit $EXIT_CODE
