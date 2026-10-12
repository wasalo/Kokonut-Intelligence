# ARM64 Kernel application build evidence

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

This fresh resolution uses version ranges and can differ from cached AMD64
dependencies. Build/install success is not runtime compatibility evidence.
Before release, capture complete dependency inventories, select a reviewed lock
strategy, and rebuild both architectures from the same source/dependency policy.
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
