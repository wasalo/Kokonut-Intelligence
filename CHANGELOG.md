# Changelog

All notable changes to the Kokonut Intelligence Platform.

## [Unreleased]

## [0.1.0] - 2026-06-10

### Added
- Repository scaffold with monorepo structure (`apps/`, `services/`, `schemas/`, `extensions/`, `migrations/`, `scripts/`, `config/`, `docs/`)
- Docker Compose stack: PostgreSQL 14 + PostGIS 3.4, Directus 11.17.4, Redis 7, ClickHouse 25.3, Metabase
- 8 PostgreSQL schema files with 58 custom tables across locations, crops, operations, finance, environmental, web3, modeled outputs, and governance domains
- 19 expense categories seeded (12 direct, 7 shared)
- 16 governed metric definitions with formulas, source tables, inclusion/exclusion rules
- TypeScript Directus extension (`kokonut-hooks`) with lifecycle hooks for NOI auto-calculation and workflow state machine
- Python Baserow migration script with field mapping config and dry-run support
- Shell scripts: `setup.sh` (bootstrap), `seed.sh` (schema + data), `backup.sh` (database backup), `schema-snapshot.sh` (Directus export)
- ClickHouse analytics schema: events table with event sourcing pattern, materialized views
- Documentation: architecture, data dictionary, deployment guide, API reference
- `.env.example` template for environment configuration

### Fixed
- ClickHouse `experimental.xml` invalid top-level setting moved to profiles section
- ClickHouse `users.d` mount removed (blocked entrypoint from writing default-user.xml)
- `docker-compose.override.yml` password overrides conflicting with `.env`
- Metabase port changed from 3000 to 3001 (conflicted with local Next.js server)
- Metabase requires PostgreSQL 14+ — upgraded from `postgis/postgis:13-3.4` to `postgis/postgis:14-3.4`
- Metabase separate `metabase` database created on PostgreSQL init
- TypeScript extension type annotations fixed for Directus 11 compatibility
