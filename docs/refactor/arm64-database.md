# ARM64 Kernel candidate profile

## Current planner status — 15 October 2026

The base candidate Compose file retains its AMD64-only PostGIS digest for the
default profile. The planner now selects a separate ARM64 overlay that builds
PostgreSQL 16/PostGIS 3.6.4 from the locked multi-platform base and package
versions, pins the app and database build/runtime platforms to `linux/arm64`,
and uses project `kokonut-kernel-candidate-arm64`. The separate Compose project
creates a separate database volume, so an AMD64 data volume is not reused.
Minimal, edge, and standard selections are supported; analytics and optional
service images are rejected until their manifests are verified. Standard adds
an ARM64 worker override.

The planner tests pass, and Compose merged configuration passed for minimal,
edge, and standard with the expected ARM64 app/database/worker settings and an
isolated project volume ([profile evidence](builds/2026-10-15-recovery/kernel-arm64-profile-config.json)).
This host's Docker socket denies daemon access, so this update did not build or
start images. The earlier QEMU runtime acceptance applied 386 migrations on
revision `e236251`; the current repository has 391 numbered migration files
through migration 400.
Repeat the isolated ARM64/QEMU build, full-schema bootstrap, health, and restore
against the current source before treating it as runtime accepted. No physical
Raspberry Pi performance, thermal, storage, power-loss, network, or restart
claim is made.

On 10 October 2026 registry metadata was inspected for the candidate's exact
database reference:

`postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5`

Buildx reports a single Docker v2 manifest, and Docker manifest inspection's
platform descriptor reports linux/amd64. The unmodified base candidate still
cannot run natively on ARM64; the planner now composes the reviewed custom image
overlay described above for supported ARM64 profiles. AMD64 emulation is not
physical Pi certification.

The planner originally rejected `linux/arm64` after this inspection. That
historical behavior has been replaced by the explicit ARM64 overlay and separate
project described at the start of this record. Manual Compose commands still
need the same platform overlay and project isolation.

## Historical CI and selection evidence — 13 October 2026

The dedicated `docker-compose.kernel-portability.yml` manifest now references
`Dockerfile.kernel-postgis` and accepts `linux/amd64` or `linux/arm64` through
`scripts/kernel-portability.py`. GitHub Actions run 287 built the application
and custom PostGIS targets for both architectures and passed the locked package
inventory comparison with the reviewed `libquadmath0` architecture difference.
These are build checks, not evidence of PostgreSQL startup, extension/schema
parity, backup/restore, or Raspberry Pi operation.

At that date, the primary `docker-compose.kernel-candidate.yml` still used the pinned
AMD64-only `postgis/postgis:16-3.4` digest above when selected alone. The
profile planner appends the ARM64 custom-image override for minimal, edge, and
standard, and uses a separate project from the AMD64 candidate. Analytics and
optional service images remain blocked for ARM64. No existing candidate or
legacy data volume is attached to the custom image. The local application build
record at that date was for commit `c2a5354`: AMD64 built, but ARM64 dependency resolution failed after
the package host timed out, so the PostGIS target was not attempted. CI run 287
passed the multi-architecture image/package gate on earlier commit `6549043`;
current branch-head CI is still required ([local evidence](builds/2026-10-13-recovery/kernel-architecture-local-build.json)).

## Remaining acceptance path

The additive PostGIS build uses a verified multi-platform PostgreSQL 16 base and
pinned package versions found on both architectures. It preserves PostgreSQL
major version, application database/user, private networking, data directory,
health probe, and extension initialization responsibility. Keep it separate
from the default candidate until extension/schema parity gates pass.

The remaining software work is to rerun the ARM64 build, initialize its fresh
database volume, apply the current ordered schema through migration 400, and
rehearse logical backup/restore plus spatial/raster queries before migrating
farm data. Do not
attach an existing candidate or legacy data directory to the replacement
image. Never upgrade extensions or database versions implicitly as part of
architecture selection.

Application ARM64 wheels/builds, hardware memory/CPU/storage measurements,
offline recovery, and 24-hour operation remain separate gates. Optional MQTT,
gRPC, ClickHouse, and proxy image platforms also require their own evidence.
Keep the profile limited to the verified ARM64 image path; build success alone
does not certify current-schema runtime or physical hardware.

At initial registry inspection, no runtime tests, image builds, migrations,
hardware runs, or data changes had been performed. The later current-state
evidence is recorded below. Rollback retains the current AMD64 candidate and
legacy artifacts and their volumes while ARM64 preparation proceeds separately.

## Additive build definition

`Dockerfile.kernel-postgis` now starts from official PostgreSQL 16 Bookworm index
`sha256:0ea6700a3b4f0ae6ce746519073558aed4d88a79d8d07622a9a644946c7319c4`.
Registry inspection reports PostgreSQL 16.15 and these platform manifests:

| Platform | Manifest digest |
| --- | --- |
| linux/amd64 | sha256:ec9f656f17c8b4dfebf49e58cf5c46d493d4846d4ea6d8b85d0637f68ee33bfc |
| linux/arm64/v8 | sha256:6b0faa930dc29e5af5af9b50081ad496fad106b85a88ad66aea01f11d4494733 |

The package approach follows the [PostGIS project's Docker build](https://github.com/postgis/docker-postgis/blob/master/16-3.5/Dockerfile),
which installs PostgreSQL-major-specific PostGIS and scripts packages. This new
candidate requires both POSTGIS_PACKAGE_VERSION and POSTGIS_SCRIPTS_VERSION
arguments and fails if either is missing. No guessed package version is supplied:
resolve verified available versions for each architecture before building.
Installed package versions are recorded inside the artifact at
`/usr/local/share/kokonut/database-packages.txt`.

The image adds no automatic schema or seed initialization. Existing migration
000 creates postgis and postgis_topology; other canonical extensions remain
owned by schema SQL. Raster capability and package compatibility still need
runtime acceptance. The earlier paired builds used the live PGDG suite before
the apt source lock below; CI run 287 later built from the locked snapshot-aware
inputs and passed the architecture package inventory gate.

At first definition this Dockerfile was not yet selected by Compose or built.
It is now used by the separate portability manifest and its build targets passed
in CI run 287. The ARM64 candidate profile added on 15 October selects it through
the explicit overlay. It does not change the candidate's existing PostgreSQL patch
level or PostGIS 3.4 deployment. The new package version differs from historical
PostGIS; review extension upgrade/restore compatibility before adoption. The
initial ARM64 deployment guard was active until the candidate overlay was
added. No schema, migration, existing volume, or candidate container was changed
by adding this evaluation path. Runtime
extension parity, fresh-volume initialization, restore, and hardware gates
remain pending.

## Package discovery stage

The additive Dockerfile now includes a build-only `package-catalog` target which
refreshes signed apt metadata and prints policy for the two required packages.
It does not start PostgreSQL, attach storage, or install PostGIS. The final
`kernel-postgis` target still requires explicit package versions.

AMD64 discovery against the pinned Bookworm base on 10 October 2026 reports
`3.6.4+dfsg-2.pgdg12+1` as the candidate for both
`postgresql-16-postgis-3` and `postgresql-16-postgis-3-scripts`, from the
bookworm-pgdg repository. Versions 3.6.3 and 3.6.2 are also listed. These are
available AMD64 packages, not verified ARM64 availability or an adoption decision.
The metadata-stage export digest is
`sha256:7791eddb4912c6d323e260089fddc09d7c39b6a883cdc6a8dc52d986be120a44`.
The build and local unpack completed successfully as
`kokonut-postgis-catalog-amd64:local`. This is a metadata-discovery artifact,
not a completed PostGIS database image.

The available 3.6 candidate differs from the legacy 3.4 extension line. Keep the
current database unchanged while inspecting ARM64 package availability and
planning spatial/raster, schema, and logical restore compatibility. No package
version default, extension upgrade, schema migration, or replacement Compose
selection was introduced during discovery.

## Matching ARM64 package evidence

The ARM64 package-catalog stage now successfully ran apt metadata refresh and
policy inspection for the same pinned base. Both packages list
`3.6.4+dfsg-2.pgdg12+1` as candidate from bookworm-pgdg's arm64 repository,
matching the AMD64 result. The verified build arguments are recorded in
`config/postgres/kernel-postgis-packages.json`; this is package availability
evidence, not a completed database build or extension certification.
The ARM64 catalog build completed as `kokonut-postgis-catalog-arm64:local`,
manifest-list digest
`sha256:fd7187ec486f02eaeebd1be3a08ce34dc6f8f90f42c0cf4c162244a6e11c9138`.

## Full ARM64 image build

The final `kernel-postgis` target subsequently built successfully with both
verified package arguments on 10 October 2026. Inspection of
`kokonut-kernel-postgis-arm64:local` reports linux/arm64, image identity
`sha256:a0ff166b0949fb1a0224c9f9115e1eb211a3b2e3d3dbb2cd3f927c5901794296`,
and Docker-reported size 217,385,115 bytes (approximately 207 MiB). Package logs
confirm both PostGIS packages at 3.6.4+dfsg-2.pgdg12+1; installation added 84
packages with no base-package upgrades. The build writes its full package list
inside the artifact. Disk usage across unpacked/shared layers must be measured
separately; this reported image size is not a memory or Pi-storage guarantee.

The build ran under local cross-platform execution, not on Raspberry Pi hardware.
No database server, volume, schemas, extension upgrades, or application services
were started by this build. At that point the image was not selected by Compose;
it is now referenced by the separate portability evaluation manifest. The
planner's historical ARM64 guard has been replaced by the separate candidate
overlay; current-schema runtime gates are still pending. AMD64 final-target
build, extension initialization, spatial/raster queries, logical restore, and
hardware certification were still pending when this historical entry was
recorded; the paired-build and locked-CI records below supersede its build status.
At this stage the JSON recorded only the ARM64 artifact, with the paired build
still pending. The completed pair below supersedes that build status; runtime
acceptance remains incomplete. No runtime tests were added or run; diff checks passed.

## Paired AMD64 build completed

The AMD64 final target also built successfully on 10 October 2026 using the same
explicit package arguments. Inspection reports linux/amd64 and identity
`sha256:10d2101d4d0abee25a6b5217ae5fa43f5c912eb75d3b34f17f206e1fcfcff789`
for `kokonut-kernel-postgis-amd64:local`. Docker reports 911,774,311 bytes
(approximately 870 MiB). AMD64 was unpacked locally; ARM64's much smaller
reported size must not be treated as proof of a smaller installed filesystem.
Comparable compressed/unpacked/layer/storage measurements remain pending.

The JSON previously marked `database_build_verified` true to mean both
architecture builds completed; those local artifacts predate the apt source
lock. Its field remains false because their image identities have not been
replaced with snapshot-aware local builds. CI run 287 separately built the
locked targets and passed package comparison, but its artifact identities are
not recorded as local image tags in this file. Runtime certification remains
false. The earlier local artifacts are historical identities, not a published
multi-platform index or selected deployment image.

No database or data volume was started, migrated, or replaced. The primary
candidate Compose and planner ARM64 guard remain unchanged. The separate
portability Compose path uses the custom image for isolated evaluation. Prepare
a fresh isolated database deployment path and complete acceptance before
adopting either artifact;
preserve historical image/volume state for rollback. Diff checks passed and no
runtime tests were added or run for the paired build.

The subsequent [ARM64 application build](arm64-application.md) also completed.
Deployment selection, extension/runtime acceptance, and hardware certification
remain separate gates; the original manifests' ARM64 guard stays active.

## Snapshot-aware apt source follow-up — 13 October 2026

The current `Dockerfile.kernel-postgis` source set is defined in
`config/postgres/kernel-apt.sources`: Debian Bookworm and security packages come
from the `20261012T000000Z` snapshot, while the exact PostGIS packages come from
`bookworm-pgdg-archive` at the versions in
`config/postgres/kernel-postgis-packages.json`. The pinned PostgreSQL base has no
CA bundle, so a first build stage installs `ca-certificates` from the same
timestamped Debian snapshot over HTTP with APT signature verification enabled;
the next stage switches to the locked HTTPS sources. A low-priority apt
preference keeps unrelated PGDG packages behind the dated Debian source. The
release-input lock covers the bootstrap source, HTTPS source, preference, and
package record. CI run 283 exposed the missing-CA bootstrap cycle. Run 284
confirmed the CA bootstrap and built both architecture images; full inventory
comparison found the documented `libquadmath0` AMD64-only package, now recorded
with its exact version in the locked package record. CI run 287 passed the
default, ClickHouse, and PostGIS image builds plus locked package comparison on
both architectures. That build-input gate is accepted for the tested commit;
current branch-head CI, extension behavior, restore, runtime, and Raspberry Pi
remain separate gates.

Build the final target with both explicit arguments after discovery:

```sh
docker build --platform linux/arm64 --target kernel-postgis \
  --build-arg POSTGIS_PACKAGE_VERSION=3.6.4+dfsg-2.pgdg12+1 \
  --build-arg POSTGIS_SCRIPTS_VERSION=3.6.4+dfsg-2.pgdg12+1 \
  -f Dockerfile.kernel-postgis -t kokonut-kernel-postgis-arm64:local .
```

This manual final-target command is documented, not executed directly; CI run
287 built the target through the release workflow. Use a distinct AMD64 tag for
its counterpart and record actual artifact/package versions. An image build
does not start a database or demonstrate Pi resource usage. The primary profile
planner remains guarded, the default candidate remains on the legacy-compatible
database image, and no existing volume, migration, or extension was changed.
