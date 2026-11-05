# Refactor finalization work queue

This queue groups the existing acceptance requirements into release decisions.
The canonical status remains [current-state-and-implementation.md](current-state-and-implementation.md).
It does not supersede capability acceptance or authorize dependency retirement.

## 1. Restore reproducible image acceptance

At `5b7b8ccf`, CI run 41949720656 passed preflight, source checks, and
database integration. Security run 41949720642 passed. The image job failed
on Debian snapshot package downloads returning HTTP 503. These results apply
only to that SHA.

The archive URL redirects to a failing `/file/` backend. A direct-download
header returned HTTP 200 for the exact failing ARM64 `libarmadillo11` package;
the alternate snapshot endpoint returned 504. A subsequent full-build experiment
using the direct-download header still failed with HTTP 503/504, including on
the CA bootstrap package. That experimental workaround was withdrawn. No image
build passed in that experiment. Exact-archive CDN fallback was also tested:
it retrieved many packages, but an obsolete security package was absent from
the maintained CDN and still required the failing snapshot service.

The replacement strategy uses maintained, signed Debian bookworm repositories
with normal freshness checking. The PostgreSQL base digest and selected PostGIS
versions remain fixed. Debian transitive dependencies can change between base
builds; source hashes are not a claim of byte-for-byte image reproducibility.
The build records resolved inventories and the existing gate checks both
architectures and their reviewed differences. Runtime reproducibility belongs
to the tested immutable image digest. No archive proxy, custom downloader, or
architecture removal is required. The PGDG archive remains an external build
dependency for the exact PostGIS selection.

Acceptance: both architecture builds and exact OCI package-inventory checks,
then all required hosted checks on the resulting pushed SHA. Do not close this
gate from unit tests or a successful single-package request.

## 2. Establish a reusable immutable database base

After the reviewed source reaches main through develop, use the existing
protected PostGIS publication workflow. Verify the published digest and both
architecture inventories before selecting it in runtime release manifests.
The publisher cannot bootstrap an artifact from a failed source build.
Ordinary CI currently still rebuilds PostGIS from APT; changing that policy is
a separate implementation, not an existing benefit of the publisher.

## 3. Close candidate acceptance as one release batch

Use one captured source/schema revision for migration replay, Standard
outage/recovery, operator/two-tenant probes, and backup/restore evidence.
Reconcile the API/general-worker shared login under the existing C1 plan;
do not equate isolated operation roles with completion of that boundary.
Compare populated Adelphi workflows and retained reports against legacy output.
Exercise live OIDC browser login/session/logout, grant mapping, Collector sync,
selected providers, delivery, and ingress against the named candidate.

## 4. Record external dispositions and cut over

Record owners for retained reports, external callers, providers, retention,
legal holds, and recovery. Keep no-prune until policy approval. Physical Pi
acceptance remains unavailable; QEMU does not close it. Record any explicitly
deferred scale/device scope in the release decision rather than marking it
tested. Execute checkpoint, restore rehearsal, reviewed rollout, and rollback
checks before legacy retirement. Merge through develop and release to main
with the required CI, Security, and review gates.

Avoid adding capabilities during this closure batch. Historical unchecked CI
entries are evidence history, not independent new engineering work; the current
pushed SHA determines the active release gate.
