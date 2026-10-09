#!/usr/bin/env bash
# Verify checkpoint manifest and encrypted backup artifacts.
set -euo pipefail

CHECKPOINT="${1:-}"
if [ -z "$CHECKPOINT" ] || [ ! -f "$CHECKPOINT/manifest.json" ]; then
    echo "Usage: $0 <checkpoint-directory>" >&2
    exit 2
fi

python3 - "$CHECKPOINT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

checkpoint = Path(sys.argv[1])
manifest = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
for item in manifest.get("files", []):
    path = checkpoint / item["path"]
    if not path.is_file():
        raise SystemExit(f"Missing checkpoint file: {item['path']}")
    if path.stat().st_size == 0:
        raise SystemExit(f"Empty checkpoint file: {item['path']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit(f"Checksum mismatch: {item['path']}")
PY

echo "Backup checkpoint is valid: $CHECKPOINT"
