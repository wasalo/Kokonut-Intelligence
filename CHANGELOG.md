# Changelog

All notable changes to the Kokonut Intelligence Platform.

## [Unreleased]

### Added
- **Bio Factory Operations Hub**: Added `043_bio_factory_operations.sql` with 7 governed tables (bio_factory_batch, bio_input_provenance, bio_recipe_library, bio_factory_distribution, bio_factory_quality_test, bio_ingredient_composition_reference, bio_regional_input_availability), 5 public views, 20 ingredient composition entries, 8 LAC regional inputs, 8 seeded recipes (vermicompost, bokashi, compost tea, sargassum extract, fish emulsion, manure tea, aerobic compost, seaweed extract), 3 Adelphi pilot batches, 6 input provenance rows, distribution tracking, quality testing, `services.agents.bio_factory_agent`, 5 report types (42 total), 5 dashboards (57-61), EAS schema `kokonut-bio-batch` registered on Celo mainnet, docs, and tests.
- **Kokonut Commons governance layer**: Added `041_kokonut_commons_governance.sql` with anti-capture governance policies, flexible redistribution policies, federation protocols, algorithmic redistribution mechanisms, participatory signal experiments, public-safe views, dashboards, Adelphi examples, `services.agents.kokonut_commons_agent`, report types, docs, and tests.
- **Open Source Capitalist scaling layer**: Added `040_open_source_capitalist_scaling.sql` with farm launch unit economics, network scaling targets, adoption barrier assessments, perpetual value stress tests, open-source artifact reuse records, public-safe views, dashboards, Adelphi examples, `services.agents.open_source_capitalist_agent`, report types, docs, and tests.
- **Regenerative outcomes and stewardship layer**: Added `039_regenerative_outcomes_and_stewardship.sql` with grant-facing regenerative outcome summaries, community governance mechanisms, replication readiness assessments, adaptive stewardship reviews, public-safe views, dashboards, Adelphi examples, `services.agents.regenerator_agent`, report types, docs, and tests.
- **GNH alignment and inclusion layer**: Added `038_gnh_alignment_and_inclusion.sql` with GNH domain assessments, cultural preservation plans, renewable energy plans, vulnerable group access plans, foundational well-being observations, public-safe views, dashboards, Adelphi examples, `services.agents.gnh_agent`, report types, docs, and tests.
- **Commons liberation and stewardship layer**: Added `037_commons_liberation_and_stewardship.sql` with time liberation observations, capital alignment assessments, governance inclusion observations, land stewardship commitments, public-safe views, dashboards, Adelphi examples, `services.agents.commons_agent`, report types, docs, and tests.
- **Capital efficiency and utility layer**: Added `036_capital_efficiency_and_utility.sql` with scenario-based capital efficiency, regenerative practice payback, governance throughput, and capital-provider utility records; public-safe views, dashboard datasets, Adelphi pilot examples, `services.agents.capital_efficiency_agent`, report types, docs, and tests.
- **Financial resilience and scaling layer**: Added `035_financial_resilience_and_scaling.sql` with financial sustainability plans, risk mitigation registers, scaling roadmap milestones, Green Paper publication review, public-safe views, dashboard datasets, Adelphi pilot examples, `services.agents.resilience_agent`, new report types, docs, and tests.
- **Holistic well-being and cultural context layer**: Added `034_holistic_wellbeing.sql` with cultural context records, well-being metric observations, participatory action traceability, and public-safe views; seeded well-being metric definitions and dashboards; added Adelphi pilot examples for Spanish-language summaries, operator capability, community trust, and feedback-to-metric traceability; added `services.agents.wellbeing_agent`, `holistic_wellbeing` report snapshots, docs, and tests.
- **EBF acceptance-quality closure**: Linked public EBF carbon scores to published Level 6 third-party verified carbon `impact_claim` records and added DB-backed EBF integration checks for schema/view behavior.
- **EBF backlog gap fixes**: Added service-level EBF publication gates, draft scorecard CSV import, aggregate stakeholder-feedback equity scoring, dashboard compatibility files, and per-pillar scoring wrapper modules without breaking existing paths.
- **EBF PR-sequence gap closure**: Added implementation memo, advisor guide, EBF operator/reviewer guide sections, Metabase scorecard JSON dashboard, standalone EBF agent modules, trust graph Mermaid export, and dedicated trust graph/agent tests.
- **EBF P2 portfolio and CIDS integration**: Added EBF portfolio messy-rollup analytics, P2 portfolio dashboard dataset/SQL, explicit EBF-to-CIDS `IndicatorReport` metadata, EBF scorecard and trust graph guides, and P2 validation tests.
- **EBF P1 operations layer**: Added farm-specific EBF metric profiles, calibration session/decision records, trust graph nodes/edges, improvement recommendations, evidence-gap/calibration views, EBF dashboard datasets, CSV templates, JSON exports, report snapshots, agent task catalogue entries, and agent safety guards for EBF draft-only workflows.
- **EBF P0 scorecard foundation**: Added first-class EBF pillars, 70 default rubric bands, scorecard and score evidence tables, public maturity gates, carbon Level 6 score gating, public-safe EBF views, CIDS-compatible metric definitions, and CI coverage for the P0 schema/rubric layer.
- **Green Paper V1 comprehensive document**: Replaced 38-line outline with full 15-section publication-ready document (~1,000 lines) covering executive summary, problem statement, system architecture, data lifecycle, evidence maturity model, CIDS mapping, stakeholder feedback, impact claims, agent safety, Web3 verification, carbon and environmental impact, reporting principles, Common Foundations checklist, publication boundaries, pilot data (Kokonut Adelphi), and glossary with 28 footnote references.

### Fixed
- **Acceptance criteria compliance pass**: Implemented missing workflow enforcement for Green Paper V1 acceptance criteria.
  - Added 7-day review period enforcement for stakeholder feedback verification in `extensions/kokonut-hooks/src/workflow.ts`.
  - Added 30-day discussion period enforcement for metric proposal approval in `extensions/kokonut-hooks/src/metric-proposal.ts`.
  - Regenerated Directus schema snapshot to include Phase 1 collections (`stakeholder_feedback`, `stakeholder_feedback_review`, `stakeholder_outcome`, `impact_claim`, `metric_proposal`, `evidence_maturity_level`).
  - Added dedicated "Stakeholder Feedback Submission" section to `docs/operator-guide.md`.

### Added
- **Backlog closure pass**: Added remaining Green Paper backlog assets for portfolio analytics, spreadsheet exchange, Common Foundations checks, workflow permissions, and missing review docs.
  - `services/analytics/portfolio.py`: portfolio theme summary with conservative confidence labels and no farm ranking.
  - `services/export/spreadsheet_bridge.py`: CSV template, dry-run validation, draft import, and verified/published export for `farm_activity`.
  - `docs/common-foundations-checklist.md`, `docs/participatory-metrics.md`, `docs/spreadsheet-guide.md`, `docs/agent-safety.md`, and `docs/public-report-disclaimer.md`.
  - Added Directus permissions for stakeholder feedback review and metric proposal workflows.
- **Phase 4 and Phase 5 Green Paper agent/documentation layer**: Added agent task catalogue, CIDS export agent, stakeholder feedback synthesis agent, and Green Paper V1 documentation.
  - `services/agents/tasks.py`: task catalogue and lightweight output schema validation for Green Paper agent tasks.
  - `services/agents/cids_agent.py`: read-only CIDS export agent over the canonical CIDS exporter.
  - `services/agents/feedback_agent.py`: stakeholder feedback synthesis agent that uses public summaries and aggregate private/no-consent signals, with optional draft `ai_summary` storage.
  - `docs/agent-workflows.md`, `docs/stakeholder-feedback.md`, `docs/operator-guide.md`, `docs/reviewer-guide.md`, and `docs/green-paper-v1.md`: Green Paper V1 operating, review, and publication guidance.
- **Phase 3 analytics and dashboards**: Added Green Paper V1 portfolio evaluation, evidence review dashboards, and public-interest report context.
  - `schemas/clickhouse/005_portfolio_views.sql`: ClickHouse views for portfolio location activity, monthly evaluation, and portfolio evaluation summary using existing analytical event mirrors.
  - `dashboards/metabase/sql/20_evidence_gap_dashboard.sql` and `20_evidence_gap_dashboard.json`: claim maturity, public threshold, carbon publication, and missing evidence-link review dashboard.
  - `dashboards/metabase/sql/21_stakeholder_feedback_dashboard.sql` and `21_stakeholder_feedback_dashboard.json`: stakeholder feedback consent, sentiment, review, and privacy dashboard.
  - `services/export/report_generator.py`: report snapshots now attach public-interest context, limitations, evidence gaps, public stakeholder voice, and public claim summaries.
  - `docs/reporting-principles.md`: public-interest reporting principles for Green Paper outputs.
- **Phase 2 workflows and review hooks**: Added Directus workflow modules for stakeholder feedback, participatory metric proposals, impact claim review, and agent safety/audit enforcement.
  - `extensions/kokonut-hooks/src/feedback.ts`: private-by-default stakeholder feedback validation, explicit public-consent checks, public summary requirement, and review log helper.
  - `extensions/kokonut-hooks/src/metric-proposal.ts`: participatory metric proposal state machine (`proposed`, `discussed`, `approved`, `implemented`, `deprecated`, `rejected`) with reviewer/date stamping and workflow history logging.
  - `extensions/kokonut-hooks/src/impact-claim.ts`: public claim validation, review stamping, and Level 6 external-verification guardrails for public carbon claims.
  - `extensions/kokonut-hooks/src/agent-safety.ts`: Directus-side safeguards for `agent_task`, `ai_summary`, and `agent_action_log`, including high-risk action flagging and human-approval requirements.
  - `services/agents/safety.py`: Python helper for assessing, blocking, hashing, and auditing agent actions before writes.
  - Extended lifecycle routing for `stakeholder_feedback`, `stakeholder_outcome`, and `impact_claim`; added hook/unit tests and CI coverage.
- **CIDS Essential Tier and impact accountability foundation**: Added evidence maturity levels, private-by-default stakeholder feedback, stakeholder outcomes, extended impact claims, participatory metric proposals, DB-level agent safety constraints, public carbon claim Level 6 gating, and a CIDS v3.2.0 Essential Tier JSON-LD exporter.
- **Carbon & Regenerative Framework Advancement**: Full implementation of 9 new tables, 4 views, 2 seed files, and analytics CLI for grant-reviewer-grade carbon evidence.
  - `ghg_emission_factor`: IPCC-based reference emission factors (fuel, fertilizer, pesticide, transport, machinery, electricity) with regional overrides.
  - `ghg_emissions_inventory`: Transport, machinery, and input emissions tracking with CO2e computed from emission factors.
  - `tree_inventory`: Above-ground carbon via allometric model (tree count, height, DBH → biomass → carbon → CO2e).
  - `underplanting_event`: Companion species planting records with survival tracking.
  - `carbon_benchmark`: Tree system carbon benchmarks (coconut, oil palm, mango, cacao, mixed agroforestry, native forest).
  - `regenerative_practice_checklist`: Scored 0-5 per-principle assessment across 5 Principles of Regeneration.
  - `framework_phase`: Framework implementation phase tracking (baseline → monitoring → verified → published).
  - `climate_impact_summary`: Annual climate-impact summary with sequestration, emissions, biodiversity, and regenerative score.
  - `operations_protocol`: Versioned handbook sections for soil management, biodiversity, emissions tracking, data entry, and reporting.
  - `v_regenerative_score_summary`: Regenerative practice score summary view.
  - `v_ghg_emissions_summary`: GHG emissions summary by category view.
  - `v_carbon_balance`: Carbon balance (sequestration vs emissions) view with net position classification.
  - `v_framework_phase_status`: Current framework phase per location view.
  - `services/analytics/carbon_balance.py`: Analytics module for GHG emissions, tree carbon, carbon balance, and regenerative scoring.
  - CLI flags: `--carbon-balance`, `--ghg-emissions`, `--tree-carbon`, `--regenerative-score`, `--emission-factors`, `--carbon-benchmarks`.
  - Report generator: `climate_impact` report type combining all carbon framework analytics.
  - Seeds: 19 emission factors (IPCC 2006), 8 carbon benchmarks (literature-based), 4 operations protocols, Adelphi pilot data (tree inventory, underplanting, GHG emissions, framework phases, practice checklist, climate-impact summary).

### Fixed
- **Forecast bed-area lookup**: Fixed the per-square-meter forecast path to resolve plots through `plot -> farm -> location` instead of referencing nonexistent `plot.location_id`.
- **Stale pilot governance drift**: Legacy `P001`/`P002`/`P003` Optimism governance rows are realigned to Gnosis/Moloch metadata during Adelphi alignment.
- **MVP definition-of-done runtime gaps**: Closed pilot lifecycle gaps so the seeded Kokonut Adelphi pilot can pass the full MVP verifier end-to-end. Pilot expenses and harvests now receive deterministic source lineage, MRV claim statuses normalize to canonical lifecycle values, public attestation summaries join through `subject_type/subject_id`, and dashboard/metric version seeds are applied by `seed-pilot.sh`.
- **Metric computation runtime failures**: Fixed `allocated_shared_cost` to join `crop_cost_allocation.expense_id`, escaped the force-majeure `LIKE` pattern in `loss_rate_pct`, normalized `source_record_ids` before `metric_value` insertion, and added `--verify` support so computed MVP metrics can populate partner-safe public metric views.
- **Schema idempotency with pilot data**: Expanded `schema_version.version`/master `schema_version` columns to `VARCHAR(50)`, normalized legacy lifecycle/indexer labels before enum checks, allowed zero-quantity/zero-amount secondary harvest and sale rows, and made unique constraints re-runnable on existing databases.
- **Agent summary governance**: Added Directus `ai_summary` permissions for Agent Read-Only/Write/Full roles and tightened `services.agents.ai_summary` queries to read governed approved data (`verified`/`published`) for sales, expenses, and harvests.
- **Forecast retained value runtime error** (`forecast/engine.py`): Moved retained-value calculation after `total_noi` aggregation so forecasts no longer reference `total_noi` before assignment.
- **Revenue multiplier forecast timestamp mismatch**: Replaced `forecast_output.created_at` ordering with schema-aligned `forecast_output.calculated_at` in all 10 revenue multiplier dimensions and Fortune500 forecast integration.
- **Revenue multiplier canonical schema alignment**: Replaced legacy placeholder table/column references (`sales`, `buyer`, `capital_event`, `crop_input`, `soil_health`, `shared_resource`, `fortune500_output`, `carbon_data`, `outputs`) with canonical PostgreSQL tables (`sales_event`, `partner`, `value_flow_event`, `expense_event`, `soil_sample`, `infrastructure_asset`, `environmental_baseline`, `forecast_output.value`) so all 10 dimensions run against the live schema.
- **Remote sensing bbox and ClickHouse safety** (`remote_sensing.py`): Preserved bbox CSV fields through parsing, added source validation, and added strict UUID/timestamp/source/number validation before ClickHouse SQL interpolation.
- **Public/export/privacy guardrails**: `v_public_metric_summary` now exposes only verified metric values; report snapshots generated by the CLI are frozen on insert; governed exports default to `verified/published`; public attestation payloads reject sensitive/private evidence keys and data URIs.
- **loss_rate_pct schema mismatch** (`loss_rate_pct.py`): Replaced invalid `harvest_event.saleable_quantity` reference with schema-aligned saleable output derivation from `quantity - COALESCE(loss_amount, 0)`, clamped at zero.
- **Critical: gnosis_indexer treasury INSERT schema mismatch** (`gnosis_indexer.py`): Fixed `insert_treasury_event()` — column names were wrong (`direction` → `flow_direction`, removed non-existent `protocol_id`/`metadata`, added `event_date`). Fixed `decode_withdraw()` to use `flow_direction` and `event_date` instead of `direction` and `block_timestamp`. Treasury events now store correctly.
- **eas_indexer race condition** (`eas_indexer.py`): Replaced manual `SELECT` + `INSERT` with `ON CONFLICT (attestation_uid) DO NOTHING` for atomic deduplication.
- **remote_sensing bbox PostGIS geometry** (`remote_sensing.py`): Changed `build_bbox()` from `json.dumps([west, south, east, north])` to `SRID=4326;POLYGON(...)` WKT format for proper PostGIS geometry storage.

### Added
- **EBF basic onboarding profile fields**: Added `027_farm_onboarding_profile.sql` with farm logo, traditional name, languages, global certifications, data privacy status/criteria, economic sectors, and credits registries on `farm`.
- **Tenure and rights assessment**: Added `tenure_rights_assessment` for property/farm-linked tenure, nearby-area survey, community effects forecast, risk level, mitigation, and source lineage.
- **DAOIP-5 project metadata**: Added DAOIP-5 project publication fields to `farm_registry_record` and `v_daoip5_project_json` for JSON-LD project export compatibility.
- **Data Hub flora/fauna and crop forecast views**: Added `v_public_farm_places`, `v_public_flora_fauna_summary`, `v_crop_forecast_summary`, and `v_public_project_carbon_credit_index` for farm-specific places, species/crop forecast summaries, and project carbon-credit indexing.
- **Forecast crop survival outputs**: Forecast engine now writes per-cycle `crop_projected_revenue_usd` and `crop_survival_rate_pct` outputs based on actual production versus forecasted production.
- **Adelphi onboarding seed**: Added `026_pilot_farm_onboarding.sql` with Adelphi EBF onboarding fields, DAOIP-5 metadata, crop expected revenue values, tenure assessment, and carbon credit attestation plan.
- **Milestone 1 — Ground Analytics normalized schema**: Added `026_ground_analytics.sql` with active canonical tables for `plant_analysis`, `water_analysis`, `disease_observation`, and `irrigation_program`, using governed lifecycle status plus source lineage fields.
- **Adelphi ground analytics seed data**: Added `025_pilot_ground_analytics.sql` with published plant scouting, water quality, disease scouting, and irrigation program records linked to Kokonut Adelphi plots, crop cycles, and water access sources.
- **Ground analytics MVP verifier coverage**: Extended `tests/test_mvp_done.py` to assert ground analytics table existence, Adelphi pilot records, source lineage completeness, and canonical lifecycle values.
- **Kokonut Adelphi framework alignment**: Added `025_kokonut_framework_alignment.sql` with canonical framework, impact mapping, Colony/Guild, DAO proposal, farm zone, and regenerative practice evidence tables.
- **Impact framework reference data**: Added SDGs, 8 Forms of Capital, Pillars of Value, EBF dimensions, CRISP dimensions, and 5 regeneration principles via `023_impact_frameworks.sql`.
- **Adelphi alignment seed**: Added `024_adelphi_alignment.sql` to converge existing seeded databases on Kokonut Adelphi, Celo EAS metadata, Gnosis DAO metadata, syntropic farm zones, practice evidence, Colony-backed Guild records, and DAO proposal records.
- **MVP verifier coverage**: Extended `tests/test_mvp_done.py` to assert Adelphi identity, Farm Registry state, Celo schema freshness, Gnosis DAO metadata, framework reference rows, Adelphi impact mappings, Guild records, and public-view filtering.
- **MVP definition-of-done verifier**: Added `tests/test_mvp_done.py` and `scripts/verify-mvp.sh` to assert pilot baselines, operational data, source lineage, governed metrics, environmental baselines, Web3 links, forecasts, dashboard datasets, public views, MRV/attestation readiness, schema/metric versions, and agent summary permissions. `ci-check.sh` now runs the verifier when the local database is available.
- **Verified metric computation path**: `scripts/compute-metrics.sh` now runs `python3 -m services.metrics --compute --all-locations --verify --json`, producing verified metric values for public aggregate views after seeding.
- **Digital Lego verification flag**: Added `digital_lego_usage.verified` plus index and pilot seed updates so `digital_lego_usage` metrics count approved Web3 interactions.
- **Risk mitigation guardrails**: Added `024_metric_governance_enforcement.sql` to automatically bump `metric_definition.version` and create `metric_version` rows when metric semantics change.
- **Milestone 3 Stage 1 — Source lineage completeness**: Created `schemas/postgres/023_source_lineage_fix.sql` migration to add missing `source_raw`, `updated_at`, `updated_by`, `verified_by`, `verified_at`, `rejection_reason`, `schema_version` columns to `loss_event`, `labor_event`, and `field_note` tables (all columns already existed from 009_operations_ux.sql — migration is idempotent)
- **Milestone 2 Stage 1 — Evidence validation hooks**: Created `extensions/kokonut-hooks/src/evidence-helpers.ts` with `validateEvidenceUrls()` (max 10 files, URL length), `validateFileUpload()` (type whitelist, 50MB limit), and `validateFieldNoteImages()` (max 20 images, URL format check)
- **Milestone 2 Stage 1 — Hook wiring**: Added evidence validation to `expense_event.create`, `sales_event.create`, `harvest_event.create`, `loss_event.create`, and `field_note.create` filter hooks
- **Milestone 2 Stage 1 — Field Worker source fields**: Updated all 7 Field Worker `create` permissions to include `source_system,source_id,source_raw`; updated `field_note.update` to include source fields
- **Milestone 3 Stage 2 — ClickHouse remote sensing**: Added `remote_sensing_events` table + `insert_clickhouse()` dual-write in `remote_sensing.py`
- **Milestone 3 Stage 2 — ClickHouse financial events**: Added `writeFinancialEvent()` dual-write in hooks for `sales_event.create` and `expense_event.create`
- **Milestone 3 Stage 2 — ClickHouse attestation events**: Added `attestation_events` table + `insert_clickhouse()` dual-write in `eas_indexer.py` and `subgraph_indexer.py`
- **Milestone 1 — Plot slug fix**: Added `slug` values (`plot-a`, `plot-b`, `plot-c`) to pilot plot INSERT to satisfy NOT NULL constraint
- **Milestone 1 — Crop cost allocation**: 126 rows in `crop_cost_allocation` (21 shared expenses × 6 crop cycles); area-based proportional allocation: Maize (23.53%), Cassava (17.65%), Beans/Sweet Potato (11.76%)
- **Milestone 1 — NOI snapshots**: 3 missing snapshots for Beans Cycle 1 ($1,807.65, 81.79%), Sweet Potato Cycle 1 ($2,175.65, 85.73%), Beans Cycle 2 ($1,503.65, 79.94%)
- **Milestone 1 — Location Overview dashboard**: `dashboards/metabase/sql/00_location_overview.sql` + `00_location_overview.json` — per-location KPIs with baseline comparison
- **Caddy reverse proxy** (Phase 2): TLS termination (self-signed in dev, real certs in prod), request logging, security headers. `config/caddy/Caddyfile` + `caddy` service in docker-compose.yml
- **CORS tightening**: Updated `CORS_ORIGIN` to include `https://localhost` for Caddy TLS
- **Gnosis indexer topic hash fix**: Corrected all 8 Moloch v2 event topic hashes from ABI keccak256 (were incorrect placeholder hashes)
- **Docs/images placeholder**: `docs/images/README.md` with screenshot naming convention and capture instructions
- **Metric calculator bug fixes**:
  - Fixed `loss_rate_pct` operator precedence: `(1 - net/gross) * 100` now correctly computes percentage (was `1 - net/gross * 100`)
  - Added force majeure exclusion to `loss_rate_pct` (excludes harvest events where `loss_reason` contains "force majeure")
  - Added harvest event IDs to `loss_rate_pct` source_record_ids (was returning empty array)
  - Fixed `operating_margin_pct` to delegate to `compute_crop_noi()` and `compute_net_crop_revenue()` sub-calculators (was computing inline NOI, ignoring `allocated_shared_cost`)
  - Fixed `digital_lego_usage` missing `WHERE dl.verified = TRUE` filter (was counting all interactions, not just verified)
- **4 baseline metric calculators**:
  - `baseline_revenue.py` — reads `location.baseline_revenue`
  - `baseline_asset_value.py` — reads `location.baseline_asset_value`
  - `baseline_cash_flow.py` — reads `location.baseline_cash_flow`
  - `baseline_cost.py` — reads `location.baseline_cost`
  - All 17 metric keys now have registered calculators
- **Metric governance seed data**: `schemas/seeds/022_metric_governance.sql` — populates `validation_tests`, `report_usage`, and `deprecation_policy` for all 17 metric definitions
- **Metric calculator tests**: `tests/test_metrics.py` — 12 tests covering calculator registration, formula correctness, governance fields, and structural validation
- **OpenAPI spec**: Added `validation_tests`, `report_usage`, `deprecation_policy` to `MetricDefinition`, `MetricDefinitionCreate`, and `MetricDefinitionUpdate` schemas
- **Data dictionary**: Updated metric table with `Report Usage` and `Validation` columns
- **Structured logging**: `services/common/logging.py` — Python `logging` setup with namespaced loggers, stderr for warnings/errors, stdout for info. `KOKONUT_LOG_LEVEL` env var.
- **Migration runner**: `python3 -m services.migration {status|migrate|dry-run}` — tracks applied SQL files in `schema_migration` with SHA-256 checksums, timing, and status. Discovers numbered files from `schemas/postgres/` and `schemas/seeds/`.
- **Centralized retry config**: `RETRY_MAX_RETRIES`, `RETRY_BACKOFF`, `RETRY_JITTER` in `services/ingestion/config.py`, overridable via env vars.
- **Improved retry decorator**: Catches only transient exceptions (network, timeout, connection errors). Adds jitter to prevent thundering herd. Uses centralized config defaults.
- **Retry coverage extended**: Added `@retry` to `gnosis_indexer.py`, `rpc_indexer.py`, `market_data.py`, `remote_sensing.py`, `sensor_ingester.py` (was only on weather, eas_indexer, subgraph_indexer).
- **Operational logging migration**: Converted ~60 `print()` calls to `logger.info/warning/error` across 8 ingestion modules (weather, gnosis, rpc, market, remote_sensing, sensor, eas, subgraph, mock_sensors).
- **Environmental Reporting — Dashboards show change over time**:
  - 6 new time-series SQL files for Metabase: NDVI trend (line), soil carbon trend (line), biodiversity trend (line), soil health trend (line), rainfall trend (area), crop diversity trend (bar)
  - 6 new cards in `06_eagle_view.json` replacing the point-in-time "Environmental Health" table card with time-series visualizations
- **Financial Reporting — Farm-level operating margin**:
  - Fixed `14_farm_operating_margin.sql` JOIN bug: was joining `ns.location_id = l.id` (attributing all location NOI to every farm); now traverses `crop_cycle → plot → farm`
  - Added "Farm Operating Margin" card to `06_eagle_view.json`
- **API Security — Phase 1 hardening**:
  - Removed PostgreSQL port `5432` and ClickHouse ports `8123`/`9000` host mappings from `docker-compose.yml`
  - Added Directus rate limiting: `RATE_LIMITER_ENABLED=true`, `RATE_LIMITER_STORE=redis`, 100 req/s, 5 login attempts/15-min lockout
  - Added CORS config: `CORS_ORIGIN` env var (defaults to `http://localhost:8055,http://localhost:3001`)
  - Added `PUBLIC_RESTRICT=true` to disable unauthenticated data access
  - Added named Docker networks: `databases` (database, cache, clickhouse) + `apps` (directus, metabase)
  - Strengthened `.env.example` placeholders: `replace-with-strong-password-min-24-chars`
  - Fixed 8 SDK example hardcoded `password123` → env var references (Python `os.environ`, JS `process.env`)
- **Blockchain Indexing — Phase 1 Gnosis Chain**:
  - Added `GNOSIS_RPC_URL` to `services/ingestion/config.py` + `CHAIN_RPC_MAP`
  - Added `KOKONUT_DAO_CHAIN` and `KOKONUT_MOLOCH_ADDRESSES` constants (treasury, token_manager, $vKKN, Loot)
  - Created `contracts/abis/MolochV2.json` — 9 event definitions (SubmitProposal, ProcessProposal, VoteProposal, Ragequit, etc.)
  - Created `services/ingestion/gnosis_indexer.py` — Gnosis Chain Moloch DAO event indexer with log filtering, event decoding, PostgreSQL + ClickHouse writes, sync state tracking
  - Added `gnosis` and `celo` to `rpc_indexer.py --chain` CLI choices
  - Created `schemas/seeds/020_gnosis_chain.sql` — chain indexer status + 4 wallet profiles + Kokonut Treasury protocol record
- **Modeled Outputs — Gap closure**:
  - Created `schemas/seeds/021_metric_versions.sql` — seeded v1 for governed metric definitions
  - Created `services/agents/ai_summary.py` — 3 generators (operations, financial, environmental) + combined + CLI with `--list`, `--verify`
  - Created `services/export/dataset_refresh.py` — executes stored SQL queries from `dashboard_dataset` + CLI with `--list`, `--all`
  - Added `--auto` flag to `services/export/report_generator.py` — generates all report types in one run (currently 37)
- **Module E: Environmental Metrics — 3 SQL bug fixes**:
  - `ecology.py`: `reading_value` → `value` in `ndvi_trends()` and `intervention_impact()`
  - `ecology.py`: `condition_rating` → `condition_status` in `soil_health()`
  - `ecology.py`: `SUM(cost)` → `SUM(labor_cost)` in `water_access_summary()`
- **Module E: 3 new environmental analytics functions**:
  - `soil_health()`: Latest soil condition rating + pH + organic matter percentage
  - `water_access_summary()`: Total water sources + access type distribution + infrastructure count
  - `environmental_baseline()`: Latest environmental metrics snapshot (soil carbon, water quality, biodiversity, NDVI)
- **Module E: 3 new CLI flags**: `--soil-health`, `--water-access`, `--environmental-baseline`
- **Module E: Water access seeds** (`schemas/seeds/018_module_e_water_access.sql`): 3 water access records (borehole, rainwater, river)
- **Per-square-meter revenue logic**:
  - Schema: `schemas/postgres/020_per_sqm_revenue.sql` — `plot.bed_count` (INTEGER), `plot.bed_area_sqm` (NUMERIC(10,2))
  - Seeds: `schemas/seeds/019_per_sqm_pilot.sql` — Plot A (20 beds × 1.2m²), Plot B (15 beds × 1.0m²), Plot C (25 beds × 1.5m²)
  - `yield_forecast.py`: `get_bed_areas_for_location()` returns `(bed_count, bed_area_sqm)`; `project_yields_per_sqm()` implements formula: `Total Production = Planting Density/m² × Bed Area m² × Beds/Plot × Plots × (1 − Loss Rate)`
  - `engine.py`: Per-m² path branches when `planting_density` + bed data exist; 2 new outputs: `production_per_sqm`, `revenue_per_sqm_usd`; returns `total_bed_area_sqm`, `calculation_path`
  - Backward compatible: existing ha-based path remains default when bed data absent
- **Module C: Revenue Multiplier — Cross-module integration** (Tiers 1–6, all 10 dimensions):
  - `crop_mix.py`: Fixed SQL bug (price_observation now scoped to location's crops via subquery); wired `projected_revenue_by_crop` and `projected_noi_by_crop` from `forecast_output` into impact calculation
  - `loss_reduction.py`: Added forecast integration (`projected_yield_tonnes`, `loss_adjusted_yield_tonnes`)
  - `buyer_channel.py`: Added forecast integration (`projected_revenue_usd`)
  - `value_added.py`: Added forecast integration (`projected_revenue_usd`)
  - `web3_replication.py`: Added forecast integration (`projected_revenue_usd`)
  - `bioinput.py`: Wired soil health trend into score; added forecast integration (`projected_yield_tonnes`)
  - `public_goods.py`: Wired treasury allocation query into score/impact; added forecast integration (`public_goods_allocation_usd`)
  - `ecological_verification.py`: Added config-driven component weights (4 weights)
  - `partner_sponsorship.py`: Wired capital partner query into score; added forecast integration (`projected_revenue_usd`)
  - `regional_clusters.py`: Wired infrastructure sharing query into score; added forecast integration (`projected_revenue_usd`)
  - `analyzer.py`: 10 hardcoded dimension weights now read from DB via `get_config()` at runtime
- **Module C: Configurable constants** (35 new → 48 total):
  - `config.py`: 35 new defaults for scoring formulas (all 10 dimensions) and analyzer weights
  - `015_revenue_multiplier_config.sql`: 35 new seed rows with `ON CONFLICT` upsert
- **Module D: Biodiversity credit value in forecast** — `estimate_biodiversity_value(conn, location_id)` in `ecology.py` queries `species_observation`, computes Shannon diversity index, returns species count × `$35/species` from config
- **Module D: Forecast outputs** — 5 new forecast outputs (16 total):
  - `biodiversity_credit_value_usd`: biodiversity credits priced from species observations
  - `retained_value_usd`: NOI × retention rate (historical or scenario override)
  - `retention_rate_pct`: historical reinvestment rate or scenario assumption
  - `production_per_sqm`: total production per square meter from bed-area formula
  - `revenue_per_sqm_usd`: total revenue per square meter from bed-area formula
- **Module D: Retained value projection** — `_get_retention_rate()` queries `value_flow_event` for historical reinvestment rate; `ScenarioAssumptions.retention_rate_pct` allows scenario override
- **Module D: Metric computation automation** — `--all-locations` flag on metrics CLI; `scripts/compute-metrics.sh` for post-seed metric population
- **Module D: Dynamic calculation version** — `CALCULATION_VERSION` now date-based (`vYYYY.MM`), auto-bumps monthly
- **Module D: Metric version tracking** — `compute_metric` writes `metadata['version']` from `metric_definition.version`
- **Module D: Location-scoped pricing** — `get_historical_avg_prices()` now accepts `location_id` to scope price observations to crops grown at that location (fixes cross-location contamination)
- **Auditor role** (`a1000000-0000-0000-0000-000000000009`): read-only access to ALL statuses (draft/submitted/rejected/verified/published), 28 collection permissions
- **Dashboard dataset seeds** (`017_dashboard_datasets.sql`): 5 example dataset definitions for BI integration
- **Module B schema** (`019_module_b_gaps.sql`): `water_access`, `capex_breakdown`, `attestation_plan` tables
- **FR gap fixes**: Comprehensive audit-driven improvements across 10 functional requirements:
  - FR1: `schema_version` columns on 9 master tables (location, farm, plot, partner, infrastructure_asset, staff, crop, expense_category, capital_source)
  - FR2: `processor_version` wired into `log_ingestion()`; `source_raw` written before normalization in weather ingestion; ingestion status CLI (`python3 -m services.ingestion.status`)
  - FR4: Farm-level operating margin aggregation SQL (`dashboards/metabase/sql/14_farm_operating_margin.sql`)
  - FR5: Environmental trends SQL for NDVI/soil carbon/biodiversity time-series (`dashboards/metabase/sql/13_environmental_trends.sql`)
  - FR6: Loss-adjusted yield in forecast engine; `dashboard_dataset` writes from forecast engine
  - FR7: Direct FK `treasury_event.capital_source_id`; `digital_lego_usage.user_id` column
  - FR9: `--verify` handler in report generator; public aggregate views (`v_public_farm_summary`, `v_public_metric_summary`, `v_public_attestation_summary`); `frozen`/`frozen_at`/`frozen_by` columns on `report_snapshot` with immutability trigger
  - FR10: 3 agent roles (Agent Read-Only, Agent Write, Agent Full) in Directus permissions; agent action logging utility (`services/agents/logging.py`); `high_risk`/`requires_human_approval` flags on `agent_task` and `agent_action_log`
- **Baseline Cost field** (`location.baseline_cost`): pre-intervention operating cost baseline on `location` table, matching existing `baseline_revenue`, `baseline_asset_value`, `baseline_cash_flow` pattern. Added across schema, seed data (metric definitions + pilot farm), Python SDK, JS SDK, OpenAPI spec (Location, LocationCreate, LocationUpdate), data dictionary, and PRD. Pilot farm baseline_cost = `12000.00`.
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
- **Metric computation engine** (`services/metrics/`): `metric_value` table, 7 calculators (value_flowed, wallet_retention, digital_lego_usage, attestation_coverage, soil_carbon_delta, biodiversity_delta, operating_margin_pct), CLI with `--compute`, `--list`, `--all` flags.
- **Revenue multiplier config** (`schemas/postgres/016_revenue_multiplier_config.sql`): DB-backed configurable constants replacing 13 hardcoded values across all 10 dimensions.
- **Environmental analytics**: 4 new functions — `ndvi_trends`, `water_resilience`, `crop_diversity`, `intervention_impact` — with CLI flags.
- **Cross-module integration**: Fortune500 ← forecast (ecological_score), Fortune500 ← revenue_multiplier (growth signal), revenue_multiplier ← forecast (projected NOI in crop_mix), forecast exclusion logic (is_excluded filtering), forecast per-cycle outputs (crop_cycle_id), carbon sequestration forecast (carbon_sequestration_tonnes + carbon_credit_value_usd).
- **dapp_session pilot data** (`schemas/seeds/016_pilot_dapp_sessions.sql`): 12 dapp session records.
- **ClickHouse Web3 views**: `mv_monthly_wallet_unique_active`, `mv_daily_dlego_protocol_usage`, `mv_dlego_value_by_location`.
- **SQL bug fixes**: Added `WHERE location_id` to capital_source queries in `web3_replication.py` and `partner_sponsorship.py`.
- **Milestone 5 Stage 4 — JS SDK NoiMethods parity**: Added `NoiSnapshot` interface, `NoiMethods` interface, and `buildNoiMethods()` builder to JS SDK (`types.ts`, `methods.ts`, `client.ts`, `index.ts`); achieves full parity with Python SDK's 13 method groups
- **Milestone 5 Stage 4 — JS SDK tests**: Created `sdk/javascript/src/__tests__/client.test.ts` — vitest suite testing all 14 method groups, domain-specific methods, and SDK instantiation (16 assertions)
- **Milestone 5 Stage 4 — Pagination + error handling examples**: Created `sdk/python/examples/pagination_and_errors.py` and `sdk/javascript/examples/pagination-and-errors.ts` — page-based and offset-based pagination patterns with try/except per error type (AuthenticationError, NotFoundError, PermissionError, ValidationError)
- **Milestone 5 Stage 4 — Partner dashboard JSON configs**: Created importable Directus dashboard templates for all 4 partner roles:
  - `dashboards/directus/partner-buyer.json` — 5 modules (production summary, upcoming harvests, sales history, quality grades, revenue trend)
  - `dashboards/directus/partner-funder.json` — 5 modules (financial overview, NOI by crop cycle, cost breakdown, forecast vs actual, impact attestations)
  - `dashboards/directus/partner-vendor.json` — 5 modules (purchase summary, purchase history, upcoming demand, category breakdown, payment status)
  - `dashboards/directus/partner-operator.json` — 6 modules (operations overview, crop cycle status, sensor dashboard, open alerts, financial summary, recent expenses)

### Changed
- `seed-pilot.sh` now applies `018_module_e_water_access.sql` before pilot files so ground analytics water quality and irrigation records can reference canonical water access rows.
- **Pilot identity**: Replaced the canonical Kisumu demo identity with Kokonut Adelphi in pilot master, registry, Web3, DAO, price, value-flow, partner, and water-access seeds.
- **Seed strictness**: Updated `seed.sh` and `seed-pilot.sh` to run PostgreSQL seeds with `ON_ERROR_STOP=1`, so SQL errors fail loudly instead of being hidden by `psql` defaults.
- **Celo and Gnosis source-of-truth seeds**: Celo EAS seeds now refresh registered schema UIDs, names, chain, resolver, schema text, and active state on conflict. Gnosis DAO seeds now upsert Kokonut Treasury protocol and DAO wallet metadata instead of leaving stale Optimism rows untouched.
- **Public aggregate views**: Public farm, metric, and attestation views now require a verified or published Farm Registry record before exposing a location; public attestation summaries are scoped to Celo.
- **Guild governance model**: Documented and seeded Colony as the Guild execution/reputation layer while preserving Gnosis Moloch as treasury governance.
- `seed-pilot.sh` now applies required non-`*_pilot_*` MVP support seeds (`017_dashboard_datasets.sql`, `021_metric_versions.sql`, `022_metric_governance.sql`) and no longer masks SQL errors with `|| true`.
- The MVP setup sequence is now `./scripts/seed.sh`, `./scripts/seed-pilot.sh`, `./scripts/compute-metrics.sh`, and `./scripts/verify-mvp.sh`; full local CI includes all four when Docker Compose database is running.
- **Retry decorator**: Now catches only transient exceptions (`ConnectionError`, `TimeoutError`, `OSError`, `psycopg2.OperationalError`), not all `Exception` subclasses. Adds configurable jitter.
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
- **Revenue multiplier dimensions**: All 45 hardcoded constants now read from DB via `get_config()` (scoring formulas + analyzer weights)
- **Fortune500 scoring**: Growth pillar now blends 50/50 historical YoY + forecast-projected revenue growth; Ecological pillar includes forecast ecological score + carbon sequestration + water access; Governance pillar includes attestation plan maturity + digital lego adoption
- **Forecast engine**: Revenue projection now uses location-scoped price observations (was global); public goods allocation reads from forecast output; capex uses structured breakdown from `capex_breakdown` table with `$200/ha` fallback
- **Docker security**: PostgreSQL and ClickHouse ports removed from host mappings; named networks isolate database and app tiers
- **SDK examples**: All hardcoded `password123` replaced with environment variable references
- **RPC indexer**: Now supports `gnosis` and `celo` chain choices
- **Report generator**: `--auto` flag for batch generation of all 5 report types

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
- Forecast engine now filters excluded value flows in cost projections.
- Fortune500 calculator now reads ecological_score from forecast_output.
- Fortune500 growth scoring now uses year-over-year revenue and yield deltas.
- **Module C SQL bug**: `crop_mix.py` price_observation query now scoped to location's crops via subquery (was fetching global prices)
- **Module C connection ordering**: `analyzer.py` now reads config-driven weights before closing DB connection
- **Module D price contamination**: `get_historical_avg_prices()` now accepts `location_id` to scope price observations to crops grown at that location
- **Farm-level margin JOIN bug**: `14_farm_operating_margin.sql` was joining on `location_id` directly (attributing all location NOI to every farm); now traverses `crop_cycle → plot → farm` for correct per-farm attribution

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
- **17 governed metric definitions** (PRD Section 16): crop_revenue, net_crop_revenue, direct_crop_cost, allocated_shared_cost, crop_noi, loss_rate_pct, operating_margin_pct, baseline_revenue, baseline_asset_value, baseline_cash_flow, baseline_cost, value_flowed, wallet_retention, digital_lego_usage, soil_carbon_delta, biodiversity_delta, attestation_coverage
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
- Governed metric definitions with formulas, source tables, inclusion/exclusion rules
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
