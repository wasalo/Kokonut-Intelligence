# PostgreSQL Migrations

Kokonut Intelligence uses numbered SQL files as the source of truth for
PostgreSQL schema evolution. The migration runner discovers schema files and
seed files, gives each an immutable namespaced ID, validates source safety,
tracks applied checksums, and applies pending files through the Compose
PostgreSQL service.

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
through the Compose `database` service.

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

The runner uses:

```text
docker compose exec -T database psql -X -U <user> -d <database>
  -v ON_ERROR_STOP=1 -A -t -F "\t"
```

The PostgreSQL service must be running under Compose. The command timeout for a
psql invocation is one hour. `ON_ERROR_STOP=1` ensures SQL failures are loud.

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

Tracking inserts occur after the migration SQL. The tracking operation uses an
`ON CONFLICT` update for the namespaced migration ID.

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

Repository SQL may contain its own `BEGIN`, `COMMIT`, or other transaction
control. Therefore a migration file and its tracking insert cannot universally
share one transaction.

If a migration fails after some statements commit, the database may contain a
partially applied file without an `applied` tracking row. Recovery is an
operator decision, not an automatic retry:

1. Stop concurrent migration attempts.
2. Run `status` and inspect the failing SQL and live database state.
3. Determine which statements committed.
4. Do not blindly rerun destructive or non-idempotent SQL.
5. Add a corrective migration, or make the never-tracked file safely idempotent
   when that is appropriate.
6. Run `validate`, then `plan`, then `migrate`.
7. Run the relevant schema and application tests.

The advisory lock prevents concurrent runners; it does not make arbitrary SQL
atomic or repair a partially applied migration.

## Default Bootstrap Path

The default platform bootstrap is `scripts/seed.sh`, not an unrestricted
`migrate` invocation:

```text
init.sql and extensions.sql
        -> migration runner migrate --schemas-only
        -> ClickHouse schemas
        -> Directus permissions when Directus is available
        -> curated reference seeds, when enabled
```

Run it with:

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
