# ARM64 database compatibility blocker

On 10 October 2026 registry metadata was inspected for the candidate's exact
database reference:

`postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5`

Buildx reports a single Docker v2 manifest, and Docker manifest inspection's
platform descriptor reports linux/amd64. This pinned artifact is not a native
ARM64 database image. The current minimal/edge/standard manifests therefore
cannot yet satisfy the Raspberry Pi ARM64 target. AMD64 emulation is not ARM64
certification and has no demonstrated Pi resource/recovery budget.

The command planner now accepts `--target-platform` and rejects linux/arm64
with this known blocker before printing a deployment command. Its default is
linux/amd64; this declaration is a compatibility guard, not a hardware detector
or Docker architecture override. Manual Compose commands bypass the planner
and still require platform review. No database image, volume, or container was
changed by this inspection.

## Implementation path

Prepare a separate candidate PostGIS build based on a verified multi-platform
PostgreSQL 16 image, with pinned/reviewed PostGIS packages and required extension
initialization. Preserve PostgreSQL major version, application database/user,
private networking, data directory, health probe, backup tools, and PostGIS/raster
capabilities required by the schema. Determine package versions from verified
repository metadata rather than assuming AMD64 package constraints are portable.
Keep this additive until its extension/schema parity gates pass.

Build native or cross-platform AMD64/ARM64 artifacts, record immutable identities,
then initialize a fresh ARM64 database volume and apply the checksummed schema.
Rehearse logical backup/restore and spatial/raster queries before migrating farm
data. Do not attach an existing candidate or legacy data directory to an
unvalidated replacement image. Never upgrade extensions or database versions
implicitly as part of architecture selection.

Application ARM64 wheels/builds, hardware memory/CPU/storage measurements,
offline recovery, and 24-hour operation remain separate gates. Optional MQTT,
gRPC, ClickHouse, and proxy image platforms also require their own evidence.
Only remove the planner guard when the selected database artifact and manifest
path actually support ARM64; build success alone does not certify hardware.

Registry inspection succeeded; planner static lint and diff checks passed.
No runtime tests, image builds, migrations, hardware runs, or data changes were
performed. Rollback retains the current AMD64 candidate and legacy artifacts
and their volumes while ARM64 preparation proceeds separately.

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
inspection/acceptance. The paired builds documented above used the live PGDG
suite before the apt source lock below and do not verify the current snapshot
inputs.

This Dockerfile is not referenced by current Compose and was not built or
started. It does not change the candidate's existing PostgreSQL patch level or
PostGIS 3.4 deployment. A new package version may differ from historical PostGIS;
review extension upgrade/restore compatibility before adoption. The ARM64 planner
guard remains active. Database schema, migrations, volumes, and containers remain
unchanged. Diff checks passed; platform package resolution, builds, extension
parity, fresh-volume initialization, restore, and hardware gates remain pending.

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
were started. The image is not selected by current Compose, and the planner's
ARM64 guard stays active until the application/database deployment path and
acceptance gates are prepared. AMD64 final-target build, extension initialization,
spatial/raster queries, logical restore, and hardware certification remain pending.
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
architecture builds completed; those artifacts predate the apt source lock.
The field is now false until both architectures rebuild from the snapshot-aware
definition. Runtime certification remains false. The earlier artifacts are
retained as historical identities, not a published multi-platform index or
selected deployment image.

No database or data volume was started, migrated, or replaced. Current candidate
Compose and the planner ARM64 guard remain unchanged. Prepare a fresh isolated
database deployment path and complete acceptance before adopting either artifact;
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
`config/postgres/kernel-postgis-packages.json`. A low-priority apt preference
keeps unrelated PGDG packages behind the dated Debian source. The release-input
lock covers both source files and the package record. The release checker now
compares the complete installed Debian package inventories and selected PostGIS
versions across architectures. A fresh multi-architecture run must rebuild both
targets and exercise this checker before the apt inputs and inventory parity
are accepted. Extension behavior, restore, runtime, and Raspberry Pi remain
separate gates.

Build the final target with both explicit arguments after discovery:

```sh
docker build --platform linux/arm64 --target kernel-postgis \
  --build-arg POSTGIS_PACKAGE_VERSION=3.6.4+dfsg-2.pgdg12+1 \
  --build-arg POSTGIS_SCRIPTS_VERSION=3.6.4+dfsg-2.pgdg12+1 \
  -f Dockerfile.kernel-postgis -t kokonut-kernel-postgis-arm64:local .
```

This final-target command is documented, not executed. Use a distinct AMD64
tag for its counterpart and record actual artifact/package versions. The ARM64
metadata stage does not start a database or demonstrate Pi resource usage.
The planner remains guarded, current Compose remains on the legacy-compatible
database image, and no volume, migration, or extension was changed.
