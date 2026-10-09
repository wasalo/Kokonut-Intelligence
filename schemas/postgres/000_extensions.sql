-- 000_extensions.sql
-- Database capabilities required by the canonical PostgreSQL schema.
-- Keep this first and idempotent so an empty database has the same
-- prerequisites as an existing Compose database.
--
-- This is the single canonical list of extensions. Keep it in sync with
-- config/postgres/init.sql (Compose first-boot path) and
-- config/postgres/extensions.sql (optional/superuser-gated additions).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
