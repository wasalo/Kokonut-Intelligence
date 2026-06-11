# Changelog

All notable changes to the Kokonut Intelligence Platform.

## [Unreleased]

## [0.4.0] - 2026-06-10

### Added
- **Milestone 2: Staff-managed operations UX**
- New schema `009_operations_ux.sql`: `workflow_history`, `file_upload`, `approval` tables
- Added `submitted_at` columns to all 7 operational tables (farm_activity, harvest_event, sales_event, expense_event, loss_event, labor_event, field_note)
- Added `updated_by` and `updated_at` to loss_event, labor_event, field_note
- Role-based approval routing: finance approves expenses, managers approve operational records
- Workflow history logging — every state transition recorded to `workflow_history` table
- Rule-based AI helpers (`ai-helpers.ts`): expense auto-categorization, amount validation, harvest quantity checks, date validation, field note summarization, labor cost auto-calculation
- Metrics calculator with real SQL queries for NOI, loss rate, operating margin — writes to `noi_snapshot` table
- 5 Directus roles: Field Worker, Supervisor, Manager, Finance, Analyst
- 84 permission rules across 5 policies with row-level and field-level access control
- Seed script applies Directus permissions on setup

## [0.3.0] - 2026-06-10

### Fixed
- **CRITICAL:** Fixed Species → Crop mapping (was mapping crop data to biodiversity table)
- **CRITICAL:** Fixed all 5 Metabase SQL queries (23 broken column references: `weight_kg`→`quantity`, `returns`→`return_amount`, `discounts`→`discount_amount`, `h.date`→`harvest_date`, `se.date`→`sale_date`, `ee.date`→`expense_date`, `ec.is_direct_cost`→`ec.is_direct`)
- **CRITICAL:** Fixed all 5 Metabase JSON templates to match corrected SQL queries
- **CRITICAL:** Fixed `digital_lego_usage` field mapping (was targeting nonexistent columns)
- **CRITICAL:** Fixed F001 Activity Report field mapping (was targeting nonexistent columns)
- **CRITICAL:** Fixed Directus schema snapshot (was empty, now contains 109 collections, 1212 fields, 149 relations)
- Fixed `ecosystem_branch` table missing CREATE TABLE definition
- Fixed `DB_SEARCH_PATH` mismatch (was `kokonut,public`, now `public,kokonut` to match actual table locations)
- Fixed `asset_type` values (was `equipment`, `ecosystem_infrastructure`, now valid values `pump`, `greenhouse`)
- Fixed `net_amount` calculation bug on partial sales_event updates
- Fixed `infrastructure_asset.url` column missing from schema
- Fixed NOT NULL constraints: `plot.farm_id`, `species_observation.location_id`, `partner.slug`, `infrastructure_asset.location_id`, `infrastructure_asset.asset_type`

### Added
- Created `ecosystem_branch` table with proper columns and FK constraints
- Created PRD-required tables: `inventory_event`, `maintenance_event`, `revenue_event`
- Added 37 foreign key constraints for Baserow migration tables
- Added `url_to_array` transform for converting URLs to PostgreSQL arrays
- Added `.env.example` file for migration scripts
- Implemented NOI calculator with actual database queries
- Implemented scheduled tasks (daily NOI reconciliation, weekly metric snapshots)
- Added workflow state machine for `loss_event`, `labor_event`, `field_note`, `ai_summary`
- Updated `config.example.json` to match current configuration

### Changed
- Removed hardcoded secrets from `config.json` and `direct_insert.py` (now use environment variables)
- Removed duplicate Baserow table mappings (kept canonical sources only)
- Removed dead volume mount from `docker-compose.override.yml`
- Removed unused `@directus/sdk` dependency from extension
- Updated `migrate.py` to read credentials from environment variables
- Updated `direct_insert.py` to read credentials from environment variables

## [0.2.0] - 2026-06-10

### Added
- Migrated 32 Baserow tables to PostgreSQL (1,923 total rows)
- 22 new PostgreSQL tables created for Baserow migration: `farm_task`, `department`, `job_role`, `funding`, `impact_record`, `dependency`, `ecosystem_branch`, `resource_input`, `development_phase`, `framework_step`, `weekly_plan`, `impact_dimension`, `impact_framework`, `form_of_capital`, `sdg`, `objective`, `funding_milestone`, `milestone_outcome`, `ebf_record`, `ground_analytics_snapshot`, `activity_metric`, `activity_output`
- Directus collection metadata for 22 new tables
- Directus field definitions for key tables (40 fields)
- Foreign key constraints: `farm_task` → `farm`, `location`, `plot`, `crop_cycle`, `staff`; `funding` → `partner`
- Directus relations metadata for UI integration
- `slugify` transform for generating slugs from names
- `url_to_json` transform for converting URL strings to JSON objects
- `defaults` support in migration config for required fields
- `direct_insert.py` script for bypassing Directus API (direct PostgreSQL insertion)

### Fixed
- NOT NULL constraints relaxed: `plot.farm_id`, `species_observation.location_id`, `species_observation.observation_date`, `partner.slug`, `infrastructure_asset.location_id`, `infrastructure_asset.asset_type`
- Added `url` column to `infrastructure_asset` table
- Partner table slug auto-generation from name field
- Infrastructure asset `asset_type` default value for Baserow data
- Python 3.9 compatibility for `dict | None` syntax in migration script
- Baserow API response format handling (list vs dict)

### Changed
- Migration script now supports `defaults` config for required fields
- Migration script auto-generates slugs for `partner` table
- Field mapping updated to store URLs as JSON in `metadata` column

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
