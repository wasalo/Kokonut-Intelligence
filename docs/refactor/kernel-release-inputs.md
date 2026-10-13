# Kernel release-input and architecture build gate

The GitHub Actions `CI` job verifies a reviewed build-input lock and builds the
default app, ClickHouse-enabled app, and PostGIS targets as multi-platform OCI
archives for `linux/amd64` and `linux/arm64`. The gate runs on main updates and
pull requests.
It uses `--pull --no-cache` so paired builds resolve current locked inputs. It
does not load images into the host daemon, start containers, alter Compose
projects, publish images, or touch database volumes.

## Locked inputs

`config/kernel/release-input-lock.json` pins SHA-256 digests for the application
and database base manifests, the Kernel Dockerfiles, the direct Python
requirement manifests and generated locks for the runtime and optional
ClickHouse profile, the Debian/PGDG apt source definitions, and the verified
PostGIS package catalog. The catalog records the exact PostGIS runtime and
script package versions, the Debian snapshot timestamp, and their verified
amd64/arm64 availability.

The gate extracts `python-packages.json` from each default and ClickHouse app
platform and requires exact package name/version parity between the two
architectures. It also checks that both database image variants contain the
locked PostGIS package versions. Platform identity comes from Linux AMD64/ARM64
OCI index descriptors. The checker recursively walks nested indexes and falls
back to image config metadata when an image descriptor omits platform labels;
non-image attestations are skipped. OCI archive digests and platform
descriptors are reported in the CI log; temporary archives are removed at job
exit.

## Current limits

The source requirement files retain compatibility ranges, while the Kernel
runtime and optional ClickHouse lockfiles pin resolved versions with artifact
hashes. The Docker build installs the selected lock with pip hash checking
enabled. Regenerate locks with the pinned pip-tools version and review package
changes before updating the release-input manifest. The lock does not pin the
Python base image's bundled pip independently from its digest.

PostGIS package resolution now uses a timestamped Debian Bookworm snapshot and
the PGDG archive, with exact versions for the two selected PostGIS packages.
The source files and timestamp are covered by the release-input lock. The
release gate verifies the selected PostGIS package versions and compares the
complete installed Debian package inventories across both architectures,
reporting missing or differently versioned packages (up to 50 differences per
failure). It does not certify extension behavior, logical restore, ARM64 runtime,
or Raspberry Pi resource limits. A fresh multi-architecture run is required to
accept the snapshot change. GitHub-hosted runner Docker and Buildx tooling come
from the runner image and are outside the app release lock.

The Debian source uses the official [snapshot service](https://snapshot.debian.org/)
at an explicit UTC timestamp. PGDG's [APT documentation](https://wiki.postgresql.org/wiki/Apt/FAQ)
describes its `-pgdg-snapshot` suite as a development snapshot; this build uses
the released-package archive with exact PostGIS version pins instead.

## Updating inputs

When a source requirement changes, regenerate both Python locks with
`pip-tools==7.6.2`, review the resolved versions and hashes, and update each
changed SHA-256 in the release lock in the same change. Keep both architectures
in the CI build. Do not replace the candidate Compose database image or remove
the ARM64 profile guard based on build success alone.

```sh
python -m pip install pip-tools==7.6.2
pip-compile --generate-hashes --allow-unsafe --resolver=backtracking --strip-extras \
  --output-file requirements/kernel-runtime.lock requirements/kernel-runtime.in
pip-compile --generate-hashes --allow-unsafe --resolver=backtracking --strip-extras \
  --constraint requirements/kernel-runtime.lock \
  --output-file requirements/kernel-clickhouse.lock requirements/kernel-clickhouse.in
```

Run the same gate locally with:

```sh
bash scripts/build-kernel-multiarch.sh
```

This requires Docker Buildx, registry access for pinned images/packages, and an
emulated or native ARM64 builder. The repository-owner local candidate and the
legacy stack are not inputs to this command.
