# ARM64 Kernel application build evidence

## Current-source software refresh — 25 October 2026 (commit e9d68670)

The exact pushed source revision `e9d68670ccd809c4b8e8a33cc8b1c8f63e99f476`
built the default Kernel target for `linux/arm64` with the pinned runtime lock.
Docker reported image `sha256:7c2405074026db2bee901012325926368fcc9ff059b60ef0f1cd80a7e9477e29`,
configured user `appuser`, and image size 544,833,127 bytes. A disposable
network-disabled QEMU container with a read-only root and 64 MiB temporary
`/tmp` reported `aarch64`, constructed the 15-route Gateway, loaded all 18 job
specs, and imported both Python SDK clients plus the worker CLI and Delphi
facilitator modules. Only a read-only SDK source mount was added. The candidate,
legacy stack, database, providers, credentials, host ports, and persistent
Compose resources were not touched. The temporary image is removed after the
smoke. This refreshes software portability evidence only; physical Raspberry
Pi, power-loss, thermal, measured resource, and storage-endurance acceptance
remain open ([evidence](builds/2026-10-25-recovery/arm64-kernel-current-source-smoke-e9d68670.json)).

## Current-source software refresh — 25 October 2026

Source revision `829376b4e0af8f143003ba8917374c4f6a2e0394` built the default
Kernel image for `linux/arm64`. Docker confirmed image user `appuser`. A
network-disabled QEMU container with a read-only root and 64 MiB temporary
`/tmp` reported `aarch64`, created a 15-route Gateway, imported both Python
SDK clients from a read-only mount, loaded all 18 `JobSpec` entries, displayed
migration CLI help without database credentials, and constructed a synthetic
RPC balance snapshot. The temporary container and image were removed; no
database, provider, credentials, published port, candidate service, legacy
stack, or persistent volume was accessed. This is software-emulation evidence
only, not physical Raspberry Pi, power-loss, thermal, performance, or
storage-endurance acceptance
([evidence](builds/2026-10-25-recovery/arm64-kernel-current-source-smoke-829376b4.json)).

## Current-source software refresh — 24 October 2026

The current source revision `8f5fd1eb` built the default Kernel target for
`linux/arm64`. Docker confirmed the configured non-root user `appuser`. A
network-disabled QEMU container with a read-only root and 64 MiB temporary
`/tmp` reported `aarch64`, created the Gateway application, imported both
Python SDK clients from a read-only mount, loaded all 18 `JobSpec` entries,
showed migration CLI help without database credentials, and constructed a
synthetic RPC balance snapshot. The temporary container and image were removed;
the candidate, legacy stack, databases, proxy, Metabase, and persistent volumes
were not changed. This is software-emulation evidence only; physical Raspberry
Pi, power-loss, thermal, performance, storage-endurance, live endpoint, provider,
and long-duration recovery acceptance remain open
([evidence](builds/2026-10-24-recovery/arm64-kernel-current-source-smoke-8f5fd1eb.json)).

## Current-source software refresh — 20 October 2026

The pushed source revision `1e5bf08a5f777276340a71752f611b8dd5eb18cc` built
the default Kernel target for `linux/arm64`. Docker reported the image as
`linux/arm64` with configured user `appuser`. A network-disabled QEMU container
with a read-only root imported `services.gateway.app` and the mounted Python
SDK, loaded all 18 `JobSpec` records, and constructed a synthetic RPC balance
snapshot. The container used only a read-only SDK bind mount and disposable
`/tmp`; it had no database, provider, credential, or host-port access. The
temporary container and image were removed, and candidate services remained
healthy. This is current-source software evidence, not physical Pi, migration,
resource-endurance, power-loss, or 24-hour recovery acceptance
([evidence](builds/2026-10-20-recovery/arm64-kernel-current-source-smoke.json)).

## Current source smokes — 16 October 2026

On `04bf2a85dffd8f2b5a28051d940f8c9ed4407ec9`, Docker Buildx built the
default Kernel target for `linux/arm64` and exported manifest
`sha256:6b99f76d7190cc2078d15468974f7f89e0038652921f004711e85388e640bde5`.
The loaded image reports `linux/arm64` and user `appuser`. Under QEMU, with
networking disabled, the runtime CLI help and Kernel image-manifest command
both completed successfully. The temporary image and archives were removed;
no Compose service was started or replaced. This refreshes the code-only ARM64
build/import smoke, not physical Pi, database, ingress, or provider acceptance
([evidence](builds/2026-10-16-recovery/kernel-arm64-qemu-smoke.json)).

The optional OIDC application target also built for `linux/arm64`. The loaded
image reported the same non-root user; runtime CLI help and its image-manifest
command passed under QEMU with networking disabled. Authlib, cryptography, and
itsdangerous resolved ARM64 packages. This verifies the Kokonut application
image only; the ZITADEL service images and full profile remain unverified
([evidence](builds/2026-10-16-recovery/kernel-arm64-oidc-smoke.json)).

## Build and runtime status — 15 October 2026

GitHub Actions run 287 built the default and ClickHouse-enabled application
images plus the custom PostGIS image for AMD64 and ARM64, and passed the locked
package inventory comparison on commit `6549043`. The current branch moved
forward afterward, so it still needs a fresh CI run. A local attempt on commit
`c2a5354` built the AMD64 application, then failed ARM64 dependency resolution
after the package host timed out; the final ARM64 image was not exported and
the paired PostGIS target was not attempted ([attempt record](builds/2026-10-13-recovery/kernel-architecture-local-build.json)).

The older CI build is build evidence only. A separate current-source local
Buildx/QEMU run now builds the profile-selected app and PostGIS images as
linux/arm64, applies all 391 ordered schemas through migration 400, restores a
logical backup with matching migration fingerprints, and recovers after a
database restart and simulated app loss. This does not certify physical Pi
operation; see the [runtime evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-400.json)
and [profile status](arm64-database.md).

The [later public-read refresh](arm64-public-reads.md) records the current ARM64
local tag with the newer public API contracts. The build below is historical
installation evidence, not the latest source artifact.

On 10 October 2026 the default Kernel target built successfully with
`--platform linux/arm64` as `kokonut-kernel-candidate-arm64:local`.
Inspection reports identity
`sha256:e5ee28ff8f2d1031bb6a8a2cadefd37826d8ffeecf1e62fac8a5e2e4d7ddd01e`,
linux/arm64, configured user appuser, and Docker-reported size 112,209,153 bytes
(approximately 107 MiB). This artifact was not unpacked or started as a runtime
service; comparable installed-filesystem/storage measurements remain pending.
The smaller reported size than the unpacked AMD64 image is not a demonstrated
storage or memory improvement.

The pinned Python base supports the selected architecture, and all chosen
dependency groups installed successfully under cross-platform execution. The
driver and encryption packages resolved ARM64 wheels. Key installed versions:

| Package | Version |
| --- | --- |
| psycopg2-binary | 2.9.13 |
| FastAPI / Uvicorn | 0.143.0 / 0.54.0 |
| Starlette / Pydantic | 1.7.0 / 2.14.0 |
| Typer / Requests | 0.27.3 / 2.34.2 |
| Web3 / eth-abi | 7.16.0 / 5.2.0 |
| boto3 / openpyxl | 1.43.111 / 3.1.5 |
| pycryptodome | 3.24.0 |

This historical resolution uses version ranges and can differ from cached AMD64
dependencies. Later work added hash-locked Python dependency closures for the
default and ClickHouse images, and CI run 287 verified package parity for its
tested commit. Build/install success is not runtime compatibility evidence.
The artifact includes uncommitted source, including migrations 371–373 and the
latest gateway rate-limit changes; none of those migrations were applied here.

The default target excludes MQTT/gRPC SDKs, ClickHouse driver, and heavy ML/GIS
requirements. Optional transport and analytics builds need separate evidence.
The initial package-resolution attempt did not run providers, wallets, requests,
jobs, ingestion operations, or attach existing database services/data volumes.
Current app startup and a fresh disposable database are covered by the QEMU
acceptance below; optional worker/provider parity remains open.

The current Compose profile is isolated from the AMD64 candidate. Under QEMU,
the current schema, application startup, health, protected-route denial, logical
restore, PostGIS spatial/raster functions, and short restart recovery passed.
Raster was enabled manually for the test because the ordered schema does not
currently create `postgis_raster`. Governed API/mobile flows, optional workers,
encrypted media, shared limiter behavior, 24-hour operation, and measured 4 GB
Pi CPU/memory/storage budgets remain separate gates.

Static provider boundaries (17 vendor sites), dependency groups (11/28), and
diff checks passed. This documentation update added no repository test suite.
The existing candidate and legacy containers and volumes remain unchanged.
Rollback preserves earlier candidate/legacy images
and data; these separately named build artifacts require no data rollback.

**Current-source code-only smoke (18 October 2026):** the default Kernel app
target built as `linux/arm64` from source commit `31c6520e`. A network-disabled,
read-only QEMU container reported `aarch64`, imported the Gateway module and
Python SDK, found all 18 catalog JobSpecs, constructed a synthetic RPC balance
snapshot, and verified the six newly exposed location-read groups. The
temporary image and container were removed; no database, provider, credential,
or persistent Compose resource was accessed ([evidence](builds/2026-10-18-recovery/arm64-kernel-current-source-smoke.json)).
This does not replace physical Raspberry Pi, power-loss, resource-budget, or
long-duration acceptance.
