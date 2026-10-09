#!/usr/bin/env bash
# Fail if any Dockerfile `FROM` or Compose `image:` reference is not pinned by
# an explicit @sha256 digest. Runtime image pinning prevents silent registry
# manifest drift and supply-chain tampering.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

violations=0

# Dockerfile FROM lines: require @sha256 after the image ref.
while IFS= read -r line; do
    file=${line%%:*}
    rest=${line#*:}
    # Only examine FROM lines that are not comments/continuations.
    if [[ "$rest" =~ ^[[:space:]]*FROM[[:space:]]+ ]]; then
        image_ref=$(echo "$rest" | sed -E 's/^[[:space:]]*FROM[[:space:]]+//; s/[[:space:]].*$//')
        # Skip ARG-driven refs that resolve at build time (none currently).
        if [[ "$image_ref" != *"@sha256:"* ]]; then
            echo "UNPINNED FROM in $file: $image_ref"
            violations=$((violations + 1))
        fi
    fi
done < <(git grep -nE '^[[:space:]]*FROM[[:space:]]' -- 'Dockerfile*' ':!*.md')

# Compose image: lines: require @sha256 after the tag.
while IFS= read -r line; do
    file=${line%%:*}
    rest=${line#*:}
    if [[ "$rest" =~ ^[[:space:]]*image:[[:space:]]+ ]]; then
        image_ref=$(echo "$rest" | sed -E 's/^[[:space:]]*image:[[:space:]]+//; s/[[:space:]]*$//')
        if [[ "$image_ref" != *"@sha256:"* ]]; then
            echo "UNPINNED image in $file: $image_ref"
            violations=$((violations + 1))
        fi
    fi
done < <(git grep -nE '^[[:space:]]*image:[[:space:]]' -- 'docker-compose*.yml' ':!*.md')

if [ "$violations" -ne 0 ]; then
    echo "FAILED: $violations unpinned image reference(s) found."
    exit 1
fi

echo "OK: all Docker image references are digest-pinned."
