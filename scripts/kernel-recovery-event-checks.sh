#!/usr/bin/env bash
# Mutates the dedicated synthetic fixture; retain its checkpoint before running.
set -euo pipefail
repository=$(cd "$(dirname "$0")/.." && pwd)
cd "$repository"
python3 scripts/kernel-recovery-fixture.py
# Caller supplies POSTGRES_PASSWORD from the existing encrypted secret loader.
docker compose -f docker-compose.kernel-recovery-fixture.yml run --rm -T \
    --no-deps --entrypoint python3 operator - \
    < scripts/fixtures/kernel-recovery-event-checks.py
