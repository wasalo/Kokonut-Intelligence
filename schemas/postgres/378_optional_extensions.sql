-- 378_optional_extensions.sql
-- Add extensions introduced after the deployed 000_extensions migration.
-- Keep the Compose first-boot path in config/postgres/init.sql aligned.

CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
