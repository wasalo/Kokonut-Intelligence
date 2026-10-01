#!/usr/bin/env bash
# Restrict the host-encrypted environment to root and the age-key group.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    printf 'Usage: %s AGE_KEY_FILE ENCRYPTED_ENV_FILE\n' "$(basename "$0")" >&2
    exit 2
fi

AGE_KEY_FILE="$1"
ENCRYPTED_ENV_FILE="$2"

if [ ! -f "$AGE_KEY_FILE" ]; then
    printf 'ERROR: age key file not found\n' >&2
    exit 1
fi
if [ ! -f "$ENCRYPTED_ENV_FILE" ]; then
    printf 'ERROR: encrypted environment file not found\n' >&2
    exit 1
fi

AGE_KEY_GID="$(stat -c '%g' -- "$AGE_KEY_FILE")"
if [[ ! "$AGE_KEY_GID" =~ ^[0-9]+$ ]]; then
    printf 'ERROR: could not determine age-key group ID\n' >&2
    exit 1
fi

# The deployment helper runs as root. Keep the ciphertext root-owned while
# granting read-only access to the same group that owns the private age key,
# which is also the group used by the Staging backup cron account.
chgrp -- "$AGE_KEY_GID" "$ENCRYPTED_ENV_FILE"
chmod 0640 -- "$ENCRYPTED_ENV_FILE"
