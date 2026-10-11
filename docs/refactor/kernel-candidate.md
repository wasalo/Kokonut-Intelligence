# Candidate Kernel image and isolated deployment

`Dockerfile.kernel` installs kernel, Web3, and exports dependency groups using
the existing digest-pinned Python base. It retains non-root execution and checks
the gateway's existing health route using Python rather than adding curl.
Services, schemas, configuration, and package metadata are included. Legacy
images remain unchanged.

`docker-compose.kernel-candidate.yml` is a standalone preparation manifest.
It contains PostgreSQL/PostGIS plus the candidate app. The database is private,
the API binds localhost port 8098 by default, and its named volume differs from
the legacy volume. Always use a separate project name:

    docker compose -p kokonut-kernel-candidate -f docker-compose.kernel-candidate.yml build

Do not combine this manifest with legacy Compose or use the legacy project name.
No automatic seeding, migration, restore, or worker execution is configured.
The database uses `POSTGRES_PASSWORD` for its owner credential. Application
connections use `PG_PASSWORD` (falling back to `POSTGRES_PASSWORD` for legacy
compatibility). The default candidate still uses the owner role until the
optional [runtime-role policy](runtime-role-policy.md) is provisioned.
Shared database settings no longer require CLICKHOUSE_PASSWORD when ClickHouse
is explicitly disabled; enabled-provider secret validation is preserved.

## Gates before starting or replacing the legacy stack

- Build and resolve all candidate dependencies; measure image size.
- Prepare the separate database through the existing checksummed migration
  runner and reviewed seeds; a fresh PostgreSQL volume has no application schema.
  Set both `COMPOSE_PROJECT_NAME=kokonut-kernel-candidate` and
  `COMPOSE_FILE=docker-compose.kernel-candidate.yml` for host migration commands;
  the runner invokes Docker Compose. Do not assume host PG_HOST redirects that
  runner away from the legacy project. Its default path must not be used here.
- Validate gateway authentication, lifecycle, mobile sync, public queries, and
  the missing-library behavior of every enabled domain route.
- Replace Directus-backed location routes before claiming route parity.
- Add durable scheduler/event worker supervision before claiming a functioning
  two-service Kernel deployment. Feature flags do not start workers.
- Preserve/configure private media storage and evidence retention.
- Reconcile migration drift and rehearse backup/restore before using live data.
- Confirm both Python and PostGIS digest manifests support the target ARM64
  platform, then measure resource usage on hardware. ARM64 is not certified.

This is a built candidate, not a supported minimal deployment. ML/GIS and
other omitted libraries may still be needed by lazy domain operations. The
candidate intentionally disables vendor probes; successful health alone cannot
prove capability parity. Candidate services have now been started as recorded below.

The image healthcheck uses `/health`, which is the gateway's liveness endpoint.
It does not probe application tables or workers. Provider health/readiness is
reported separately through `/api/health/services`; neither replaces the schema
and durability acceptance gates.

## First local build evidence

The candidate image built successfully on 9 October 2026 through the standalone
Compose build command above. Local image inspection reports:

- Tag: `kokonut-kernel-candidate-app:latest`
- Image ID: `sha256:ebe9928ab3153a6cfa24afe7a91f2553ca251939f914230273c41ff309b0af4a`
- Platform: `linux/amd64`
- Reported local size: 474,927,465 bytes (about 453 MiB); this is not registry
  transfer size or runtime memory usage.
- Dependencies resolved and installed using the inherited version ranges.

No containers, application schemas, workers, or volumes were created by this
build. Runtime capability tests and ARM64 builds remain pending. This image uses
the source available at build time; later source edits require rebuilding.
The source remains uncommitted, so the image ID is the concrete build identity
and cannot be represented as a clean release from the baseline commit.

## Isolated bootstrap and first startup

The candidate database and app were started under `kokonut-kernel-candidate`.
The database uses `kokonut-kernel-candidate_kernel-postgres-data`; legacy volumes
and records were not copied or migrated. The checksummed runner applied all
361 schema migrations through #370 with `Failed: 0`. Numbered seeds and pilot
data were not applied by this schema-only run; migration SQL may itself insert
reference records. No scheduler or event worker was started.

The first host migration attempt failed to decrypt SOPS before any migrations
ran. The documented development plaintext fallback then completed the isolated
bootstrap. The supplied local age key subsequently decrypted the dotenv-format
SOPS file successfully. A read-only migration status command also succeeded with
`SOPS_AGE_KEY_FILE` explicitly set and plaintext fallback disabled: 361 applied
schemas and 118 pending numbered seeds (479 discovered migrations total).
No decrypted values or key contents were displayed. Future host commands should
set that key-file environment variable and retain encrypted loading. The
candidate app receives `PG_USER` and `PG_PASSWORD` through Compose. When the
runtime-role overlay is selected, the admin password stays with PostgreSQL and
the one-shot role bootstrap; the app receives the distinct runtime credential.

Gateway logs confirm application startup completed, listening on container port
8099, exposed only as `127.0.0.1:8098`. Its Docker liveness probe returned 200.
This proves launch, not API capability parity, worker readiness, or field-data
compatibility. Runtime suites remain pending. To stop the candidate while
preserving its data, use the separate project/file with `stop`; avoid deleting
volumes. Legacy services were not recreated.

## Supervised rebuild

The candidate was rebuilt with native public location reads and the process
supervisor. Build output recorded manifest-list digest
`sha256:897925167d07fd1530b3f1c3e02f492693ffad4539695fe8c636d70597bafd50`.
Only the app was recreated (`up -d --no-deps app`); the candidate database and
volume were preserved. Pre-start inventory found zero scheduled tasks, five
registered event handlers, and zero platform events. Numbered seeds remain
pending. Logs confirm supervisor launch of API/scheduler/events, scheduler
startup, completed API startup, and the existing liveness probe returning 200.
The legacy stack remains stopped at the user's request. Runtime route parity,
worker recovery, ARM64, and complete capability acceptance remain open.

## Receiver and projection source rebuild — 10 October 2026

The default Kernel target built as `kokonut-kernel-candidate:local` with identity
`sha256:590bea28a30769f9e30e1508bdeb38d7ddb3b926ab1557cb4488eab8b4214c10`.
Inspection reports linux/amd64, 475,118,306 bytes (approximately 453 MiB), user
appuser. It includes separate worker supervision, forwarding-header policy,
HTTP sensor transaction/retry/body guards, active-device checks, shared sensor
timestamp/projection helpers, and updated outbox failure outcomes.

No containers were recreated or started for this rebuild. The running candidate
continues using its earlier image. Migration 371 is still unapplied and required
before running the updated scheduler; migration 372 is required for updated
MQTT receipts. Building an image copies schema files but never applies them.
The MQTT and gRPC targets were not rebuilt here. Default Kernel dependencies
exclude their SDKs and the ClickHouse driver; analytics requires its explicit
driver build argument.

The tag captures uncommitted local source and is not a release artifact. Compose
manifests currently use build definitions, so this manually named tag is evidence
of a build rather than an automatic change to the image selected by Compose.
The same default target supports API, separate worker, and standalone HTTP
receiver commands with their role-specific healthchecks. Build success does not
prove those entry points import, start, process requests, recover, or fit ARM64
hardware. Runtime suites were not added or run. Static provider boundaries
(17 vendor sites), dependency groups (11 groups/28 requirements), and diff checks
passed.

## Active candidate schema update — 11 October 2026

The older startup and receiver-build sections above record their state at the
time each build was captured. The active candidate's exact `000_extensions.sql`
history was subsequently repaired through the audited allowlist after all six
expected extensions were verified. Migrations 371–379 then applied with zero
failures; the exact-target plan now reports zero pending across 370 schema
migrations. The reporting schema's three views and the NOI crop-cycle unique
index exist. The candidate app and private database are healthy. Its supervisor
runs scheduler and event-worker processes, but scheduler status reports zero
enabled, disabled, or running tasks; the NOI daily task is not registered. No
runtime/analytics role or Metabase source/cards are configured. [Active migration evidence](builds/2026-10-11-recovery/candidate-migration-apply.json).

The rollback statement above applies to the earlier build-only checkpoint. For
the active database migration, restore the retained encrypted pre-repair
checkpoint into a clean database if rollback is required; this returns the
ledger to the historical checksum state, so replaying current migrations first
requires the audited repair. See [candidate migration evidence](builds/2026-10-11-recovery/candidate-migration-apply.json).
