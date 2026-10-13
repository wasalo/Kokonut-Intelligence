# ARM64 Kernel application build evidence

## Current source status — 13 October 2026

GitHub Actions run 287 built the default and ClickHouse-enabled application
images plus the custom PostGIS image for AMD64 and ARM64, and passed the locked
package inventory comparison on commit `6549043`. The current branch moved
forward afterward, so it still needs a fresh CI run. A local attempt on commit
`c2a5354` built the AMD64 application, then failed ARM64 dependency resolution
after the package host timed out; the final ARM64 image was not exported and
the paired PostGIS target was not attempted ([attempt record](builds/2026-10-13-recovery/kernel-architecture-local-build.json)).

The passing CI build is build evidence only. It does not certify startup,
PostGIS extension parity, ARM64 restore, or operation on a 4 GB Raspberry Pi.
The primary candidate still uses its AMD64-only database image and its planner
guard remains active.

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
requirements. It can supply API, workers, and HTTP receiver commands, but their
imports/startup and capability parity remain unverified on ARM64. Optional
transport and analytics builds need separate evidence. No providers, wallets,
requests, jobs, ingestion operations, database services, or data volumes ran.

Together with the paired PostGIS build, this establishes ARM64 build artifacts,
not a complete deployment or Raspberry Pi certification. Current Compose still
uses the original AMD64-only PostGIS image, and the command planner guard remains.
Prepare an explicitly isolated application/database path before any cutover.
Pending gates: schema/extension readiness, startup, governed API/mobile flows,
worker recovery, encrypted media, shared limiter behavior, backup/restore,
24-hour operation, and measured 4 GB Pi CPU/memory/storage budgets.

Static provider boundaries (17 vendor sites), dependency groups (11/28), and
diff checks passed. No runtime tests were added or run. Existing containers and
volumes remain unchanged. Rollback preserves earlier candidate/legacy images
and data; these separately named build artifacts require no data rollback.
