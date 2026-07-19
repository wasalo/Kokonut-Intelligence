#!/usr/bin/env bash
set -euo pipefail

missing=0
for tool in python3 node npm forge slither aderyn semgrep; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: required CI tool is missing: $tool" >&2
        missing=1
    fi
done

if [ "$missing" -ne 0 ]; then
    exit 1
fi

python3 --version
node --version
npm --version
forge --version
slither --version
aderyn --version
semgrep --version
