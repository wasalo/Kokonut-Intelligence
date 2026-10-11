# Kernel readiness image builds — 10 October 2026

Both default Kernel targets rebuilt successfully from the current uncommitted
checkout on `chore/kernel-plan-ignore`, based on commit
`ad806f504bfef15cba41446d777cb22f6bd8fe6a`. That commit alone does not reproduce
the built source: implementation changes remain uncommitted. This record
supersedes earlier application build evidence for the mutable local tags.

| Platform | Local tag | Inspected image identity |
| --- | --- | --- |
| linux/amd64 | kokonut-kernel-candidate:local | sha256:287fcfb9aa05990220dd1bd67a4aff524c99f24f1723f2485e5590bd29341166 |
| linux/arm64 | kokonut-kernel-candidate-arm64:local | sha256:a335b9d370575363d5fc80e7970511e9150d5f4a23353d8827af749ffbd5ef80 |

Both configure `appuser` and include the schema/extension readiness gate,
readiness CLI, and embedded package/runtime inventories. Dependency installation
layers were reused from prior builds, so this is not a fresh resolver comparison.
Each extracted inventory contains 68 distributions; package names and versions
match across architectures. See `images.json`, `package-differences.json`, and
the per-architecture inventory directories beside this document.

Inventories were copied from temporary stopped containers created with no
network and a read-only filesystem. No application process executed. Those
containers were removed after extraction. The extraction caused Docker to prepare
image filesystems; reported image sizes still should not be treated as comparable
installed-storage or Pi memory measurements.

## Remaining gates and rollback

No services were restarted, databases migrated, or runtime tests run. The
existing candidate container continues to use its previous image; legacy remains
stopped. Migrations 371–373 are bundled but remain unapplied. These tags are build
artifacts, not deployed releases. Optional MQTT/gRPC/analytics targets were not
rebuilt in this slice.

Matching package versions do not certify native wheels, imports, API behavior,
schema readiness, extension compatibility, worker durability, backup/restore, or
Pi hardware budgets. Dependency hashes/locking and a committed source revision
remain release prerequisites. The main planner's ARM64 guard remains active.

Mutable local tags now point at these new builds. Use previously recorded image
identities for rollback; do not assume the old tag still selects an earlier image.
No data rollback is needed for this build-only change. Do not prune earlier
artifacts before choosing and retaining the required rollback images.
