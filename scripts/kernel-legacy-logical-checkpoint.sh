#!/usr/bin/env bash
# Capture all databases/globals from the isolated legacy PostgreSQL recovery clone.
set -euo pipefail
umask 077
if [ "$#" -ne 2 ]; then
    echo "Usage: bash scripts/kernel-legacy-logical-checkpoint.sh NEW_DIRECTORY AGE_RECIPIENT" >&2
    exit 2
fi
destination="$1"
recipient="$2"
container=kokonut-kernel-recovery-legacy-postgres
state=$(docker inspect "$container" --format '{{.State.Status}} {{.HostConfig.NetworkMode}}')
if [ "$state" != 'running none' ]; then
    echo "Require the running, no-network legacy recovery clone" >&2
    exit 1
fi
mkdir -m 700 "$destination"
trap 'echo "Incomplete encrypted checkpoint retained" >&2' ERR
docker inspect "$container" --format '{{.Image}}' > "$destination/database-image.txt"
databases=$(docker exec "$container" psql -X -qAt -v ON_ERROR_STOP=1 \
    -U kokonut -d postgres -c 'SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname')
while IFS= read -r database; do
    if [[ ! "$database" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "Unexpected database identifier; refusing incomplete scope" >&2
        exit 1
    fi
    output="$destination/$database.dump.age"
    docker exec "$container" pg_dump -U kokonut -d "$database" \
        --format=custom --no-owner --no-privileges \
        | age -r "$recipient" -o "$output.partial"
    mv "$output.partial" "$output"
done <<< "$databases"
docker exec "$container" pg_dumpall -U kokonut --globals-only \
    | age -r "$recipient" -o "$destination/globals.sql.age.partial"
mv "$destination/globals.sql.age.partial" "$destination/globals.sql.age"
python3 - "$destination" <<'PY'
import datetime
import hashlib
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
files = []
for path in sorted(directory.glob("*.age")):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    files.append({"file": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
manifest = {
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source": "kokonut-kernel-recovery-legacy-postgres",
    "source_image": (directory / "database-image.txt").read_text().strip(),
    "files": files,
    "scope": "All non-template databases; dumps omit grants/ownership. Globals encrypted separately. Not a coordinated live-cluster snapshot.",
    "restore_rehearsed": False,
}
(directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY
echo "Encrypted logical checkpoint captured; restore pending"
