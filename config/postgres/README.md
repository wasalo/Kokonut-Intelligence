# PostgreSQL Initialization Scripts

SQL scripts that run on first container start (or via `scripts/seed.sh`).

## Files

| File | Purpose | When Applied |
|---|---|---|
| `init.sql` | Extensions, schema, roles, Metabase DB | First container start (Docker entrypoint) |
| `extensions.sql` | Optional/superuser extensions | Explicitly via `seed.sh` |

## init.sql

Creates the foundational database objects:

1. **Extensions**: `postgis`, `postgis_topology`, `uuid-ossp`, `pgcrypto`, `pg_trgm`
2. **Schema**: `kokonut` schema with grants to `kokonut` role
3. **Search path**: `public, kokonut` (set as database default)
4. **Metabase DB**: Creates `metabase` database if it doesn't exist

## extensions.sql

Optional extensions that require superuser or are not critical:

- `pg_stat_statements` — query analytics and performance monitoring

## How They're Applied

```bash
# Via seed.sh (standard path)
cat config/postgres/init.sql | docker exec -i kokonut-database psql -U kokonut -d kokonut_intelligence
cat config/postgres/extensions.sql | docker exec -i kokonut-database psql -U kokonut -d kokonut_intelligence
```

Also applied automatically by the Postgres Docker entrypoint on first start.

## Adding New Extensions

1. **Standard extensions** (no superuser): Add to `init.sql`
2. **Superuser extensions**: Add to `extensions.sql`
3. Re-apply: `./scripts/seed.sh` or restart the database container

## Adding New Schemas

Add to `init.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS my_schema;
GRANT USAGE ON SCHEMA my_schema TO kokonut;
```

Then update `DB_SEARCH_PATH` in `docker-compose.yml` if needed.
