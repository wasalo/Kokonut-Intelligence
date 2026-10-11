# Isolated PostGIS portability deployment preparation

**Subsequent deployment:** the [AMD64 runtime record](portability-runtime.md)
documents the completed isolated startup and 364 applied schemas through 373.
Preparation-only statements below describe the earlier implementation slices;
the runtime record is the current deployment evidence. ARM64 runtime and Pi
certification remain pending.

`docker-compose.kernel-portability.yml` is a standalone database evaluation
manifest with project name `kokonut-kernel-portability`, a separate private
network, and project-scoped `portability-postgres-data` volume. Never combine it
with candidate/legacy manifests, override its project name to an existing
deployment, or attach an existing data directory to this evaluation service.

The build selects `Dockerfile.kernel-postgis`'s final target and the package
versions verified on AMD64 and ARM64. Platform defaults to linux/amd64; explicitly
export KOKONUT_DATABASE_PLATFORM=linux/arm64 for the ARM64 counterpart. The
mutable evaluation image tag is rebuilt for the selected architecture; do not
assume it holds both architectures simultaneously. Retain the separately recorded
artifact tags/digests for comparison and rollback evidence.

The database keeps the application database/user and data-directory convention,
publishes no host ports, and preloads pg_stat_statements for the schema's
observability extension. It uses restart=no to expose evaluation failures and
a 40-second stop period. pg_isready is process readiness, not schema certification.
No extension SQL, numbered seeds, pilot data, or migrations run automatically.

After reviewing acceptance prerequisites, load encrypted secrets and explicitly
select this isolated manifest:

```sh
export COMPOSE_PROJECT_NAME=kokonut-kernel-portability
export COMPOSE_FILE=docker-compose.kernel-portability.yml
docker compose --env-file /dev/null config --quiet
docker compose --env-file /dev/null build database
```

These are documented commands; neither deployment nor migration was performed.
Start a fresh evaluation database only when proceeding with runtime acceptance,
then direct the existing migration runner to the same explicit project/file.
Inspect its status, apply schemas through its ordered checksummed path, and
review failed migrations before any data restore. Never bypass drift detection.
Portability evaluation should not accidentally create scheduler jobs, run
ingestion, or access external blockchain providers.

The migration CLI now accepts an explicit project and one or more manifest files.
Both options are required together; filenames resolve against the invoking working
directory. Explicit selection uses the repository project directory and disables
implicit plaintext `.env` loading. Export encrypted secrets before use. Without
these options the existing ambient Compose behavior remains unchanged.

After the evaluation database has been started, the schema application command is:

```sh
python3 -m services.migration migrate --schemas-only \
  --compose-project kokonut-kernel-portability \
  --compose-file docker-compose.kernel-portability.yml
```

This command is documented, not executed. The canonical first schema migration
creates required extensions. Do not run the legacy seed script for this preparation:
it additionally applies legacy initialization, optional-provider setup, and curated
seeds. The schema-only runner preserves existing checksum validation, ordering,
advisory locks, and transactional failure handling. It applies pending migrations,
including 371–373; it does not automatically apply numbered seeds or pilot data.
Schema files can themselves contain reference data, so schema-only does not mean
that no rows are inserted. Missing application reference data remains a separate
capability acceptance concern.

## Optional application role

The `application` Compose profile adds a private API role built from the Kernel
target. It uses the same `KOKONUT_DATABASE_PLATFORM` selection as the database,
a separate evaluation image tag, and no published host ports. All six vendor
providers are disabled. The explicit command starts only the API; no scheduler
or event worker starts. Rate limiting uses the local provider.

Apply the ordered schemas to the fresh evaluation database before starting the
application. The database health dependency only confirms that PostgreSQL accepts
connections; it does not check extensions or schema readiness. The application
now selects `--require-schema`: before spawning the API it reads the bundled
numbered schema files and requires matching applied checksums in
`public.schema_migration`. Missing tracking state, missing/non-applied/mismatched
schemas, unknown applied schema IDs, or database errors prevent startup. Unknown
applied IDs intentionally block using an older image against a newer database.

The gate uses a read-only, repeatable-read transaction with connection, statement, and lock
timeouts. It never initializes tracking tables, repairs checksums, applies SQL
files, or loads seeds. It logs the failure type without database connection
details; use the explicitly selected migration CLI to inspect the cause.

Startup now reports safe categories and counts: `inventory_unavailable` means the
image lacks its numbered SQL inventory; `tracking_unavailable` means the database
has no migration tracking table; `schema_mismatch` reports missing IDs, recorded
statuses other than applied, checksum drift, and unknown applied schema IDs.
The expected count comes from that image's bundled files. A recorded row can count
as both not applied and checksum drift; the categories are not a total failure
count. Database failures still report only their exception type. No raw SQL,
database-supplied identifiers, checksums, connection addresses, or credentials
are included in these startup diagnostics.

For an existing tracking table, inspect the pending plan using the same explicit
destination:

```sh
python3 -m services.migration plan --schemas-only \
  --compose-project kokonut-kernel-portability \
  --compose-file docker-compose.kernel-portability.yml
```

The plan command requires existing tracking state. For a fresh database, use the
documented schema migration command after confirming the selected project. For
checksum drift, investigate source/image provenance and use the runner's existing
audited repair policy where applicable; do not edit recorded checksums to force
startup. Unknown applied IDs require a compatible newer image or a reviewed data
rollback, not deletion of migration history. None of these commands ran here.
Legacy/candidate runtime commands do not select the flag and retain their current
startup behavior. This is a startup check, not continuous drift monitoring or a
schema lock against concurrent migrations. Applied tracking checksums do not prove
that manually changed objects, seed data, or runtime capabilities are healthy.
Deployment coordination and the remaining acceptance gates still apply.

The gate also reads required extension names from the canonical
`schemas/postgres/000_extensions.sql` and checks their presence in
`pg_catalog.pg_extension` in the same database snapshot. The current list contains
uuid-ossp, pgcrypto, postgis, postgis_topology, pg_trgm, and pg_stat_statements.
No second hardcoded extension inventory is introduced. The inventory reader
accepts the file's simple `CREATE EXTENSION IF NOT EXISTS` statements and whole-line
comments; future unsupported SQL forms stop readiness with
`extension_inventory_unsupported` rather than silently omitting requirements.
A missing canonical file reports `extension_inventory_unavailable`.

An otherwise matching schema with missing extensions reports `extensions_missing`.
Reports include `extensions_expected` and `extensions_missing`; a schema mismatch
can also include missing-extension counts. Tracking-unavailable reports have not
yet inspected installed extensions, so their zero missing-extension count is not
a presence check. Extension versions, preload configuration, native library
execution, raster/spatial operations, and extension upgrade compatibility are not
certified by this catalog check. It never creates or upgrades extensions.

```sh
docker compose --env-file /dev/null --profile application config --quiet
docker compose --env-file /dev/null --profile application build app
```

These commands prepare the application without starting services. The separately
recorded ARM64 application build succeeded; this combined evaluation has not been
started. Application startup, route authorization, database integration, and
capability parity remain pending. This manifest does not enable the main profile
planner's ARM64 deployment option.

## Read-only readiness command

The subsequent [public relation gate](public-relation-readiness.md) adds structural
checks for the migrated API projections. It is now deployed to the AMD64 API and
worker; it does not certify grants, view predicates, or query behavior.

`python3 -m services.cli kernel schema-readiness` exposes the same gate through
the unified CLI. The standalone entry point is
`python3 -m services.core.cli schema-readiness`. Both print a JSON report with
`ready`, a category code, and counts, returning zero only when checksums match.
Unavailable probes report only their exception type. The command uses the shared
JSON/error helpers and does not start API processes, workers, or migrations.

The destination comes from the normal PostgreSQL environment, not migration
CLI Compose options. Since the evaluation database is private, run the command
inside its application image after building the latest source and starting the
database explicitly:

```sh
docker compose --env-file /dev/null \
  -p kokonut-kernel-portability -f docker-compose.kernel-portability.yml \
  --profile application run --rm --no-deps app \
  python3 -m services.core.cli schema-readiness
```

This documented command creates a temporary application container and connects
to the existing evaluation database. `--no-deps` prevents it from starting the
database implicitly. It requires exported encrypted secrets and the selected
architecture setting. No readiness command was run here. The subsequent
[paired application builds](builds/2026-10-10-readiness/README.md) include the
readiness implementation, but this manifest's separate evaluation image tag still
requires its explicit build. A successful report
checks migration tracking consistency and required extension presence, not full
application readiness.

## Preparation command planner

The optional [worker profile](portability-workers.md) can be included with
`--with-workers`. It remains opt-in; its subsequent idle AMD64 startup is recorded
in [the runtime record](portability-runtime.md).

`scripts/kernel-portability.py` prints shell-quoted commands for this standalone
evaluation project. It requires an explicit `--target-platform linux/amd64` or
`linux/arm64` and includes that platform in the printed command's environment,
so both services use the declared architecture even if the invoking shell has a
different value. Project and manifest paths are explicit; plaintext `.env`
loading is disabled. Encrypted secrets must already be exported before executing
the printed command.

```sh
python3 scripts/kernel-portability.py --target-platform linux/arm64
python3 scripts/kernel-portability.py --target-platform linux/arm64 --action build-database
python3 scripts/kernel-portability.py --target-platform linux/arm64 --action build-app
python3 scripts/kernel-portability.py --target-platform linux/arm64 --action readiness
```

Default action is quiet configuration parsing. Other actions are database build,
app build, the read-only readiness command, and project container listing (`ps`).
The planner itself never invokes Docker, loads secrets, connects to databases,
or changes data. Executing a printed readiness command creates a temporary
container and requires a previously started database; it does not start dependencies.
Review printed commands before executing them rather than piping output to a shell.

This is evaluation preparation, not a certified ARM64 deployment profile. The
main `kernel-profile.py` guard remains active. No startup, migration, cutover,
scaling, volume deletion, or legacy overlays are offered by this planner. Mutable
evaluation tags hold the most recently built architecture, so rebuild for the
declared platform and retain image identities before switching architectures.

## Acceptance and rollback

Placeholder-only Compose parsing passed for both declared architectures, and
diff checks passed. No evaluation container or volume was created. Existing
candidate and legacy data remain unchanged; runtime tests were not added or run.
Still pending: startup, full schema application, extension/raster capabilities,
spatial queries, logical backup/restore, clean shutdown/restart, package parity,
AMD64/ARM64 comparable disk measurement, combined application/database runtime,
and Pi hardware certification. The separate ARM64 app image build is recorded in
[the application build record](arm64-application.md).
The profile planner ARM64 guard remains active.

The deployment manifest is an evaluation path, not a replacement for the main
candidate. On failure stop only this explicit project's selected services and retain its
volume/logs for diagnosis. Keep legacy/candidate artifacts intact. There is no
automated volume deletion or cutover; any evaluated data must be reconciled
before selecting a production migration or rollback path.
