#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

python3 -m pip install --disable-pip-version-check --no-cache-dir pip-tools==7.6.2
pip-compile \
  --allow-unsafe \
  --resolver=backtracking \
  --strip-extras \
  --output-file "$WORK/ml-anomaly-runtime.resolved.txt" \
  "$ROOT/requirements/ml-anomaly-runtime.in"

mkdir -p "$WORK/wheels-amd64" "$WORK/wheels-arm64"
python3 -m pip download \
  --disable-pip-version-check \
  --no-cache-dir \
  --only-binary=:all: \
  --no-deps \
  --platform=manylinux_2_28_x86_64 \
  --platform=manylinux2014_x86_64 \
  --python-version=3.11 \
  --implementation=cp \
  --abi=cp311 \
  --dest "$WORK/wheels-amd64" \
  -r "$WORK/ml-anomaly-runtime.resolved.txt"
python3 -m pip download \
  --disable-pip-version-check \
  --no-cache-dir \
  --only-binary=:all: \
  --no-deps \
  --platform=manylinux_2_28_aarch64 \
  --platform=manylinux2014_aarch64 \
  --python-version=3.11 \
  --implementation=cp \
  --abi=cp311 \
  --dest "$WORK/wheels-arm64" \
  -r "$WORK/ml-anomaly-runtime.resolved.txt"

python3 "$ROOT/scripts/generate_ml_anomaly_runtime_lock.py" \
  --resolved "$WORK/ml-anomaly-runtime.resolved.txt" \
  --amd64-wheels "$WORK/wheels-amd64" \
  --arm64-wheels "$WORK/wheels-arm64" \
  --output "$ROOT/requirements/ml-anomaly-runtime.lock"
