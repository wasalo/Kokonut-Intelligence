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

# SOPS does not discover the repository-documented macOS key path in every
# installation. Set it automatically when the local key is present.
if [ -z "${SOPS_AGE_KEY_FILE:-}" ] && [ -f "$HOME/.config/sops/age/keys.txt" ]; then
    export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
fi

# Decrypt into a restrictive temporary file, then parse assignments without
# evaluating shell code from the encrypted payload.
umask 077
DECRYPTED_FILE="$(mktemp "${TMPDIR:-/tmp}/kokonut-env.XXXXXX")"
cleanup() {
    rm -f "$DECRYPTED_FILE"
}
trap cleanup EXIT

if ! sops -d --input-type dotenv --output-type dotenv "$SOPS_FILE" > "$DECRYPTED_FILE"; then
    echo "ERROR: unable to decrypt $SOPS_FILE" >&2
    return 1 2>/dev/null || exit 1
fi

while IFS= read -r line || [ -n "$line" ]; do
    line="${line#${line%%[![:space:]]*}}"
    line="${line%${line##*[![:space:]]}}"
    [ -z "$line" ] && continue
    [[ "$line" == \#* ]] && continue

    if [[ "$line" == export\ * ]]; then
        line="${line#export }"
    fi
    if [[ "$line" != *=* ]]; then
        echo "ERROR: invalid dotenv assignment" >&2
        return 1 2>/dev/null || exit 1
    fi

    key="${line%%=*}"
    value="${line#*=}"
    key="${key#${key%%[![:space:]]*}}"
    key="${key%${key##*[![:space:]]}}"
    if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "ERROR: invalid dotenv variable name: $key" >&2
        return 1 2>/dev/null || exit 1
    fi
    if [[ "$value" == \"*\" && "$value" == *\" ]] ||
       [[ "$value" == \'*\' && "$value" == *\' ]]; then
        value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
done < "$DECRYPTED_FILE"
