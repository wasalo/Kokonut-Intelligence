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
umask 077
BUILDER_NAME="kokonut-kernel-release-${BUILD_DIR##*.}"
BUILDER_CREATED=false

cleanup() {
    local status=$?
    trap - EXIT
    if [ "$BUILDER_CREATED" = true ]; then
        docker buildx rm --force "$BUILDER_NAME" >/dev/null 2>&1 || {
            if [ "$status" -eq 0 ]; then status=1; fi
        }
    fi
    rm -rf "$BUILD_DIR" || {
        if [ "$status" -eq 0 ]; then status=1; fi
    }
    exit "$status"
}
trap cleanup EXIT

readarray -t POSTGIS_ARGS < <(python3 - <<'PY'
import json
from pathlib import Path
record = json.loads(Path("config/kernel/release-input-lock.json").read_text())
print(record["postgis_packages"]["POSTGIS_PACKAGE_VERSION"])
print(record["postgis_packages"]["POSTGIS_SCRIPTS_VERSION"])
PY
)

# Use a fresh builder with no imported cache. Its cache is temporary and shared
# only by the sequential builds below, avoiding repeated QEMU installs of the
# same locked dependency layers. --pull refreshes digest-pinned base images;
# changed lockfiles and Dockerfile inputs invalidate their affected layers.
docker buildx create --name "$BUILDER_NAME" --driver docker-container >/dev/null
BUILDER_CREATED=true
docker buildx inspect "$BUILDER_NAME" --bootstrap >/dev/null

# OCI archives are temporary verification outputs; no image is loaded, tagged,
# pushed, or deployed. The Buildx builder must support linux/amd64 and arm64.
docker buildx build \
    --builder "$BUILDER_NAME" \
    --pull \
    --platform linux/amd64,linux/arm64 \
    --target kernel \
    --output "type=oci,dest=$BUILD_DIR/kernel-app.oci.tar" \
    --file Dockerfile.kernel \
    .
python3 scripts/check-kernel-release-inputs.py \
    --application-oci "$BUILD_DIR/kernel-app.oci.tar"
rm -f "$BUILD_DIR/kernel-app.oci.tar"

# Verify the new opt-in minimal dependency closure on both architectures. The
# base/minimal/edge profiles above continue using the existing full runtime.
docker buildx build \
    --builder "$BUILDER_NAME" \
    --pull \
    --platform linux/amd64,linux/arm64 \
    --target kernel-core \
    --output "type=oci,dest=$BUILD_DIR/kernel-core.oci.tar" \
    --file Dockerfile.kernel \
    .
python3 scripts/check-kernel-release-inputs.py \
    --core-oci "$BUILD_DIR/kernel-core.oci.tar"
rm -f "$BUILD_DIR/kernel-core.oci.tar"

# Verify that the optional capability overlays can be composed on the lean
# core for both supported architectures. This also exercises each true build
# argument and checks the exact union of the four hash-locked closures.
docker buildx build \
    --builder "$BUILDER_NAME" \
    --pull \
    --platform linux/amd64,linux/arm64 \
    --target kernel-core \
    --build-arg KOKONUT_CORE_WEB3=true \
    --build-arg KOKONUT_CORE_EXPORTS=true \
    --build-arg KOKONUT_CORE_LOCAL_MEDIA=true \
    --output "type=oci,dest=$BUILD_DIR/kernel-core-capabilities.oci.tar" \
    --file Dockerfile.kernel \
    .
python3 scripts/check-kernel-release-inputs.py \
    --core-capabilities-oci "$BUILD_DIR/kernel-core-capabilities.oci.tar"
rm -f "$BUILD_DIR/kernel-core-capabilities.oci.tar"

# Verify the optional ClickHouse client profile has the same locked platform
# support. This is the same app target with its full superset lock selected.
docker buildx build \
    --builder "$BUILDER_NAME" \
    --pull \
    --platform linux/amd64,linux/arm64 \
    --target kernel \
    --build-arg KOKONUT_CLICKHOUSE=true \
    --output "type=oci,dest=$BUILD_DIR/kernel-clickhouse-app.oci.tar" \
    --file Dockerfile.kernel \
    .
python3 scripts/check-kernel-release-inputs.py \
    --application-oci "$BUILD_DIR/kernel-clickhouse-app.oci.tar"
rm -f "$BUILD_DIR/kernel-clickhouse-app.oci.tar"

# Verify the independently locked optional ML worker on both architectures.
docker buildx build \
    --builder "$BUILDER_NAME" \
    --pull \
    --platform linux/amd64,linux/arm64 \
    --target ml-anomaly \
    --output "type=oci,dest=$BUILD_DIR/kernel-ml-anomaly.oci.tar" \
    --file Dockerfile.kernel \
    .
python3 scripts/check-kernel-release-inputs.py \
    --ml-anomaly-oci "$BUILD_DIR/kernel-ml-anomaly.oci.tar"
rm -f "$BUILD_DIR/kernel-ml-anomaly.oci.tar"

docker buildx build \
    --builder "$BUILDER_NAME" \
    --pull \
    --platform linux/amd64,linux/arm64 \
    --target kernel-postgis \
    --build-arg "POSTGIS_PACKAGE_VERSION=${POSTGIS_ARGS[0]}" \
    --build-arg "POSTGIS_SCRIPTS_VERSION=${POSTGIS_ARGS[1]}" \
    --output "type=oci,dest=$BUILD_DIR/kernel-postgis.oci.tar" \
    --file Dockerfile.kernel-postgis \
    .
python3 scripts/check-kernel-release-inputs.py \
    --postgis-oci "$BUILD_DIR/kernel-postgis.oci.tar"
