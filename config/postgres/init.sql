-- Kokonut Intelligence Platform
-- PostgreSQL initialization script
-- Runs on first container start

-- Ensure PostGIS is available
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Cryptographic functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Trigram similarity (useful for search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create application schema
CREATE SCHEMA IF NOT EXISTS kokonut;

-- Grant usage to application role
GRANT USAGE ON SCHEMA kokonut TO kokonut;
GRANT ALL ON SCHEMA public TO kokonut;

-- Set default search path
ALTER DATABASE kokonut_intelligence SET search_path TO public, kokonut;
