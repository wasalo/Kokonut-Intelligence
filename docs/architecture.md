# Architecture

## System Overview

The Kokonut Intelligence Platform is a governed, open-source data operating system for regenerative farm operations, financial performance, ecological outcomes, and Web3 verification.

## Core Principles

1. **The schema is the product** — Dashboards, spreadsheets, agents, and blockchain views are interfaces. The durable asset is the canonical schema, metric dictionary, verification logic, and API contract.

2. **Web3 is a proof layer, not source of truth** — Canonical operational and financial data lives in PostgreSQL. Blockchain provides proofs, coordination, and public verifiability.

3. **Humans and AI agents use the same governed objects** — Different interfaces over the same canonical objects, permissions, and audit trails.

4. **Private evidence stays off-chain by default** — Public surfaces store hashes, CIDs, attestation UIDs, chain labels, and transaction hashes. Raw private MRV payloads remain in controlled off-chain storage.

## Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                    INTERFACES                           │
│  Directus Studio │ Metabase │ API │ Agents             │
└────────┬────────┴─────┬─────┴──┬──┴────┬───────────────┘
         │              │        │       │
┌────────▼──────────────▼────────▼───────▼───────────────┐
│                    DIRECTUS                             │
│          REST API │ GraphQL │ SDK │ Flows              │
│          Permissions │ Automations │ Webhooks           │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│                 POSTGRESQL + POSTGIS                     │
│                                                         │
│  Master Data    Operational Facts    Financial Facts    │
│  ──────────     ────────────────     ──────────────    │
│  locations      farm_activity        financial_txn      │
│  farms          harvest_event        expense_event      │
│  plots          sales_event          crop_cost_alloc    │
│  crops          loss_event           noi_snapshot       │
│  crop_cycle     labor_event          cash_flow_snap     │
│  partners       field_note           value_flow_event   │
│  farm_registry  inventory_event      revenue_event      │
│                 maintenance_event                       │
│                                                         │
│  Environmental    Web3/Attestation    Modeled Outputs   │
│  ─────────────    ────────────────    ──────────────    │
│  soil_sample      wallet_profile      forecast_scenario  │
│  species_obs      attestation_record  forecast_output    │
│  remote_sensing   digital_lego_usage  metric_definition  │
│  weather_obs      attestation_schema  report_snapshot    │
│  sensor_reading   mrv_event           ai_summary         │
│  attestation_req  governance_event    agent_task         │
│  price_observation                    ingestion_log      │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│              PYTHON INGESTION LAYER                     │
│                                                         │
│  weather.py       → OpenWeatherMap API                  │
│  rpc_indexer.py   → Ethereum/L2 public RPC              │
│  market_data.py   → World Bank Pink Sheet               │
│  remote_sensing.py → CSV upload (NDVI/NDRE)            │
│  eas_indexer.py   → EAS GraphQL API (Celo/Optimism/Base)   │
│                                                         │
│  All scripts: services/ingestion/                       │
│  Common framework: base.py (DB, logging, retry)         │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│                   CLICKHOUSE                            │
│                                                         │
│  events_raw │ wallet_events │ sensor_readings           │
│  weather_events │ financial_events │ dlego_events       │
│                                                         │
│  Materialized Views:                                     │
│  daily_event_counts │ hourly_sensor_stats               │
│  daily_wallet_activity │ monthly_financial_summary      │
│  daily_weather_summary │ daily_sensor_summary           │
│  sensor_reading_rate                                    │
└─────────────────────────────────────────────────────────┘
```

## Data Lifecycle

Every important record follows four states:

```
Draft → Submitted → Verified → Published
 │        │           │          │
 │        │           │          └─ Available to dashboards, APIs, attestations
 │        │           └─ Reviewed, validated, linked to evidence
 │        └─ Mapped to Kokonut canonical schema and submitted for review
 └─ Record created; source payload preserved where available
```

## Schema Management

Schemas are version-controlled as SQL files in `schemas/postgres/`. Directus snapshots capture the API-layer state.

- `schemas/postgres/` — Source of truth for database schema
- `schemas/directus/` — Directus snapshot exports
- `schemas/clickhouse/` — Analytical event schemas

## API Layers

| Layer | Protocol | Auth | Use Case |
|-------|----------|------|----------|
| Directus REST | HTTP REST | Bearer token | CRUD, admin, integrations |
| Directus GraphQL | GraphQL | Bearer token | Complex queries, frontend |
| Directus SDK | JavaScript | Session | Application integration |
| ClickHouse HTTP | HTTP | Basic auth | Analytical queries |
| Directus MCP | MCP | Scoped token | AI agent access |
| Helper CLIs | Python modules | Local process auth | Registry validation, local CID prep, attestation request prep, agent manifest prep |

## Security Model

- **Roles:** Administrator, Field Worker, Supervisor, Manager, Finance, Analyst
- **Policies:** Per-collection, per-action, per-field permissions (84 rules across 5 policies)
- **Field-level:** Sensitive fields hidden per role
- **Row-level:** Filter rules restrict record visibility
- **Audit:** All mutations logged to `audit_log`
- **Evidence:** Raw evidence stored off-chain; hashes/CIDs on-chain
- **Agent scope:** This repository stores agent metadata and tasks only; marketplace identity, payment, escrow, and reputation logic are external to `Kokonut-Agentic-Marketplace`

## Data Ingestion

External data flows through Python scripts in `services/ingestion/`:

| Source | Script | Frequency | Target |
|--------|--------|-----------|--------|
| OpenWeatherMap | `weather.py` | On demand | `weather_observation` + ClickHouse |
| Ethereum/L2 RPC | `rpc_indexer.py` | On demand | `wallet_activity_event` + ClickHouse |
| World Bank | `market_data.py` | On demand | `price_observation` |
| CSV upload | `remote_sensing.py` | On demand | `remote_sensing_observation` |
| EAS API | `eas_indexer.py` | On demand | `attestation_record` |

DApp session ingestion and metrics are deferred. Current Web3 ingestion remains focused on wallet activity, protocol interactions, EAS attestations, and governed value-flow records.

All ingestion is logged to `ingestion_log` with source, status, and timing. Chain indexer health tracked in `chain_indexer_status`.

## EAS on Celo

Celo is the primary chain for Kokonut attestations. EAS v1.3.0 is deployed on Celo mainnet.

**Deployed Contracts:**

| Contract | Address |
|----------|---------|
| EAS | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` |
| SchemaRegistry | `0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34` |
| KokonutResolver | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` |

**Registered Schemas:**

| Schema | UID | Use Case |
|--------|-----|----------|
| `kokonut-mrv` | `0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54` | MRV claims |
| `kokonut-impact` | `0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe` | Environmental impact |
| `kokonut-financial` | `0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b` | Financial summaries |
| `kokonut-harvest` | `0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff` | Harvest verification |
| `kokonut-compliance` | `0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5` | Partner compliance |

**Attester wallets:** Deployer `0x3394C45b5938127EB56603A6051dF26CFAF08C26` + Kokonut multisig `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5`

**Resolver ownership:** Transferred to Kokonut multisig.

**Smart contracts:** `contracts/` (Foundry project) with `KokonutResolver.sol` gating attestation to allowed attesters. Build/test with `forge build` and `forge test`.

**Chain expansion:** New chains get testnet-first deployments. EAS chain config in `services/attestation/config.py` and `services/ingestion/config.py`. Add new chain config to expand.

## Configurable Container Architecture

The platform implements a Docker-inspired configurable container architecture for farms and projects. Each farm is a composable container that can be configured, instantiated from templates, and scaled.

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    STAKEHOLDERS LAYER                        │
│  Needs │ PoV │ Wants │ Goals │ WHW (What/How/Why)          │
│  needs_assessment │ stakeholder_aspiration │ objective      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                 KOKONUT FRAMEWORK LAYER                      │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  Farm Templates  │  │  Framework Specification        │  │
│  │  (Docker Image)  │  │  impact_framework               │  │
│  │  farm_template   │  │  regeneration_principle         │  │
│  │  default_zones   │  │  operations_protocol            │  │
│  │  default_gov     │  │  pillar_of_value                │  │
│  │  default_TE      │  │  form_of_capital                │  │
│  │  default_IF      │  │  impact_dimension               │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  Farm Compose    │  │  Implementation                 │  │
│  │  (docker-compose)│  │  farm_practice_event            │  │
│  │  farm_specification│ │  framework_phase               │  │
│  │  zones (JSONB)   │  │  regenerative_practice_checklist│  │
│  │  governance      │  │  ecological_interaction         │  │
│  │  token_economics │  │  energy_flow_measurement        │  │
│  │  impact_config   │  │  population_dynamics_record     │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│               OUTCOMES CONFIGURATION LAYER                   │
│                                                             │
│  Gov (Governance)    TE (Token Economics)                   │
│  community_governance_mechanism   commons_redistribution    │
│  anti_capture_governance_policy   algorithmic_redistribution│
│  farm_registry_record.governance  farm_registry_record.token│
│                                                             │
│  ID (Impact Dimensions)    IF (Impact Framework)            │
│  impact_dimension           impact_framework                │
│  form_of_capital            farm_impact_mapping             │
│  pillar_of_value            ebf_scorecard                   │
│  sdg                        regenerative_outcome_summary    │
└─────────────────────────────────────────────────────────────┘
```

### Key Tables

| Table | Docker Analog | Purpose |
|-------|--------------|---------|
| `farm_template` | Docker Image | Reusable configuration bundle with default zones, governance, token economics, impact frameworks |
| `farm_specification` | docker-compose.yml | Declarative per-farm configuration (zones, governance, TE, ID, IF as JSONB) |
| `farm_zone` | Container Component | Configurable zone types per farm (syntropic_plot, agroforestry, biofactory, poultry, etc.) |
| `needs_assessment` | N/A | Structured community needs with severity, urgency, mitigation tracking |
| `stakeholder_aspiration` | N/A | Formal wants/aspirations with priority, timeline, success criteria |
| `objective` | N/A | Hierarchical goals with auto-computed progress_pct |

### How to Design a New Project from Scratch

1. **Choose a template**: `farm_template` defines the "Docker image" — default zones, governance, token economics, impact frameworks
2. **Instantiate**: `farm_specification` is the "docker-compose.yml" — declarative JSONB config per farm
3. **Assess needs**: `needs_assessment` tracks what the community needs before/after launch
4. **Capture aspirations**: `stakeholder_aspiration` formalizes what stakeholders want
5. **Set objectives**: `objective` table tracks hierarchical goals with auto-computed progress

### Per-Farm Configurability

Each farm/container can independently configure:

| Component | Per-Farm Table | Global Reference |
|-----------|---------------|-----------------|
| Zones | `farm_zone.zone_type`, `farm_zone.strata_layer` | — |
| Governance | `farm_registry_record.governance_mechanism` | `impact_framework` |
| Token Economics | `farm_registry_record.token_allocation` | `revenue_multiplier_config` |
| Impact Dimensions | `farm_impact_mapping.dimension_key` | `impact_dimension` |
| Impact Frameworks | `farm_impact_mapping.framework_key` | `impact_framework` |
| Redistribution | `commons_redistribution_policy` | — |
| Anti-Capture | `anti_capture_governance_policy` | — |

## Grant Application & Network Diversity

The platform supports grant application tracking, returning applicant detection, and regional network diversity analysis.

### Key Tables

| Table | Purpose |
|-------|---------|
| `grant_application_history` | Tracks each grant application with cycle number, returning applicant flag, ecological metrics submitted, and on-chain/off-chain flow description |
| `regional_chapter` | Registry of regional chapters/networks with geographic region, country, chapter type |
| `network_membership` | Links farms to regional chapters with membership type and role |
| `farm_registry_record` (extended) | `returning_applicant`, `grant_count`, `total_grants_received` fields |

### Grant Application Template

A pre-configured `farm_template` called "Grant Application Template" is available for new farms applying to grants. It includes:
- Default zones (production, nursery, biofactory)
- Governance configuration
- Impact framework alignment
- Tags: `grant`, `application`, `template`, `regenerative`, `funder-ready`

### Network Diversity

The `v_network_diversity` view shows geographic and ecological diversity across the network:
- Farm count per chapter
- Countries represented
- Unique species observed
- Average regenerative score

### How Funders Use This

1. **Check land security**: `tenure_rights_assessment` + `property.deed_or_title_url`
2. **Verify pilot status**: `farm_registry_record.status` + `framework_phase` + `farm_practice_event`
3. **Review ecological metrics**: `objective` (target/current values) + `carbon_benchmark` + `soil_sample`
4. **Assess community engagement**: `training_session` + `partner` + `guild_contributor`
5. **Verify on-chain/off-chain flow**: `token_reward_distribution.linked_metric_key` + `reward_calibration_model`
6. **Check returning applicant**: `farm_registry_record.returning_applicant` + `grant_application_history`
7. **Review network diversity**: `v_network_diversity` + `v_public_regional_chapters`

## Organic Certification Readiness & Compliance

The platform supports organic certification tracking across USDA NOP, EU 2018/848, and IFOAM standards. The system covers the full lifecycle: transition planning, input compliance, buffer zone management, harvest segregation, inspection checklists, and readiness scoring.

### Certification Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORGANIC CERTIFICATION LIFECYCLE                │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Transition   │───▶│  Preparation │───▶│  Application │      │
│  │  Plan (2-3yr) │    │  & Readiness │    │  & Inspection│      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Prohibited   │    │  Buffer Zone │    │  Compliance  │      │
│  │  Substance    │    │  Management  │    │  Checklist   │      │
│  │  Tracking     │    │              │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Input Audit  │    │  Harvest     │    │  Readiness   │      │
│  │  Trail        │    │  Segregation │    │  Assessment  │      │
│  │               │    │              │    │  (0-100)     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              CERTIFICATION ACHIEVED                       │   │
│  │  organic_certification_record.status = 'certified'       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Tables

| Table | Purpose |
|-------|---------|
| `organic_certification_record` | Certification lifecycle per standard (USDA NOP, EU 2018/848, IFOAM) |
| `organic_transition_plan` | 2-3 year transition tracking with readiness scoring and milestone dates |
| `prohibited_substance_record` | Prohibited substance usage with withdrawal period tracking |
| `buffer_zone` | Physical separation zones with PostGIS geometry and adequacy assessment |
| `organic_input_audit` | Full input audit trail with organic/prohibited flags and supplier certification |
| `harvest_handling_record` | Post-harvest organic compliance with segregation and traceability |
| `organic_compliance_checklist` | Inspector audit trail with structured JSONB checklist per standard |
| `organic_readiness_assessment` | Composite 0-100 readiness scoring across 8 dimensions |

### Readiness Score Dimensions

| Dimension | Weight | Source |
|-----------|--------|--------|
| Transition Progress | 15% | `organic_transition_plan.current_year / total_years_required` |
| Soil Health | 15% | `soil_sample` pH, organic matter, NPK, CEC analysis |
| Input Compliance | 15% | `organic_input_audit` organic_certified / total inputs |
| Pest Management | 10% | `pest_observation` + `biocontrol_release` effectiveness |
| Biodiversity | 10% | `species_observation` species count per hectare |
| Buffer Zones | 10% | `buffer_zone` width >= 3m and condition = adequate |
| Record Completeness | 10% | Presence of required records across all organic tables |
| Training | 10% | `training_session` organic practice topics completed |
| Harvest Segregation | 5% | `harvest_handling_record` organic_segregated / total harvests |

### Standards Supported

| Standard | Transition Period | Buffer Width | Key Requirements |
|----------|------------------|--------------|------------------|
| USDA NOP | 36 months | Site-specific | National List allowed substances, NOP Fertilizer List |
| EU 2018/848 | 24 months | >= 3m | EU low-risk and basic substances list |
| IFOAM | 24+ months | Site-specific | IFOAM-approved natural biocontrols, recycled nutrient cycles |

### How Certifiers Use This

1. **Review transition timeline**: `organic_transition_plan` with current_year and milestones
2. **Verify input compliance**: `organic_input_audit` with organic_certified and is_prohibited flags
3. **Check buffer zones**: `buffer_zone` with width_m, condition_status, and PostGIS geometry
4. **Audit harvest handling**: `harvest_handling_record` with organic_segregated and lot tracking
5. **Review prohibited substances**: `prohibited_substance_record` with clearance status
6. **Assess readiness**: `organic_readiness_assessment` with composite score and sub-dimensions
7. **Inspect checklist**: `organic_compliance_checklist` with structured pass/fail items
8. **Verify on-chain**: `attestation_record` with `attestation_type = 'organic'`

## True Cost Accounting & Triple Bottom Line

The platform implements True Cost Accounting (TCA) and Triple Bottom Line (TBL) reporting across 5 phases:

### Phase 1: Hidden Cost Accounting
- `hidden_cost_observation` tracks externalities (pollution, health, social, environmental) with monetary estimates
- `compute_true_cost_statement()` combines market costs + hidden costs + capital values

### Phase 2: Natural & Social Capital Valuation
- `natural_capital_valuation` assigns monetary values to carbon, biodiversity, water, soil, pollination
- `social_impact_valuation` monetizes training, governance, cultural preservation, health, community
- `worker_safety_observation` tracks workplace incidents
- `living_wage_benchmark` enables wage comparison

### Phase 3: Life Cycle Assessment
- `lca_assessment` tracks cradle-to-grave environmental impacts per product
- `compute_product_carbon_footprint()` and `compute_water_footprint()` compute per-unit impacts

### Phase 4: GRI Reporting
- `gri_indicator` maps platform metrics to GRI standards
- `materiality_assessment` maps stakeholder priorities vs business importance

### Phase 5: Systems Thinking
- `capital_flow_observation` tracks transfers between natural, human, social, produced, and financial capitals
- `compute_system_resilience()` scores cross-capital resilience

### Key Analytics

| Function | What It Computes |
|----------|-----------------|
| `compute_true_cost_statement()` | Market profit - hidden costs + natural + social capital = true profit |
| `compute_hidden_cost_summary()` | Hidden costs by category and subcategory |
| `compute_natural_capital_valuation()` | Natural capital value by type |
| `compute_social_impact_valuation()` | Social impact value by category |
| `compute_human_capital_score()` | Unified 0-100 human capital score |
| `compute_product_carbon_footprint()` | Emissions per kg of product |
| `compute_water_footprint()` | Blue/green/grey water per crop |
| `compute_lca_summary()` | Full lifecycle impact by stage |
| `compute_gri_compliance_score()` | % of GRI indicators with data |
| `compute_materiality_matrix()` | Stakeholder importance vs business importance |
| `compute_capital_flow_summary()` | Transfers between capitals |
| `compute_cross_capital_dependencies()` | How investment in one capital affects others |
| `compute_system_resilience()` | Cross-capital resilience score |

See [Metrics by Development Phase](metrics-by-phase.md) for the complete phase-to-metric mapping.

## Impact Value Chain

The platform implements the Impact Value Chain framework with organizational structure and operational planning:

### Organizational Structure
- `department` — Organizational units (Operations, Ecology, Finance, Community, Governance)
- `job_role` — Role definitions with department linkage
- `staff` — Extended with `job_role_id`, `department_id`, `hire_date`, `employment_status`

### Operational Planning
- `farm_task` — Planned tasks with scheduling, priorities, and assignees
- `weekly_plan` — Weekly action planning with budget tracking
- `development_phase` — Farm lifecycle phases with sequencing
- `framework_step` — Sequenced methodology steps with prerequisites

### Key Analytics

| Function | What It Computes |
|----------|-----------------|
| `compute_task_completion_rate()` | Task completion rate, on-time delivery, cost adherence |
| `compute_weekly_plan_adherence()` | Budget actual vs forecast, task completion |
| `compute_development_phase_progress()` | Current phase, % complete, time elapsed |
| `compute_framework_step_progress()` | Steps completed, prerequisites met, blocked steps |

## Scenario Parameters

The platform supports worst/base/best case scenario modeling with Monte Carlo simulation:

### Parameters
- 18 default parameters across 6 categories: yield, price, cost, weather, ecological, governance
- Each parameter has worst/base/best values with distribution types (normal, uniform, triangular)

### Key Analytics

| Function | What It Computes |
|----------|-----------------|
| `run_monte_carlo()` | 1000-sample simulation with P10-P90 percentile bands |
| `run_sensitivity_analysis()` | Per-parameter sensitivity with elasticity |
| `run_sensitivity_tornado()` | Ranked impact across all parameters |
