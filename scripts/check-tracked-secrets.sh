#!/usr/bin/env bash
set -euo pipefail

PATTERN='-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|"private_key"[[:space:]]*:[[:space:]]*"-----BEGIN|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[0-9A-Za-z-]{20,}|0x[0-9a-fA-F]{64}|sk-[A-Za-z0-9]{20,}|(api[_-]?key|secret|token|passwd|password)[[:space:]]*[:=][[:space:]]*['\''"][A-Za-z0-9/+_=-]{16,}['\''"]'

set +e
matches=$(git grep -IlE -e "$PATTERN" -- . ':!*.md' ':!*.adoc')
grep_status=$?
set -e
if [ "$grep_status" -gt 1 ]; then
    printf '%s\n' "Secret scan failed with git grep status $grep_status." >&2
    exit "$grep_status"
fi

if [ -n "$matches" ]; then
    printf '%s\n' "Tracked secret-like material found in:" >&2
    printf '%s\n' "$matches" >&2
    exit 1
fi

printf '%s\n' "No tracked secret-like material detected."
