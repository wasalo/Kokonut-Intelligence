#!/usr/bin/env bash
# Decrypt .env.sops and export all variables into the current shell.
# Usage: source scripts/load-secrets.sh
#    or: . scripts/load-secrets.sh
#
# Requires: sops (brew install sops)
# Key location: ~/.config/sops/age/keys.txt or ~/Library/Application Support/sops/age/keys.txt
set -euo pipefail

# Find the project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SOPS_FILE="${PROJECT_ROOT}/.env.sops"

if [ ! -f "$SOPS_FILE" ]; then
    echo "ERROR: $SOPS_FILE not found." >&2
    echo "Copy .env.sops.example to .env.sops and encrypt with: sops -e .env > .env.sops" >&2
    return 1 2>/dev/null || exit 1
fi

# Check sops is installed
if ! command -v sops &>/dev/null; then
    echo "ERROR: sops not found. Install with: brew install sops" >&2
    return 1 2>/dev/null || exit 1
fi

# Decrypt and export each variable
eval "$(sops -d --input-type dotenv --output-type dotenv "$SOPS_FILE")"
