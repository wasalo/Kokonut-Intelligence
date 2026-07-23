# Baserow → PostgreSQL Migration

Completed one-shot migration that moved 32 Baserow tables (1,923 rows) into the canonical PostgreSQL schema. Performed in **v0.2.0** (2026-06-10). This directory is **legacy** — it is no longer needed for new setups.

## What Happened

Baserow was used as a staff-managed data entry tool during early platform development. The migration transferred all Baserow table data into PostgreSQL via two scripts:

- **`migrate.py`** — reads Baserow via REST API, transforms fields per config, inserts via Directus REST API
- **`direct_insert.py`** — reads Baserow via REST API, inserts directly into PostgreSQL via `psycopg2` (bypasses Directus)

## Files

| File | Purpose | Status |
|---|---|---|
| `migrate.py` | Directus-mediated migration script | Legacy — completed |
| `direct_insert.py` | Direct PostgreSQL migration script | Legacy — completed |
| `schema_proposal.sql` | DDL proposals for Baserow tables | **Superseded** by canonical schemas (`061_impact_value_chain.sql`, `025_kokonut_framework_alignment.sql`, etc.) |
| `config.json` | Live config with table/field mappings | Gitignored (contains env var placeholders) |
| `config.example.json` | Example config with placeholder credentials | Committed |
| `.env.example` | Environment variable template | Committed |

## Current Status

- **Migration complete.** All 32 tables and 1,923 rows are in PostgreSQL.
- **Schema proposals superseded.** The canonical schema files define these tables more completely (with `CHECK` constraints, triggers, `source_raw` columns, etc.).
- **No active code references this directory.** The `services/ingestion/` pipeline handles all new data ingestion.
- **`source_system = 'baserow'`** values in existing data are valid historical provenance and should not be removed.

## If You Need to Reference Baserow Data

Existing rows with `source_system = 'baserow'` are in the database. Query them:

```sql
SELECT * FROM ingestion_log WHERE source_system = 'baserow';
```

## Environment Variables

The `BASEROW_API_URL` and `BASEROW_TOKEN` env vars in `.env` / `.env.sops` are legacy. They can be removed if Baserow is no longer used as a data source. The `baserow` value in the `source_system` enum (`schemas/postgres/008_governance.sql`) should be preserved as historical provenance.
