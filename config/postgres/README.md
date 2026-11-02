# PostgreSQL Initialization Scripts

Legacy bootstrap SQL applied explicitly by `scripts/seed.sh`. These files are
not mounted into the PostgreSQL container's automatic
`/docker-entrypoint-initdb.d` directory. The Kernel candidate has a separate
bootstrap and ordered migration procedure; see the [current implementation
guide](../../docs/refactor/current-state-and-implementation.md).

## Files

| File | Purpose | When Applied |
|---|---|---|
| `init.sql` | Legacy foundational extensions, schema/search path, and Metabase DB | Explicitly through `scripts/seed.sh` |
| `extensions.sql` | Historical repeat declaration for `pg_stat_statements` | Explicitly through `scripts/seed.sh` after `init.sql` |

## init.sql

Creates the foundational database objects:

1. **Extensions**: `postgis`, `postgis_topology`, `uuid-ossp`, `pgcrypto`, `pg_trgm`
2. **Schema**: `kokonut` schema with grants to `kokonut` role
3. **Search path**: `public, kokonut` (set as database default)
4. **Metabase DB**: Creates `metabase` database if it doesn't exist

## Migration source immutability

`schemas/postgres/000_extensions.sql` records the baseline and is
checksum-tracked. Later extension additions belong in forward-only schema
migrations, including `schemas/postgres/315_btree_gist.sql` and the historical
`schemas/postgres/378_optional_extensions.sql`. Do not edit an applied
migration to add an extension; add a new ordered migration instead. The
migration ledger and target database determine which migrations have actually
been applied.

## extensions.sql

This legacy file repeats the `pg_stat_statements` declaration already present
in `init.sql` and the canonical extension migration. It does not represent a
separate optional extension bundle.

## How They're Applied

From the repository root, use `./scripts/seed.sh` after selecting the intended
legacy Compose target and loading its secrets. The root Compose file does not
mount either file into the Postgres image's first-boot entrypoint directory;
the script explicitly sends them to the configured PostgreSQL service.

## Adding New Extensions

1. For legacy bootstrap compatibility only, update `init.sql` or `extensions.sql` as appropriate.
2. For a schema change, add a new ordered migration instead of changing an already-applied migration.
3. Use the documented seed/migration runner for the explicitly selected target; restarting the database does not apply these files.

## Adding New Schemas

For legacy bootstrap compatibility, add to `init.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS my_schema;
GRANT USAGE ON SCHEMA my_schema TO kokonut;
```

Apply with `./scripts/seed.sh`. Kernel schema changes belong in ordered
migrations and must use the candidate rollout procedure.
