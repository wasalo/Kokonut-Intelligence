#!/usr/bin/env bash
# Build, but never publish or start, the Kernel app and PostGIS OCI image pairs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

command -v docker >/dev/null || { echo "docker CLI is required" >&2; exit 2; }
docker buildx version >/dev/null 2>&1 || {
    echo "Docker Buildx is required (install docker-buildx-plugin)" >&2
    exit 2
}

python3 scripts/check-kernel-release-inputs.py

BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kokonut-kernel-multiarch.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT
umask 077

readarray -t POSTGIS_ARGS < <(python3 - <<'PY'
import json
from pathlib import Path
record = json.loads(Path("config/kernel/release-input-lock.json").read_text())
print(record["postgis_packages"]["POSTGIS_PACKAGE_VERSION"])
print(record["postgis_packages"]["POSTGIS_SCRIPTS_VERSION"])
PY
)

# OCI archives are temporary verification outputs; no image is loaded, tagged,
# pushed, or deployed. The Buildx builder must support linux/amd64 and arm64.
docker buildx build \
    --pull \
    --no-cache \
    --platform linux/amd64,linux/arm64 \
    --target kernel \
    --output "type=oci,dest=$BUILD_DIR/kernel-app.oci.tar" \
    --file Dockerfile.kernel \
    .
python3 scripts/check-kernel-release-inputs.py \
    --application-oci "$BUILD_DIR/kernel-app.oci.tar"
rm -f "$BUILD_DIR/kernel-app.oci.tar"

# Verify the optional ClickHouse client profile has the same locked platform
# support. This is the same app target with its full superset lock selected.
docker buildx build \
    --pull \
    --no-cache \
    --platform linux/amd64,linux/arm64 \
    --target kernel \
    --build-arg KOKONUT_CLICKHOUSE=true \
    --output "type=oci,dest=$BUILD_DIR/kernel-clickhouse-app.oci.tar" \
    --file Dockerfile.kernel \
    .
python3 scripts/check-kernel-release-inputs.py \
    --application-oci "$BUILD_DIR/kernel-clickhouse-app.oci.tar"
rm -f "$BUILD_DIR/kernel-clickhouse-app.oci.tar"

docker buildx build \
    --pull \
    --no-cache \
    --platform linux/amd64,linux/arm64 \
    --target kernel-postgis \
    --build-arg "POSTGIS_PACKAGE_VERSION=${POSTGIS_ARGS[0]}" \
    --build-arg "POSTGIS_SCRIPTS_VERSION=${POSTGIS_ARGS[1]}" \
    --output "type=oci,dest=$BUILD_DIR/kernel-postgis.oci.tar" \
    --file Dockerfile.kernel-postgis \
    .
python3 scripts/check-kernel-release-inputs.py \
    --postgis-oci "$BUILD_DIR/kernel-postgis.oci.tar"
