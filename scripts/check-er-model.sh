#!/usr/bin/env bash
set -euo pipefail

# Read-only ER risk report. The command intentionally does not fail on known
# legacy patterns until their migrations have an explicit replacement plan.
python3 -m services.schema_introspection --format markdown
