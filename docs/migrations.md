# PostgreSQL Migrations

Kokonut Intelligence uses numbered SQL files as the source of truth for
PostgreSQL schema evolution. The migration runner discovers schema files and
seed files, gives each an immutable namespaced ID, validates source safety,
tracks applied checksums, and applies pending files through an explicitly
selected Compose PostgreSQL service. If no explicit Compose selection is
provided, legacy ambient Compose selection remains in effect; do not use that
default when targeting a Kernel candidate.

The normal runner path is:

```text
discover schema files, then seed files
        -> validate source IDs and SQL boundaries
        -> ensure schema_migration tracking tables
        -> reconcile compatible legacy numeric rows
        -> validate applied SHA-256 checksums
         -> acquire PostgreSQL advisory lock in the applying psql session
        -> recheck and apply each pending file
        -> record applied migration state
```

The migration runner lives in `services/migration/cli.py` and executes SQL
through the selected Compose `database` service. It does not start containers.

## Migration IDs And Discovery

The runner scans:

1. `schemas/postgres/` as `schema` migrations.
2. `schemas/seeds/` as `seed` migrations, unless `--schemas-only` is used.

Only files whose names begin with a numeric prefix and end in `.sql` are
discovered. Files are sorted by filename within each directory, with all
schema files before all seed files. IDs include the kind and complete filename:

```text
schema:001_example.sql
seed:001_example.sql
```

Schema migration numbers must be unique. Seed files may historically share a
numeric version because they are independently named seed units. Duplicate
IDs still fail closed.

Before any database work, source validation rejects:

- Duplicate migration IDs.
- Duplicate schema version numbers.
- NUL bytes in SQL.
- SQL containing a `\connect` command that could switch databases.

The runner calculates a SHA-256 checksum from the complete file contents.
Applied migration IDs and checksums are immutable records of what was run.

## Commands

```bash
python3 -m services.migration status
python3 -m services.migration validate
python3 -m services.migration plan
python3 -m services.migration migrate
python3 -m services.migration migrate --schemas-only
```

For an explicit deployment, include both `--compose-project` and
`--compose-file`. Repeat `--compose-file` for ordered overlay manifests. The
runner uses the repository root as the Compose project directory and disables
implicit `.env` loading; export the required environment values through the
approved secret loader first.

### Status

`status` initializes or upgrades the tracking tables, reconciles compatible
legacy rows, validates applied checksums, and prints every discovered migration
with its status and checksum prefix. It reports total, applied, and pending
counts.

### Validate

`validate` performs source discovery and SQL-boundary validation without
applying SQL or requiring PostgreSQL. It is useful in CI and before opening a
pull request.

```bash
python3 -m services.migration validate
python3 -m services.migration validate --schemas-only
```

### Plan

`plan` reports pending migrations without changing database state. It requires
the Compose database because it reads tracking state and validates checksums.
It does not create tracking tables or reconcile legacy rows.

```bash
python3 -m services.migration plan
python3 -m services.migration plan --schemas-only
```

`dry-run` remains an alias for `plan`.

### Migrate

`migrate` applies every discovered file whose tracking status is not `applied`.
`--schemas-only` applies PostgreSQL schema migrations while excluding all seed
files.

```bash
python3 -m services.migration migrate
python3 -m services.migration migrate --schemas-only
```

With explicit selection, the runner uses:

```text
docker compose exec -T database psql -X -U <user> -d <database>
  -v ON_ERROR_STOP=1 -A -t -F "\t"
```

The PostgreSQL service must be running under the selected project. The command
timeout for a psql invocation is one hour. `ON_ERROR_STOP=1` ensures SQL
failures are loud.

## Kernel Candidate Targeting

The candidate has a separate Compose project and database volume. A fresh
candidate does not seed or migrate itself, and its app may restart until the
schema is ready. Start only its database first, then explicitly aim the
migration runner at the same project and manifest. Example for a disposable
local project (substitute your unique project name if needed):

```bash
source scripts/load-secrets.sh

docker compose --project-directory . --env-file /dev/null \
  -p kokonut-kernel-dev \
  -f docker-compose.kernel-candidate.yml up -d database

python3 -m services.migration validate --schemas-only
python3 -m services.migration status \
  --compose-project kokonut-kernel-dev \
  --compose-file docker-compose.kernel-candidate.yml
python3 -m services.migration plan --schemas-only \
  --compose-project kokonut-kernel-dev \
  --compose-file docker-compose.kernel-candidate.yml
```

Review the selected target and migration plan. When authorized for that target,
apply schema migrations explicitly:

```bash
python3 -m services.migration migrate --schemas-only \
  --compose-project kokonut-kernel-dev \
  --compose-file docker-compose.kernel-candidate.yml

docker compose --project-directory . --env-file /dev/null \
  -p kokonut-kernel-dev \
  -f docker-compose.kernel-candidate.yml up -d --build app
```

For the `standard` profile, include
`docker-compose.kernel-standard.yml` in **both** the start and migration
selection. If adding other overlays, pass them in the same order as the
profile planner output. Do not apply seeds or pilot data as an implicit next
step: candidate seed scope is separately curated. Never point the candidate
runner at the legacy project, reuse legacy volumes, or use `scripts/seed.sh` as
a substitute for this isolated flow. See [candidate setup](refactor/kernel-candidate.md)
and the [profile planner](refactor/profile-selection.md).

## Tracking And Concurrency

The runner creates or upgrades:

- `schema_migration`: migration ID, legacy version/name, SQL reference,
  checksum, status, execution metadata, applied timestamp, and runner identity.
- `schema_migration_repair`: audited records for explicitly approved historical
  checksum corrections.

The runner uses PostgreSQL advisory lock `777204681`. Each migration acquires
the lock and rechecks its applied state in the same psql session that executes
the migration and tracking insert. A concurrent runner therefore cannot pass a
check and execute the same migration concurrently.

The migration SQL and its `schema_migration` ledger insert run inside the same
transaction. The tracking operation uses an `ON CONFLICT` update for the
namespaced migration ID.

## Legacy Tracking Rows

Older installations may contain numeric tracking rows without a namespaced
`migration_id`. The runner upgrades the tracking table and assigns a modern ID
only when both conditions match:

- The numeric version matches the discovered file prefix.
- The legacy name matches the exact filename stem.

Ambiguous or unmatched legacy rows are not silently reclassified as applied.

## Integrity Rules

- Applied files are verified against their stored SHA-256 checksum.
- Modifying an applied migration is a hard error.
- New schema changes require a new numbered migration.
- New seeds should be idempotent and should correct stale canonical metadata on
  conflict rather than relying only on `DO NOTHING`.
- The runner does not infer whether arbitrary SQL is safely idempotent; schema
  authors and reviewers must ensure that property.
- Do not manually insert an applied tracking row to bypass a failure.
- Do not delete or rewrite migration history to make drift disappear.

## Transaction Boundaries And Failure

For SQL accepted by the runner, each migration body and its `applied` ledger
row commit in the same PostgreSQL transaction while the advisory lock is held.
Balanced top-level `BEGIN`/`START TRANSACTION` and `COMMIT` wrappers in source
are normalized into that transaction; unbalanced or nested markers fail
closed. With `ON_ERROR_STOP=1`, a statement error rolls back that migration and
its ledger insert rather than leaving a committed prefix. The runner does not
support SQL that requires escaping its transaction boundary.

If a migration reports failure or the client loses its connection near
completion, inspect the selected target and ledger before retrying:

1. Stop concurrent migration attempts.
2. Run `status` against the same explicit project and manifest.
3. Confirm the migration is either fully applied with the current checksum or
   still pending; investigate any other state before proceeding.
4. Do not manually insert a tracking row or rewrite historical migration data.
5. If the migration remains pending and the transaction rolled back, correct
   its unapplied source through review or add a corrective migration as
   appropriate; then run `validate`, `plan`, and the relevant acceptance.

The advisory lock serializes runners, while the shared transaction protects
schema and ledger consistency. Neither substitutes for reviewing the selected
database, backup, migration content, and post-migration application behavior.

## Legacy Compose Bootstrap Path

`scripts/seed.sh` is the legacy integration-stack bootstrap, not the Kernel
candidate bootstrap:

```text
init.sql and extensions.sql
        -> migration runner migrate --schemas-only
        -> ClickHouse schemas
        -> Directus permissions when Directus is available
        -> curated reference seeds, when enabled
```

Run it only when deliberately targeting the legacy stack:

```bash
./scripts/seed.sh
```

The script waits for PostgreSQL, applies initialization SQL with
`ON_ERROR_STOP=1`, and applies schema migrations through the checksum-tracked
runner. ClickHouse and Directus are separate setup paths. ClickHouse is skipped
when unavailable; Directus permissions are skipped when Directus or the
permissions table is unavailable.

Curated reference seeds are applied directly after schema migration because
historical seed dependencies are not yet all suitable for the generic tracked
seed order. Set `KOKONUT_RUN_CURATED_SEEDS=false` to skip that curated phase.
The script fails on SQL errors and does not hide seed failures.

## Pilot Data Path

Pilot data is intentionally separate from schema evolution:

```bash
./scripts/seed-pilot.sh
```

This script waits for PostgreSQL, sets the session variable
`kokonut.seed_context = 'pilot'`, and applies selected support, pilot, and
reference seed files with `psql -v ON_ERROR_STOP=1`. It includes dependency
ordered files, `*_pilot_*.sql` files, and explicitly listed support/reference
files.

Pilot seeding is curated data loading, not a replacement for schema
migrations. Do not use pilot seeds to repair schema drift or to mark a schema
migration applied.

## Historical Checksum Repair

Checksum repair is an exceptional workflow for a small, explicit allowlist of
historical post-apply edits. It is not a general drift mechanism.

```bash
python3 -m services.migration repair \
  --migration-id schema:046_ecological_modeling.sql \
  --expected-old-checksum CHECKSUM_FROM_DATABASE \
  --reason "Reconcile documented historical migration edit" \
  --repaired-by OPERATOR \
  --confirm
```

Repair requires:

- An explicitly approved migration ID.
- The exact old checksum currently recorded in `schema_migration`.
- A non-empty reason.
- A named operator.
- `--confirm`.
- A live-schema validation where the approved migration requires one.
- An `applied` tracking row matching the expected checksum.

The operation takes the migration advisory lock, inserts an audit row into
`schema_migration_repair`, and updates the tracking checksum to the current
file checksum. Unknown migration IDs, unapproved checksums, identical old and
new checksums, and mismatched tracking state are rejected.

For new checksum drift, create a new migration instead.

## Tests

```bash
python3 -m pytest tests/test_migration.py -v
```

The focused migration tests cover deterministic schema-first discovery,
namespaced IDs, duplicate detection, SQL boundary validation, psql error
handling, safe variable passing, legacy reconciliation, lock and tracking
ordering, applied-file drift rejection, and audited checksum repair.

See [Platform Integrity](platform-integrity.md), [Metric Verification](metric-verification.md),
and [Scheduler and Events](scheduler-and-events.md) for related integrity and
recovery boundaries.
