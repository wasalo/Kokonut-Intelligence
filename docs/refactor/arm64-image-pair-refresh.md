# ARM64 application and PostGIS image refresh — 11 October 2026

## Build record

Built current-checkout ARM64 artifacts through Docker Buildx on the
`desktop-linux` builder. The source commit was
`761d06a0734d3d4417533eeb0ab3a363e0886777` on `chore/kernel-plan-ignore`.
Buildx was `v0.37.2`, BuildKit was `v0.33.1`, and Docker Engine was `29.8.2`.

| Artifact | Image tag | Image identity | Platform | Reported image size |
| --- | --- | --- | --- | ---: |
| Kernel application (`kernel` target) | `kokonut-kernel-batch-next-arm64:local` | `sha256:6737ff1e09a8c552a49f76c56f83fedc64c931a41ec5be38d85cea6bf3934967` | `linux/arm64` | 112,745,077 bytes |
| PostgreSQL/PostGIS 16 (`kernel-postgis` target) | `kokonut-kernel-batch-next-postgis-arm64:local` | `sha256:bbaa03c306bbae158a4ec1c088dfcbc0c54956fb422bb5cae6707a4e564dc507` | `linux/arm64` | 217,385,115 bytes |

The application build used the existing pinned Python base and reused its
dependency-installation layers. The PostGIS image used the pinned
`postgres:16-bookworm` base digest and PostGIS packages
`3.6.4+dfsg-2.pgdg12+1`; its package-installation layer was already cached from
the same recipe. The Dockerfile inventory step ran as part of the application
image build.

## Isolation and limits

The artifacts have new tags; existing local image tags were not retagged. No
container was created or started, no Compose project was changed, and no volume,
database, migration, or schema was touched. After the builds, the active
candidate app and Metabase containers remained healthy and the candidate
PostgreSQL container remained up on its previous image.

This is build evidence only. No ARM64 service was started. It does not establish
native-device startup, migration/bootstrap, PostGIS extension behavior, backup
and restore, memory or storage use, or Raspberry Pi 4 GB suitability. No new
dependency resolution or lockfile was produced. The candidate Compose manifest
still selects its previous AMD64-only PostGIS digest; these images are not yet a
deployable ARM64 candidate profile. Architecture CI gates and release-input
locking also remain open.

## Rollback

The running stack has no rollback action because it was not changed. The two
unique local tags can be removed independently with `docker image rm` if the
artifacts are no longer needed; keep the prior ARM64 tags and running candidate
images intact until later runtime and restore acceptance has been reviewed.
