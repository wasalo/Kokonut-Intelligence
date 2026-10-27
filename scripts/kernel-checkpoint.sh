#!/usr/bin/env bash
# Scoped PostgreSQL checkpoint; intentionally excludes external/provider state.
set -euo pipefail
umask 077
if [ "$#" -ne 3 ]; then
    echo "Usage: bash scripts/kernel-checkpoint.sh SOURCE_CONTAINER NEW_DIRECTORY AGE_RECIPIENT" >&2
    exit 2
fi
container="$1"
destination="$2"
recipient="$3"
case "$container" in
    kokonut-kernel-portability-database-1|kokonut-kernel-candidate-database-1|kokonut-intelligence-database-1) ;;
    kokonut-kernel-recovery-fixture-database-1)
        python3 "$(dirname "$0")/kernel-recovery-fixture.py" >/dev/null ;;
    *)
        if [[ "$container" =~ ^(kokonut-kernel-recovery-fixture-[0-9a-f]{8})-database-1$ ]]; then
            KOKONUT_RECOVERY_FIXTURE_PROJECT="${BASH_REMATCH[1]}" \
                python3 "$(dirname "$0")/kernel-recovery-fixture.py" >/dev/null
        else
            echo "Unsupported source container" >&2
            exit 2
        fi
        ;;
esac
command -v age >/dev/null
command -v docker >/dev/null
# Existing directories are never reused, including incomplete checkpoints.
mkdir -m 700 "$destination"
trap 'echo "Checkpoint incomplete; retain directory for diagnosis" >&2' ERR
docker inspect "$container" --format '{{.Image}}' > "$destination/database-image.txt"
docker exec "$container" pg_dump -U kokonut -d kokonut_intelligence \
    --format=custom --no-owner --no-privileges \
    | age -r "$recipient" -o "$destination/postgres.dump.age.partial"
mv "$destination/postgres.dump.age.partial" "$destination/postgres.dump.age"
python3 - "$destination" "$container" <<'PY'
import datetime
import hashlib
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
archive = directory / "postgres.dump.age"
digest = hashlib.sha256()
with archive.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
manifest = {
    "format": 1,
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source_container": sys.argv[2],
    "database_image": (directory / "database-image.txt").read_text().strip(),
    "database": "kokonut_intelligence",
    "archive": archive.name,
    "sha256": digest.hexdigest(),
    "bytes": archive.stat().st_size,
    "scope": "Single PostgreSQL database; ownership/grants excluded. No roles, other databases, volumes or external media.",
    "restore_rehearsed": False,
}
(directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY
echo "Encrypted scoped checkpoint created; restore not rehearsed."
