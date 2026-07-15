# Migrations

The migration runner discovers numbered `*.sql` files in `schemas/postgres/` first and `schemas/seeds/` second. IDs are immutable, namespaced filenames such as `schema:001_example.sql` and `seed:001_example.sql`.

```text
discover -> ensure tracking table -> reconcile legacy rows -> validate checksums
         -> acquire PostgreSQL advisory lock -> apply pending files -> track applied
```

## Commands

```bash
python3 -m services.migration status
python3 -m services.migration dry-run
python3 -m services.migration migrate
```

The runner executes through `docker compose exec -T database psql` with `ON_ERROR_STOP=1`. The database must therefore be running under Compose.

## Invariants

- Applied files are SHA-256 checked. Modifying an applied migration is a hard error; add a new migration instead.
- One PostgreSQL session holds advisory lock `777204681` for the pending batch, preventing concurrent runners.
- Legacy numeric tracking rows are assigned modern IDs only when both numeric version and exact filename stem match.
- Duplicate discovered or tracked migration IDs fail closed.
- Seed files must be idempotent and canonical metadata must update stale rows on conflict.
- The default PostgreSQL schema bootstrap path is `scripts/seed.sh` -> the migration runner. Curated pilot/reference seeds remain a separate, explicit seed phase until all historical seed dependencies are validated.
- Historical checksum repairs are allowlisted, schema-validated where required, operator-confirmed, and recorded in `schema_migration_repair`.

## Failure And Recovery

Repository SQL may contain its own transaction control. Consequently, a migration file and its tracking insert cannot always share one transaction: an error can leave statements committed without an `applied` row.

1. Stop concurrent migration attempts.
2. Run `python3 -m services.migration status` and inspect the failing SQL and database state.
3. Determine which statements committed; do not blindly rerun destructive or non-idempotent SQL.
4. Repair with a new migration or make the pending migration safely idempotent when it has never been recorded as applied.
5. Run `dry-run`, then `migrate`, then the relevant tests.

## Historical Checksum Repair

Use this only for the documented post-apply edits that predate consistent
checksum enforcement. The command requires the exact checksum currently stored
in `schema_migration`, validates the live schema, and records an audit row:

```bash
python3 -m services.migration repair \
  --migration-id schema:046_ecological_modeling.sql \
  --expected-old-checksum CHECKSUM_FROM_DATABASE \
  --reason "Reconcile documented historical migration edit" \
  --repaired-by OPERATOR \
  --confirm
```

Unknown migration IDs and unapproved old checksums are rejected. Do not use
this workflow for new drift; create a new migration instead.

Schema authors write migrations; operators review and apply them. Never bypass checksum validation or manually mark a migration applied merely to clear an error. See [Platform Integrity](platform-integrity.md) and [Metric Verification](metric-verification.md).
