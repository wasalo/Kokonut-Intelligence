# Kernel dependency decisions

Status: proposed implementation boundaries, grounded at baseline
ad806f504bfef15cba41446d777cb22f6bd8fe6a.
These decisions authorize incremental development, not an immediate cutover.

| Provider | Current hard coupling | Default target | Preservation and removal gate |
|---|---|---|---|
| PostgreSQL/PostGIS | common/database.py; canonical schemas, jobs, outbox, audit | Keep canonical | Preserve ordered migration checksums, custody, lifecycle, scope, backup/restore |
| Directus | core/features.py and health.py; extensions/kokonut-hooks; config/directus/permissions.sql | Optional admin and compatibility adapter; public location reads now use the native governed view | Complete auth/role/field/row/hook/API and reviewer UI parity per collection |
| ClickHouse | ingestion/base.py; projection outbox; core health; gateway and gRPC require credentials; worker depends_on | PostgreSQL analytics and durable projections | Source lineage for each analytical dataset; export any unique data; result and performance parity; replay demonstration |
| Metabase | dashboards assets, seed-metabase.sh, PostgreSQL metadata database | Optional analytics profile; PostgreSQL source limited to reviewed `kokonut_reporting` views | Preserve templates, questions, filters, metadata; replace user dashboards before claiming first-party parity; follow [reporting source contract](metabase-reporting-contract.md) |
| Prefect | 17 Python source files import Prefect; config/prefect/deployment.yaml; required pip dependency | Existing scheduler plus event bus | Map every flow trigger/retry/dependency/approval; resolve baseline pipeline concerns; one schedule owner |
| Redis | Legacy Compose cache service for optional Directus caching and throttling; no Kernel Redis client | No Redis in Kernel minimal/edge/standard core. Keep PostgreSQL computation cache and operator sessions; use local rate limits in single-instance minimal/edge and shared PostgreSQL limits in standard. Any future scale deployment must use a shared provider. Redis remains an optional Directus adapter. | Preserve archived Directus telemetry/collaboration/failed-login state; never clear it during cutover. Validate shared limits before scaling; define any Directus Redis transfer/reset with login lockout. |
| Mosquitto | Compose service, cert/ACL mounts; two Python source files import paho | HTTP/CSV baseline, MQTT optional | Preserve topics, device authentication, TLS/ACLs, normalized readings, reconnect/idempotency |
| gRPC | eight Python source files import gRPC libraries; proto, SDK generation, image | REST baseline, optional transport | Keep protobuf field compatibility, streaming semantics and shared authorization |
| Caddy | routes /mobile and Directus; depends_on Directus+gateway; TLS volumes | Replaceable proxy; optional in minimal | HTTPS, trusted headers, paths, browser offline/security context, uploads and websocket parity |

## ADR-001: reuse existing infrastructure before adding ports

Choose explicit dependency injection around implementations that already exist.
The PostgreSQL ComputationCache, scheduler leases, platform_event delivery
history and clickhouse_outbox are retained. A cache miss must not become an
authorization or workflow decision. Do not replace persisted cache records with
memory until callers and reporting semantics have been reviewed.

## ADR-002: canonical writes and derived projections

PostgreSQL transactions own operational records. Keep the existing projection
outbox, including event identity and retry/lease semantics. AnalyticsBackend
supports named queries with typed scope, not arbitrary client SQL.
LISTEN/NOTIFY can wake workers; durable tables remain the recovery source.
Event cleanup currently cascades history; it is not an indefinite replay
archive. Define retention and an archive before promising full rebuildability.

## ADR-003: separate profile selection from feature availability

Existing feature flags are import-time constants and do not control Compose.
Metabase Compose is opt-in while its feature flag defaults on. The source
inventory counts credential-name references without storing values.
Compose interpolates required credentials before service profile filtering.
Therefore a future minimal manifest must be independently renderable with
PostgreSQL credentials only, not just a profile applied to the legacy manifest.

## ADR-004: keep runtime supervision explicit

The scheduler and bus invoke isolated child processes and use synchronous DB
work. Do not run blocking worker loops inside an ASGI event loop. Evaluate a
single application container with explicit API/worker process supervision for
minimal, or document a separate worker role until safe supervision exists.
Standard/scale may split processes while sharing one application distribution.
Graceful shutdown, lease recovery, worker health and one dispatch owner are
acceptance requirements.

## ADR-005: compatibility includes governance and user workflows

Gateway authorization is already default-protected. Moving location reads off
Directus requires deliberate scope and response-field policies; a raw SELECT
without those checks is not equivalent. Preserve independent human review,
agent limits, public-view eligibility, consent and custody throughout.
Do not claim the minimal profile preserves all capabilities until every matrix
row has either a built-in path or a documented optional/offloaded path with
accepted parity evidence.

## Deployment targets

| Profile | Planned roles | Gate |
|---|---|---|
| minimal | PostgreSQL/PostGIS + Kokonut app, local evidence | Native auth/API, supervised durable workers, optional-package import isolation |
| edge | minimal plus optional MQTT | Device/TLS parity and browser offline media behavior |
| standard | PostgreSQL, API, workers, replaceable proxy | Production policy, recovery, backup and job ownership |
| analytics | standard plus bounded DuckDB/Parquet jobs; optional Metabase | Scoped export, dataset parity, resource limits |
| scale | standard plus selected Redis/ClickHouse/gRPC adapters | Shared limiter/caches, concurrency, projection replay and transport parity |

ARM64 target: Linux 64-bit Raspberry Pi-class device with 4 GB RAM and SSD.
Image manifests and scientific-package wheels have not been certified.
Pin supported ARM64 images after build and device checks. Heavy ML/GIS jobs may
be optional or explicitly offloaded, with capability parity retained.

## Rollback and operational gates

- Preserve named volumes and old app images; never use down -v during refactor.
- Take an encrypted checkpoint with scripts/backup.sh and verify with
  scripts/verify-backup.sh; restore only into an isolated rehearsal stack.
- Encrypted upgrade checkpoints record PostgreSQL and ClickHouse inclusion.
  PostgreSQL-only profiles can checkpoint and restore without ClickHouse;
  ClickHouse-enabled backups and restores require the service and credentials
  and preflight it before writes. External media and provider-specific state
  still need separate backup coverage.
- Add forward migrations; old and new app versions must coexist on additive
  schema changes until the consumer cutover completes.
- Revert provider wiring/config before database restoration. Keep legacy
  Directus routes and analytical assets until their parity windows close.
- No new recurring owner may start until the old owner is quiesced.
- Local volumes, migration backlog and unresolved unique analytics data block
  removing an existing provider, not work on additive interfaces.
