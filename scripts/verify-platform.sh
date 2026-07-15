#!/usr/bin/env bash
# ============================================================
# verify-platform.sh — Validate platform definition of done
# ============================================================
set -euo pipefail

python3 -m tests.test_platform_done
