# Isolated AMD64 portability deployment — 10 October 2026

The Docker daemon reports linux/x86_64. The standalone portability manifest was
built and started as linux/amd64 using encrypted SOPS secrets. No credentials
were printed. Project selection was explicit for every Docker and migration
command: `kokonut-kernel-portability`, `docker-compose.kernel-portability.yml`.

## Applied deployment state

| Role | Inspected image identity | Container status |
| --- | --- | --- |
| Database | sha256:b573e82124b3530c454ea6d5ae8aefce1fb7ee137467f66f75a5079f8569ee6b | running, healthy |
| Private API | sha256:78389fb6cf1f05291e89b35ce4f0271e533bbe5403be97a8d77a29cdfc5825f5 | running, healthy |
| Native worker | sha256:78389fb6cf1f05291e89b35ce4f0271e533bbe5403be97a8d77a29cdfc5825f5 | running; HTTP healthcheck disabled |

The database owns the new project-scoped
`kokonut-kernel-portability_portability-postgres-data` volume and private
`kokonut-kernel-portability_portability` network. All three containers have empty host
port bindings. This deployment cannot be opened through a localhost browser URL.

The ordered checksummed migration runner applied **364 schemas through 373**,
reporting **Applied: 364, Failed: 0**. It used explicit Compose project/file
options and `--schemas-only`. Numbered seeds and pilot data were not loaded;
schema migrations may themselves contain reference data. No migration was edited
or checksum repair performed. Required extension creation came from the canonical
schema migration; legacy initialization and optional-provider seed scripts did
not run. The runner log is retained locally at
`/tmp/kokonut-portability-migrations-20261010.log` with restrictive permissions.

The application command includes `--require-schema`. It passed the startup gate
before spawning the API, and Docker subsequently reported its configured HTTP
healthcheck healthy. Directus, ClickHouse, Metabase,
Prefect, MQTT, and gRPC remain disabled. Gateway rate limiting uses the local
provider; migration 373's presence does not activate shared rate limits.

## Subsequent native worker startup

Before worker startup, read-only inspection found zero scheduled tasks, enabled
tasks, platform events, and task runs. The explicit `workers` profile was then
started for this project using the existing AMD64 image with no build or dependency
startup. The schema gate passed before the supervisor spawned separate scheduler
and event processes with distinct lease-owner identifiers.

Process inspection showed both child commands running. Read-only inspection after
startup still found zero scheduled tasks, platform events, task runs, and delivery
attempt rows. No task was created or activated and no synthetic event was inserted.
This establishes idle process startup, not execution/retry/recovery acceptance.
The worker's HTTP healthcheck is intentionally disabled; its durable progress
requires operator observation when real work is selected.

## Scope of evidence

The latest replacement synchronizes API and worker on the public-relation gate
image shown above. Pre-update read-only inspection found zero scheduled tasks,
platform events, task runs, and delivery attempts. Both roles were then replaced
with no dependency startup or build during replacement; the existing database
instance/storage were retained. API startup passed the gate and Docker HTTP
healthcheck. Worker process inspection showed its supervisor plus distinct
scheduler/event children, establishing gate passage and idle process startup.
Compose's worker "Healthy" progress label is not a worker HTTP/liveness probe;
its image HTTP healthcheck remains disabled.

Immediate rollback image identities are
`sha256:eb8e59d1ae6d7280b9edffc9a6998d2ee956e8fc9b7b96a55d65c3916a0d648e`
for the prior API and
`sha256:aecd8291c9363f0ffeb88225a7db13baa124e83025347b1168bf6b74afc00a54`
for the prior worker. No migration, task activation, event insertion, test suite,
or live summary request accompanied the update. This establishes that the
current database satisfies the new structural gate at startup; it does not
exercise rejection paths, grants, view semantics, populated responses or recovery.
Earlier replacement notes below are chronological history, not the current
API/worker image selection. ARM64 artifacts still predate this relation-gate change.

The preceding API replacement added [explicit public response models](public-response-models.md)
for metrics, CRISP and location summaries, including pre-serialization payload
validation and generated OpenAPI response declarations. The build completed and
the schema gate/API startup succeeded; Docker reported the API healthy. The
immediately preceding API identity was
`sha256:0b3f55e86731d5045678fc83fc98fa3ef90a1b2b715b5d1baa2744aede088a1a`.
The worker and database instances were not replaced. No migration, data write,
model fixture exercise, live summary request, generated OpenAPI inspection, or
test suite accompanied this deployment. Startup establishes model/route import
compatibility, not payload/client compatibility.

The preceding API replacement added the governed public CRISP assessment and
location-summary services described in [their contracts](public-summary-contracts.md).
The build completed, startup passed the schema gate, and Docker reported the API
healthy. The immediately preceding API image was
`sha256:452db246d2ea8b86f227b0b51ad78d4a96f13925a38ba4fba594ccc91ed09d43`.
No worker/database replacement, migration, fixture creation, scoring, or lifecycle
transition accompanied this API update. No live summary request or test suite ran;
HTTP health does not certify those lazy-loaded route functions or response parity.
The subsequent [ARM64 public-read refresh](arm64-public-reads.md) now contains these
changes and the response models; ARM64 runtime remains unvalidated.

The API was subsequently rebuilt and replaced with bounded native location and
metric reads, async thread-pool offloading, metric UUID validation, and Decimal
JSON encoding. It again passed the schema gate and Docker healthcheck. Its
previous image identity was
`sha256:aecd8291c9363f0ffeb88225a7db13baa124e83025347b1168bf6b74afc00a54`;
retain that artifact for API rollback. The worker still uses that earlier image
and was not replaced in this read-path deployment. Both images share the same
schema inventory; API/worker source versions now differ intentionally. Restarting
or recreating a service from the mutable shared tag may select the newer build.
The database instance and storage were unchanged. No live location/metric
requests or populated-response acceptance checks ran.

This establishes fresh AMD64 schema application and API startup for this isolated
stack. No test suites, manual readiness command, domain request checks, ingestion
jobs, or external blockchain operations ran. It does not certify capability
parity, seed completeness, authorization behavior, spatial/raster operations,
worker recovery, PostGIS 3.4-to-3.6 restoration, backup/restore, shared rate limits,
ARM64 runtime, or Raspberry Pi hardware budgets. The application source is still
uncommitted; image tags are local mutable artifacts.

The older candidate API/database remain running with their previous images and
data. Its migration backlog is separate: applying 371–373 here did not apply them
to the candidate or legacy database. All legacy project containers remain stopped.
This is an additional private evaluation deployment, not a cutover.

## Rollback and next deployment steps

To stop this deployment, load encrypted secrets and run the following explicit
command with the same architecture selection:

```sh
KOKONUT_DATABASE_PLATFORM=linux/amd64 docker compose --env-file /dev/null \
  -p kokonut-kernel-portability -f docker-compose.kernel-portability.yml \
  --profile application --profile workers stop worker app database
```

Stop retains its containers, private network, and database volume. Do not use
volume removal, attach legacy/candidate storage, or attempt a database downgrade
as a rollback shortcut. Retain image identities and migration logs. A future
image rollback must satisfy the schema gate; an older schema inventory may
deliberately reject this newer database. Restore or data reconciliation requires
a reviewed backup/migration path. Restart does not apply new migrations by itself.

Before exposing this API or choosing production cutover, complete reference-data
planning, backup/restore, capability and authorization acceptance, resource sizing,
and a committed release/dependency policy. The candidate planner now selects an
isolated ARM64 image overlay for minimal, edge, and standard; current-schema
QEMU acceptance remains open ([profile record](arm64-database.md)).
