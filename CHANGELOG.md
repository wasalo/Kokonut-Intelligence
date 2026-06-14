# Changelog

All notable changes to the Kokonut Intelligence Platform.

## [Unreleased]

### Added
- PRD completion layer: farm registry records, inventory events, maintenance events, revenue events, MRV events, attestation requests, agent metadata, agent tasks, and action logs.
- Development local CID adapter with deterministic `local://sha256/<hash>` references.
- Registry, attestation, and agent helper CLIs for Common Data Schema validation, MRV payload preparation, private-data hash metadata, and capability manifest metadata.
- Directus metadata drift test covering invalid collection sort fields and stale field metadata.
- EAS on Celo: Foundry project with `KokonutResolver` contract (attester-gating resolver), deploy script, and fuzz-tested unit tests.
- EAS Python integration: `EASClient`, `SchemaEncoder`, `EASSigner`, offchain attestation signing/verification, and schema definitions for 5 Kokonut schemas (MRV, impact, financial, harvest, compliance).
- EAS CLI (`python3 -m services.attestation.cli`): schema registration, onchain attestation, offchain attestation, revocation, query, and chain info commands.
- Celo chain configuration: RPC URLs, EAS contract addresses, and chain config for Celo mainnet, Alfajores, Optimism, and Base.
- Celo EAS seed data (`schemas/seeds/014_pilot_celo_eas.sql`): chain indexer status and placeholder schema rows for 5 Kokonut schemas.
- CI workflow (`.github/workflows/ci.yml`): Python checks, Directus hooks build, Foundry contracts (fmt, build, test) — runs on push, PR, and manual dispatch.
- Foundry dependencies committed to repo (`contracts/lib/`): forge-std, eas-contracts, openzeppelin-contracts, openzeppelin-contracts-upgradeable.
- PostgreSQL schema constraints (`015_constraints.sql`): 18 enum types, 37 CHECK constraints, 48 auto-update triggers, 3 UNIQUE constraints, ~55 ON DELETE SET NULL, ~50 FK indexes.
- End-to-end user guide (`docs/user-guide.md`): role-based walkthroughs for Field Worker, Supervisor, Manager, Finance, Analyst, Admin, and partner roles (Buyer, Funder, Vendor, Operator) — covers data entry, workflow lifecycle, dashboards, analytics, export, SDK, and attestations.

### Changed
- JavaScript and Python SDK examples now use the canonical `draft -> submitted -> verified -> published` lifecycle.
- Documentation now states EAS/private-data boundaries, external `Kokonut-Agentic-Marketplace` scope, and deferred dApp session ingestion.
- Attestation guide updated with Celo workflow, CLI usage, offchain attestations, and private data strategy.
- Solidity contracts formatted with `forge fmt` (single-line constructor/function signatures).
- `contracts/.gitignore` no longer excludes `lib/` — Foundry dependencies now committed for CI reliability.
- CI uses committed dependencies instead of `forge install`.
- ClickHouse HTTP inserts now validate all interpolated values against strict regex patterns before SQL interpolation.
- `pendingTransitions` Map now has 30-minute TTL and 1000-entry cap to prevent memory leaks.
- Role cache in `roles.ts` now has 5-minute TTL with automatic expiration.
- `storeNoiSnapshot` now uses `INSERT ... ON CONFLICT DO UPDATE` to prevent TOCTOU races.
- `calculateNetAmount` now clamps to zero minimum (prevents negative net amounts).
- Shannon diversity index now computed across all observations for a location (not per-row).
- Field Worker create permissions now exclude `status` — lifecycle starts at `draft` by default.
- `harvest_event`, `sales_event`, `expense_event` now have `updated_at` column with auto-update trigger.
- `plot.slug` is now `NOT NULL` (consistent with `location.slug`, `farm.slug`, `partner.slug`).
- `eas_indexer.py --chain` now accepts `celo` in addition to `optimism` and `base`.
- ClickHouse backup script now dumps actual table data, not just `system.tables` metadata.
- `verification_review.result` seed data corrected from `verified` to `approved`.
- `014_directus_metadata_repair.sql` wrapped in `DO $$ EXCEPTION` guard — skips cleanly when Directus not installed.
- `expense_event.update` now re-runs auto-categorization if category is cleared.
- JS/TS SDK types corrected: `Farm.farm_type`, `Plot.slug`, `HarvestEvent.location_id`, `SalesEvent` fields, `ExpenseEvent` fields, `SensorReading.quality`, `AttestationRecord` fields.

### Fixed
- Cleared invalid Directus `sort_field` metadata for Baserow-migrated collections where no physical `sort` column exists.
- Removed stale Directus field metadata that referenced nonexistent PostgreSQL columns.
- Directus metadata snapshot test skips gracefully when gitignored `schema_latest.json` is absent (fixes CI failure).
- Workflow `USER_FIELDS` accountability stamping — `verified_by`/`rejected_by`/`submitted_by` now correctly written from `meta.accountability`.
- `subgraph_indexer.py` INSERT column `attestation_tx` corrected to `tx_hash` to match schema.
- DB connection leaks fixed in `sensor_ingester.py`, `mock_sensors.py`, `eas_indexer.py` — all use `try/finally` blocks.
- `sensor_alert.claim_id` now has FK constraint to `mrv_claim(id)`.
- Nonce double-consumption in `eas_client.py` — removed redundant `get_nonce()` from `build_transaction` calls.
- Hardcoded dev credentials removed from `services/common/db.py` — secrets now required via environment variables.
- Added `ROLE_ROUTING` for `inventory_event`, `maintenance_event`, `dashboard_dataset` — prevents unauthorized transitions.
- Added Directus permissions for `revenue_event` (Finance and Manager policies).
- Added CHECK constraints: `quantity > 0` on harvest/sales, `total_amount > 0` on sales, `amount > 0` on expense, `hours_worked > 0` on labor.

## [0.10.0] - 2026-06-12

### Added
- **Module C: Revenue Multiplier Opportunity Map** (`services/revenue_multiplier/`): 10-dimension strategic analysis identifying where Kokonut's system can multiply value
  - `crop_mix.py`: NOI/ha ranking by crop, recommends reallocation based on soil/water/market data
  - `loss_reduction.py`: Loss Pareto analysis by type, crop, severity; identifies top reduction opportunities
  - `buyer_channel.py`: Buyer performance scoring (net revenue, payment speed, returns rate)
  - `value_added.py`: Raw vs processed price delta, processing ROI estimation
  - `web3_replication.py`: On-chain funding analysis, DAO replication model viability
  - `bioinput.py`: Bioinput spend vs conventional, on-farm production ROI
  - `public_goods.py`: Actual vs forecasted allocation, funding→impact→funding cycle
  - `ecological_verification.py`: Carbon credit + biodiversity credit + impact certificate monetization
  - `partner_sponsorship.py`: Partner ROI scoring, sponsorship pipeline value
  - `regional_clusters.py`: Cluster proximity, shared infrastructure opportunities
- **Revenue Multiplier CLI**: `--location-id UUID`, `--dimension`, `--json`, `--list-dimensions`
- **Revenue Multiplier Report**: Added to `report_generator.py` as `revenue_multiplier` report type
- **6 additional pilot seed data files** for Module C dimensions:
  - `007_pilot_prices.sql`: 16 price observations (4 crops × 4 dates)
  - `008_pilot_capital_flows.sql`: 4 capital sources, 11 value flow events, 2 cash flow snapshots
  - `009_pilot_carbon_biodiversity.sql`: 6 soil carbon measurements, 8 species observations, 3 environmental baselines
  - `010_pilot_mrv_claims.sql`: 4 MRV claims, 2 verification reviews
  - `011_pilot_partners_extended.sql`: 2 additional buyer partners, 3 cross-buyer sales events
  - `012_pilot_bioinputs.sql`: 3 bioinput expenses, 1 biofactory infrastructure asset

## [0.9.0] - 2026-06-12

### Added
- **Property table** (`schemas/postgres/012_property.sql`): legal/managed property boundaries with PostGIS spatial columns, FK linked to farm
- **16 governed metric definitions** (PRD Section 16): crop_revenue, net_crop_revenue, direct_crop_cost, allocated_shared_cost, crop_noi, loss_rate_pct, operating_margin_pct, baseline_revenue, baseline_asset_value, baseline_cash_flow, value_flowed, wallet_retention, digital_lego_usage, soil_carbon_delta, biodiversity_delta, attestation_coverage
- **Ecology analytics service** (`services/analytics/ecology.py`): soil carbon before/after comparison, biodiversity metrics with Shannon diversity index, scenario comparison, sensitivity analysis
- **Ecology CLI** (`services/analytics/cli.py`): `--soil-carbon`, `--biodiversity`, `--compare-scenarios`, `--sensitivity`
- **Forecast CLI extensions**: `--compare` for scenario comparison, `--sensitivity` for variable sensitivity analysis

### Changed
- **PRD Section 7.5**: Added `protocol` table row (existed in DB but undocumented)
- **PRD Section 8**: Updated lifecycle states from Raw/Normalized/Verified/Published to Draft/Submitted/Verified/Published
- **Farm table**: Added `property_id` FK to link farms to legal properties
- **Seed data**: Pilot farm now includes property record

### Fixed
- **Report generator**: Fixed `species_observation.species_count` → `species_observation.count` column reference bug
- **Data dictionary**: Fixed display glitch in `soil_carbon_delta` formula (mixed Chinese character)
- **Metric definitions**: Replaced 10 ad-hoc metrics with 16 PRD-governed metrics

## [0.8.0] - 2026-06-12

### Added
- **Milestone 7: Pilot farm seed data & analytics**
- Pilot farm seed data (`schemas/seeds/001_pilot_farm.sql`): location, farm, plots, crops, crop cycles, partners, staff, infrastructure, wallets
- Pilot environmental data (`schemas/seeds/003_pilot_environmental.sql`): soil samples, weather observations, remote sensing, sensor devices, alert rules, sensor readings/alerts
- Pilot web3 data (`schemas/seeds/004_pilot_web3.sql`): wallet activity events, digital lego usage, attestation schemas/records, chain indexer status
- Pilot forecasts and NOI data (`schemas/seeds/005_pilot_forecasts.sql`): forecast scenarios, forecast outputs, NOI snapshots
- Pilot DAO data (`schemas/seeds/006_pilot_farm_dao.sql`): proposals, votes, delegations, treasury snapshots, metric definitions, governance settings
- Seed orchestrator (`scripts/seed-pilot.sh`): runs every `*_pilot_*.sql` seed file in sorted order
- Revenue forecast engine (`services/analytics/forecast.py`): 3-month, 6-month, 12-month projections from historical harvest/sales data
- Monte Carlo simulation for confidence intervals on projections
- CLI tools: `forecast.py` (run projections), `fortune500.py` (score & rank farms)
- Fortune 500 farm scoring engine (`services/fortune500/calculator.py`): weighted 4-pillar ranking (Financial 45%, Ecological 25%, Governance 15%, Growth 15%)
- 5-tier ranking: Platinum (800+), Gold (600+), Silver (400+), Bronze (200+), Developing
- 15 sub-metrics across the 4 pillars with normalized 0-1000 scoring
- Directus partner dashboard templates (`dashboards/directus/`):
  - Buyer view: production summary, upcoming harvests, sales history, quality grades, revenue trends
  - Funder view: financial performance, NOI trends, cost breakdown, forecasts, impact attestations, ecological outcomes
  - Vendor view: purchase summary, history, demand forecasts, payment status, category breakdown
  - Operator view: operations overview, activity timeline, crop cycles, sensors, weather, financials, remote sensing, alerts
- Row-level security rules for partner data isolation

### Changed
- Rewrote `001_pilot_farm.sql` with correct schema column names (removed nonexistent `slug`, `status` from crop; added `location_id` to crop_cycle; fixed `capacity` type to NUMERIC)
- Rewrote `003_pilot_environmental.sql` with correct column names (removed nonexistent `depth_cm`, `depth_layer`, `sample_id` from soil_sample; added `rainfall_mm` to weather_observation)
- Fixed `fortune500/calculator.py` data completeness check to use RealDictCursor column access instead of tuple indexing

## [0.7.0] - 2026-06-12

### Added
- **Milestone 5: Developer & downstream integration layer**
- OpenAPI 3.0 specification (`docs/openapi.yaml`) covering all 60+ collections with request/response schemas, filter operators, and authentication flows
- JavaScript/TypeScript SDK (`sdk/javascript/`) with typed client wrapper, 12 collection interfaces, and 4 example scripts (create farm, query NOI, sensor data, workflow)
- Python SDK (`sdk/python/`) with typed client wrapper, 13 collection method classes, error hierarchy, and 4 example scripts
- Developer sandbox: `docker-compose.sandbox.yml` with Metabase embedding, `scripts/sandbox-setup.sh` for auto-seeding API keys and sample data
- Export service (`services/export/exporter.py`): CSV/JSON/Parquet export from PostgreSQL and ClickHouse with filter support and audit logging
- Report generator (`services/export/report_generator.py`): farm summary, crop NOI, environmental impact reports with hash-verified snapshots
- Documentation: `docs/sandbox.md` (hello world tutorial), `docs/subgraph-guide.md`, `docs/attestation-guide.md`, `docs/partner-dashboards.md`, `docs/agent-access.md`, `docs/export-guide.md`
- Metabase embedding enabled: `MB_ENABLE_EMBEDDING=true` in docker-compose.yml
- `METABASE_EMBEDDING_SECRET_KEY` added to `.env.example`

### Changed
- Rewrote `docs/api-reference.md` with per-collection API docs, error formats, webhook catalog, and GraphQL reference
- Enhanced `docs/data-dictionary.md` with field-level documentation for all collections
- Updated `docs/architecture.md` with SDK layer and export services
- Updated directory structure in README with SDK and export directories

## [0.6.0] - 2026-06-11

### Added
- **Milestone 4: Real-time Sensor Streams**
- New schema `011_sensor_registry.sql`: `sensor_type` (7 seeded), `sensor_device`, `alert_rule`, `sensor_alert` tables + ALTER `mrv_claim`
- ClickHouse materialized views `003_sensor_views.sql`: `mv_hourly_sensor_stats`, `mv_daily_sensor_summary`, `mv_sensor_reading_rate`
- Sensor ingestion (`sensor_ingester.py`): batch CSV + single reading + list sensors
- Mock sensor data generator (`mock_sensors.py`): setup devices, generate readings (normal + anomaly), cleanup
- Anomaly detection engine (`anomaly_detector.py`): 8 default alert rules (soil_moisture/soil_temperature/air_temperature/humidity/light/rainfall/water_level/frost), cooldown, auto-create MRV claims for critical alerts
- Sensor types: soil_moisture, soil_temperature, air_temperature, humidity, light, rainfall, water_level

## [0.5.0] - 2026-06-11

### Added
- **Milestone 3: External data ingestion**
- ClickHouse event store: 6 event tables (`events_raw`, `wallet_events`, `sensor_readings`, `weather_events`, `financial_events`, `dlego_events`) + 5 materialized views
- New schema `010_market_data.sql`: `price_observation` table for commodity prices
- Common ingestion framework (`services/ingestion/`): base utilities (DB, logging, retry, hashing), config loader from `.env`
- Weather ingestion (`weather.py`): OpenWeatherMap API → `weather_observation` (PostgreSQL) + `weather_events` (ClickHouse)
- RPC ingestion (`rpc_indexer.py`): Ethereum/L2 wallet balance tracking via web3.py → `wallet_activity_event` + ClickHouse `wallet_events`
- Market data ingestion (`market_data.py`): World Bank Pink Sheet seed data (8 commodities, 48 price records) → `price_observation`
- Remote sensing CSV ingestion (`remote_sensing.py`): NDVI/NDRE CSV upload → `remote_sensing_observation` with auto location lookup
- EAS attestation ingestion (`eas_indexer.py`): EAS GraphQL API (Optimism/Base) → `attestation_record` + `attestation_schema`
- Chain indexer health tracking via `chain_indexer_status` table
- Ingestion logging to `ingestion_log` table for all external data sources
- Test seed data: location (Nairobi), farm, plot, wallet profiles (Vitalik on ETH + Optimism)

### Fixed
- ClickHouse HTTP port not accessible from host — added `config/clickhouse/config.d/network.xml` (`listen_host: 0.0.0.0`)
- ClickHouse schema: `Decimal15`/`Decimal18` → `Decimal128` (compatible with ClickHouse 25.3)
- Weather ingestion: column mapping aligned with actual `weather_observation` schema (no `feels_like_c`, `visibility_m` → `visibility_km`)
- Weather ClickHouse insert: switched from `clickhouse_connect` to requests-based HTTP (package didn't support native protocol)
- RPC indexer: simplified to balance check (free public RPCs don't support block range scanning)
- EAS indexer: GraphQL schema updated for `easscan.org` API (`orderBy`, `where: { equals: }` filter format, `txid` not `txHash`, `time` not `blockTimestamp`)
- EAS indexer: checksum address required (case-sensitive API)
- Market data: FAO GIEWS now requires auth — switched to World Bank Pink Sheet seed data

### Changed
- Updated `seed.sh` to apply ClickHouse schemas on setup
- Updated `.env.example` with weather, RPC, and EAS configuration
- Free public RPC endpoints: `ethereum.publicnode.com`, `mainnet.optimism.io`, `mainnet.base.org`, `arb1.arbitrum.io/rpc`

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
