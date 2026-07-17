-- 000_extensions.sql
-- Database capabilities required by the canonical PostgreSQL schema.
-- Keep this first and idempotent so an empty database has the same
-- prerequisites as an existing Compose database.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;
