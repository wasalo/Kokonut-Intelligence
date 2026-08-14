-- Additional extensions (can be applied later)
-- This file is for extensions that require superuser or are optional
--
-- NOTE: the canonical extension list lives in schemas/postgres/000_extensions.sql.
-- This file is kept for the legacy bootstrap path (scripts/seed.sh applies it
-- after init.sql); its contents are idempotent and already covered there.

-- pg_stat_statements for query analytics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
