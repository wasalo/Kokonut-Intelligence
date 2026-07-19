#!/usr/bin/env bash
# ============================================================
# verify-platform.sh — Validate platform definition of done
# ============================================================
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m tests.test_platform_done
