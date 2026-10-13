# Kernel release-input and architecture build gate

The GitHub Actions `CI` job verifies a reviewed build-input lock and builds the
minimal application and PostGIS targets as multi-platform OCI archives for
`linux/amd64` and `linux/arm64`. The gate runs on main updates and pull requests.
It uses `--pull --no-cache` so paired builds resolve current locked inputs. It
does not load images into the host daemon, start containers, alter Compose
projects, publish images, or touch database volumes.

## Locked inputs

`config/kernel/release-input-lock.json` pins SHA-256 digests for the application
and database base manifests, the Kernel Dockerfiles, the four direct Python
requirement manifests used by the minimal image, and the verified PostGIS
package catalog. The catalog records the exact PostGIS runtime and script
package versions and their verified amd64/arm64 availability.

The gate extracts `python-packages.json` from each application platform and
requires exact package name/version parity between the two architectures. It
also checks that both database image variants contain the locked PostGIS
package versions. Platform identity comes from Linux AMD64/ARM64 OCI index
descriptors. The checker recursively walks nested indexes and falls back to
image config metadata when an image descriptor omits platform labels;
non-image attestations are skipped. OCI archive digests and platform
descriptors are reported in the CI log; temporary archives are removed at job
exit.

## Current limits

The Python requirement files still use ranges. Their file contents are locked,
but their resolved dependency versions and wheel hashes are not locked across
builds. The CI pair comparison catches an amd64/arm64 mismatch in one run, not
an update to a newer version shared by both architectures. A future release
lock must use a reviewed cross-platform Python lock with hashes.

The PostGIS apt packages are version-pinned, but apt repository snapshots and
transitive Debian package versions are not locked. GitHub-hosted runner Docker
and Buildx tooling come from the runner image and are outside the app release
lock. The CI gate validates the selected PostGIS package versions; it
does not certify extension behavior,
logical restore, ARM64 runtime, or Raspberry Pi resource limits.

## Updating inputs

When a locked Dockerfile, requirement manifest, or PostGIS catalog changes,
review the dependency/base-image change and update its SHA-256 in the release
lock in the same change. Keep both architectures in the CI build. Do not replace
the candidate Compose database image or remove the ARM64 profile guard based on
build success alone.

Run the same gate locally with:

```sh
bash scripts/build-kernel-multiarch.sh
```

This requires Docker Buildx, registry access for pinned images/packages, and an
emulated or native ARM64 builder. The repository-owner local candidate and the
legacy stack are not inputs to this command.
