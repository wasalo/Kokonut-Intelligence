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

## Failure And Recovery

Repository SQL may contain its own transaction control. Consequently, a migration file and its tracking insert cannot always share one transaction: an error can leave statements committed without an `applied` row.

1. Stop concurrent migration attempts.
2. Run `python3 -m services.migration status` and inspect the failing SQL and database state.
3. Determine which statements committed; do not blindly rerun destructive or non-idempotent SQL.
4. Repair with a new migration or make the pending migration safely idempotent when it has never been recorded as applied.
5. Run `dry-run`, then `migrate`, then the relevant tests.

Schema authors write migrations; operators review and apply them. Never bypass checksum validation or manually mark a migration applied merely to clear an error. See [Platform Integrity](platform-integrity.md) and [Metric Verification](metric-verification.md).
