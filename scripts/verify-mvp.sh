#!/usr/bin/env bash
# ============================================================
# verify-mvp.sh — Validate MVP definition of done on local DB
# ============================================================
set -euo pipefail

python3 -m tests.test_mvp_done
