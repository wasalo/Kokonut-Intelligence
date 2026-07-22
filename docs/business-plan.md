# Business Plan Program

Structured business-plan generation for Kokonut Intelligence, built from the
Enterprise Planning System (EPS), Value Stream Mapping (VSM), and strategy
capabilities already in the platform. It assembles a single coherent narrative
from market, management, financial, operational, strategic, and risk evidence
at two grains.

## Two grains

- **Organization grain** (`--org-id UUID`): rolls up every location in the
  organization — market overviews aggregated, S&OP cockpit, budget/variance,
  operational flow per location, and organization-wide strategy.
- **Location grain** (`--location-id UUID`): a single-farm plan — that
  location's market overview, financial snapshot + reference-class dampening,
  VSM current-state and bottlenecks, SWOT, and location-scoped strategy.

Exactly one of `--org-id` / `--location-id` is required.

## Sections assembled

| Section | Source | Notes |
|---------|--------|-------|
| Market analysis | `services.analytics.marketplace.get_market_overview` | per-location; aggregated for org |
| Management & governance | `services.planning.sandop.cockpit` | org-scoped |
| Financial plan | `services.planning.budget` + `noi_snapshot` + reference-class | variance + latest NOI |
| Operational flow | `services.analytics.value_stream` | current-state map + bottlenecks |
| SWOT | `services.analytics.swot` | existing row, else suggested from threatcasting/CRISP |
| Strategy kernel | `services.analytics.strategy_kernel` + execution + coherence + competitive | plans, dashboards, findings |
| Executive summary | generated | short narrative |

Each section is computed best-effort: if a backing table or service is
unavailable, that section degrades to an error note rather than breaking the
whole plan. The assembler is read-only — it never writes governed data.

## Database schema

### `swot_analysis`

Stores structured SWOT for an org or location (`schemas/postgres/181_swot_analysis.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `organization_id` | UUID | FK to `organization` (org grain) |
| `location_id` | UUID | FK to `location` (location grain) |
| `entity_type` | VARCHAR(50) | `organization` or `location` |
| `entity_id` | UUID | The org or location ID |
| `strengths` | TEXT[] | Strength items |
| `weaknesses` | TEXT[] | Weakness items |
| `opportunities` | TEXT[] | Opportunity items |
| `threats` | TEXT[] | Threat items |
| `generated_from` | TEXT[] | Data sources used for suggestions |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `created_by` | UUID | Who created the SWOT |
| `updated_by` | UUID | Who last updated |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

### `swot_factor`

Classified individual SWOT items (`schemas/postgres/201_swot_enhancements.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `swot_id` | UUID | FK to `swot_analysis` |
| `factor_type` | VARCHAR(20) | `strength`, `weakness`, `opportunity`, `threat` |
| `classification` | VARCHAR(10) | `internal` or `external` |
| `category` | VARCHAR(50) | One of 12 categories (see below) |
| `description` | TEXT | Factor description |
| `priority` | INTEGER | Priority rank (higher = more important) |
| `confidence` | NUMERIC(3,2) | Confidence score 0.0–1.0 |
| `source` | TEXT | Data source reference |
| `metadata` | JSONB | Additional metadata |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

**Internal categories**: `human_resources`, `physical_resources`, `financial`, `activities_processes`, `past_experiences`

**External categories**: `future_trends`, `economy`, `funding_sources`, `demographics`, `physical_environment`, `legislation`, `events`

### `tows_strategy`

TOWS matrix strategic options (`schemas/postgres/201_swot_enhancements.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `swot_id` | UUID | FK to `swot_analysis` |
| `strategy_type` | VARCHAR(2) | `SO`, `ST`, `WO`, `WT` |
| `strategy_label` | VARCHAR(50) | Human-readable label |
| `description` | TEXT | Strategy description |
| `factor_pairs` | JSONB | Cross-matched factor pairs |
| `action_items` | TEXT[] | Action items |
| `priority` | INTEGER | Priority rank |
| `status` | VARCHAR(50) | `draft`, `under_review`, `approved`, `implemented`, `rejected` |
| `approved_by` | UUID | Who approved |
| `approved_at` | TIMESTAMPTZ | Approval timestamp |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

**TOWS labels**:

| Type | Label | Strategy |
|------|-------|----------|
| SO | Maxi-Maxi | Aggressive — use strengths to capture opportunities |
| ST | Maxi-Mini | Diversification — use strengths to avoid threats |
| WO | Mini-Maxi | Turnaround — overcome weaknesses via opportunities |
| WT | Mini-Mini | Defensive — minimize weaknesses and avoid threats |

### `competitor_swot`

Competitive intelligence (`schemas/postgres/201_swot_enhancements.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `competitor_name` | VARCHAR(255) | Competitor name |
| `competitor_type` | VARCHAR(50) | Type of competitor |
| `strengths` | TEXT[] | Competitor strengths |
| `weaknesses` | TEXT[] | Competitor weaknesses |
| `market_position` | TEXT | Market position description |
| `competitive_threat_level` | VARCHAR(20) | `low`, `moderate`, `high`, `critical` |
| `last_assessed` | TIMESTAMPTZ | Last assessment date |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `swot_temporal`

Versioned SWOT snapshots over time (`schemas/postgres/201_swot_enhancements.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `swot_id` | UUID | FK to `swot_analysis` |
| `version` | INTEGER | Version number |
| `snapshot` | JSONB | Full SWOT state at this version |
| `strengths_diff` | JSONB | Changes to strengths |
| `weaknesses_diff` | JSONB | Changes to weaknesses |
| `opportunities_diff` | JSONB | Changes to opportunities |
| `threats_diff` | JSONB | Changes to threats |
| `change_summary` | TEXT | Description of what changed |
| `created_at` | TIMESTAMPTZ | Snapshot timestamp |

### `swot_action_link`

Links SWOT factors/strategies to actions (`schemas/postgres/201_swot_enhancements.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `swot_id` | UUID | FK to `swot_analysis` |
| `factor_id` | UUID | FK to `swot_factor` (nullable) |
| `strategy_id` | UUID | FK to `tows_strategy` (nullable) |
| `target_type` | VARCHAR(50) | `decision_policy`, `work_item`, `recommendation`, `manual` |
| `target_id` | UUID | ID of the target entity |
| `action_description` | TEXT | Action description |
| `status` | VARCHAR(50) | `proposed`, `accepted`, `in_progress`, `completed`, `rejected` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `business_model_canvas`

Osterwalder/Painer BMC with 9 JSONB block columns (`schemas/postgres/197_business_model_canvas.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `organization_id` | UUID | FK to `organization` |
| `entity_type` | VARCHAR(50) | `location` or `organization` |
| `entity_id` | UUID | The org or location ID |
| `key_partners` | JSONB | Partner list |
| `key_activities` | JSONB | Activity list |
| `key_resources` | JSONB | Resource list |
| `value_propositions` | JSONB | Value proposition list |
| `customer_relationships` | JSONB | Relationship types |
| `channels` | JSONB | Distribution channels |
| `customer_segments` | JSONB | Customer segments |
| `revenue_streams` | JSONB | Revenue stream list |
| `cost_structure` | JSONB | Cost structure object |
| `canvas_name` | VARCHAR(255) | Canvas name (default: "Primary Canvas") |
| `description` | TEXT | Canvas description |
| `fiscal_year` | INTEGER | Fiscal year |
| `tags` | TEXT[] | Classification tags |
| `health_score` | NUMERIC(5,2) | Composite 0–100 health score |
| `health_score_breakdown` | JSONB | Per-block score breakdown |
| `health_score_computed_at` | TIMESTAMPTZ | When health was computed |
| `version` | INTEGER | Version number |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `revenue_stream_definition`

Revenue stream models (`schemas/postgres/198_revenue_model.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `stream_name` | VARCHAR(255) | Stream name |
| `stream_type` | VARCHAR(50) | `one_time`, `recurring`, `subscription`, `licensing`, `brokerage`, `advertising`, `grant`, `carbon_credit`, `biodiversity_credit` |
| `product_service` | VARCHAR(255) | Associated product/service |
| `description` | TEXT | Description |
| `currency` | VARCHAR(10) | Currency (default: USD) |
| `estimated_annual_usd` | NUMERIC(12,2) | Estimated annual revenue |
| `is_active` | BOOLEAN | Whether stream is active |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `pricing_model`

Pricing tiers and models (`schemas/postgres/198_revenue_model.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `revenue_stream_id` | UUID | FK to `revenue_stream_definition` |
| `product_name` | VARCHAR(255) | Product name |
| `pricing_type` | VARCHAR(50) | `per_unit`, `per_kg`, `per_hectare`, `subscription_tier`, `volume_discount`, `dynamic`, `flat_rate` |
| `base_price` | NUMERIC(12,2) | Base price |
| `currency` | VARCHAR(10) | Currency |
| `unit` | VARCHAR(50) | Unit of measure |
| `volume_discount_pct` | NUMERIC(5,2) | Volume discount percentage |
| `is_active` | BOOLEAN | Whether model is active |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `cost_structure`

Fixed vs variable cost classification (`schemas/postgres/198_revenue_model.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `cost_category` | VARCHAR(100) | Cost category |
| `cost_subcategory` | VARCHAR(100) | Cost subcategory |
| `cost_type` | VARCHAR(20) | `fixed`, `variable`, `semi_variable` |
| `amount_usd` | NUMERIC(12,2) | Cost amount |
| `frequency` | VARCHAR(50) | `one_time`, `daily`, `weekly`, `monthly`, `quarterly`, `annually` |
| `is_active` | BOOLEAN | Whether cost is active |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `break_even_analysis`

Break-even calculations (`schemas/postgres/198_revenue_model.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `analysis_name` | VARCHAR(255) | Analysis name |
| `total_fixed_costs` | NUMERIC(12,2) | Fixed costs |
| `variable_cost_per_unit` | NUMERIC(12,2) | Variable cost per unit |
| `price_per_unit` | NUMERIC(12,2) | Price per unit |
| `break_even_units` | NUMERIC(12,2) | Break-even unit count |
| `break_even_revenue` | NUMERIC(12,2) | Break-even revenue |
| `contribution_margin` | NUMERIC(5,2) | Contribution margin percentage |
| `margin_of_safety_pct` | NUMERIC(5,2) | Margin of safety percentage |
| `operating_leverage` | NUMERIC(8,4) | Operating leverage |
| `sensitivity_data` | JSONB | Sensitivity analysis results |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `pitch_template`

Audience-segmented pitch configurations (`schemas/postgres/202_pitch_presentation.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `audience` | VARCHAR(50) | `funders`, `operators`, `developers`, `refi`, `impact`, `elevator` (UNIQUE) |
| `hook` | TEXT | Opening hook |
| `problem` | TEXT | Problem statement |
| `solution` | TEXT | Solution description |
| `proof_headline` | TEXT | Key proof point |
| `cta_label` | TEXT | Call-to-action label |
| `cta_url` | TEXT | Call-to-action URL |
| `sections` | JSONB | Additional sections |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

## SWOT framework

Structured Strengths / Weaknesses / Opportunities / Threats for an org or
location. The base `suggest()` function auto-generates suggestions from:

| Quadrant | Source | Logic |
|----------|--------|-------|
| Threats | `threat` table | Top 20 active threats by severity × probability |
| Opportunities | `threat_narrative` table | Desirable/baseline narratives, top 20 |
| Strengths | `crisp_risk_assessment` | Dimensions rated AAA, AA, or A |
| Weaknesses | `crisp_risk_assessment` | Dimensions rated C or D |

### Enhanced SWOT (TOWS, factors, competitors, temporal, actions)

The enhanced module (`services/analytics/swot_enhanced.py`, 670 lines) adds:

- **Factor classification**: Individual SWOT items with 12 categories, auto-classified as internal/external, with priority and confidence scoring
- **TOWS matrix generation**: Auto-generates SO/ST/WO/WT strategies by cross-matching factor pairs by category overlap + priority + confidence
- **Competitor SWOT**: Track competitor strengths, weaknesses, market position, and threat level
- **Temporal snapshots**: Versioned SWOT snapshots with diff tracking per quadrant
- **Action linkage**: Link SWOT factors/strategies to decisions, work items, or recommendations
- **Strategic fit scoring**: `overlap_score × balance_score × coverage_score` across all factors

### CLI

```bash
# Create a SWOT
python3 -m services.analytics.swot --location-id UUID create \
  --strengths "Strong soil" "Water access" \
  --weaknesses "Limited labor" \
  --opportunities "Organic premium" \
  --threats "Drought risk"

# List SWOTs
python3 -m services.analytics.swot --location-id UUID list

# Get a SWOT
python3 -m services.analytics.swot --location-id UUID get --swot-id UUID

# Auto-suggest from platform data
python3 -m services.analytics.swot --location-id UUID suggest

# Create a classified factor
python3 -m services.analytics.swot factor create \
  --swot-id UUID --factor-type strength --category physical_resources \
  --description "Deep borehole with solar pump" --priority 5 --confidence 0.9

# List factors with optional filters
python3 -m services.analytics.swot factor list --swot-id UUID \
  --factor-type strength --classification internal

# Generate TOWS matrix
python3 -m services.analytics.swot tows generate --swot-id UUID

# List TOWS strategies
python3 -m services.analytics.swot tows list --swot-id UUID

# Approve a TOWS strategy
python3 -m services.analytics.swot tows approve --strategy-id UUID --approved-by UUID

# Compute strategic fit score
python3 -m services.analytics.swot tows fit --swot-id UUID

# Create a competitor SWOT
python3 -m services.analytics.swot competitor create \
  --location-id UUID --name "BigAg Coop" --type cooperative \
  --strengths "Scale" --weaknesses "No organic" --threat-level high

# List competitors
python3 -m services.analytics.swot competitor list --location-id UUID

# Create a temporal snapshot
python3 -m services.analytics.swot temporal snapshot --swot-id UUID --summary "Added competitor"

# List temporal snapshots
python3 -m services.analytics.swot temporal list --swot-id UUID

# Link an action to a SWOT factor
python3 -m services.analytics.swot action link \
  --swot-id UUID --description "Secure borehole maintenance contract" \
  --factor-id UUID --target-type recommendation

# List action links
python3 -m services.analytics.swot action list --swot-id UUID
```

## Strategy Kernel

Versioned strategy plans with governance lifecycle, execution tracking,
coherence analysis, and competitive positioning.

### Strategy plans

Strategy plans follow a governed lifecycle: `draft → submitted → approved → active → superseded → retired`.

| Scope | Description |
|-------|-------------|
| `organization` | Organization-wide strategy |
| `location` | Location-specific strategy |

Plans support versioning (auto-incremented), supersession (one plan replaces another), parent/child cascading, and three approval modes: `governance_circle`, `stakeholder_decision`, or `dual`.

Key fields: `diagnosis_summary`, `guiding_policy`, `theory_of_change`, `uncertainty_summary`, `planning_horizon_start`, `planning_horizon_end`.

### Execution dashboard

Tracks strategy execution snapshots — a point-in-time capture of how well the active strategy is being executed.

### Coherence analysis

Checks for internal consistency across strategy plan entries — flags critical/high findings that block approval.

### Competitive position

A competitive landscape report comparing the organization's active strategy against market positioning.

### CLI

```bash
# List strategy plans
python3 -m services.analytics.strategy_kernel list

# Create a strategy plan
python3 -m services.analytics.strategy_kernel create \
  --scope-type location --scope-id UUID --name "2026 Regenerative Rollout" \
  --horizon-start 2026-01-01 --horizon-end 2026-12-31

# Submit for approval
python3 -m services.analytics.strategy_kernel submit --plan-id UUID

# Approve
python3 -m services.analytics.strategy_kernel approve --plan-id UUID --approved-by UUID

# Activate
python3 -m services.analytics.strategy_kernel activate --plan-id UUID

# Execution dashboard
python3 -m services.analytics.strategy_execution dashboard --scope-type location --scope-id UUID

# Run coherence checks
python3 -m services.analytics.strategy_coherence check --plan-id UUID

# Competitive report
python3 -m services.analytics.competitive_report report --plan-id UUID
```

## Business Model Canvas

The 9-building-block Osterwalder/Painer BMC, per location or organization,
with Value Proposition Canvas support (customer jobs, pain points, gain
creators) and 1-click auto-populate from platform data.

### The 9 blocks

`key_partners`, `key_activities`, `key_resources`, `value_propositions`,
`customer_relationships`, `channels`, `customer_segments`, `revenue_streams`,
`cost_structure`

### Health scoring

Composite 0–100 score across all 9 blocks with bonus modifiers. Computed on demand via `compute_health()`.

### 1-click auto-populate

`create_from_data()` derives all 9 blocks from existing platform data:

| Block | Data Sources |
|-------|-------------|
| Key Partners | `federation_node`, `cooperative`, `supplier_profile` |
| Key Activities | `process_map` |
| Key Resources | `sensor_device`, `energy_source`, `cooperative_asset` |
| Value Propositions | `impact_claim` |
| Channels | `content_delivery` |
| Customer Segments | `buyer_segment` |
| Revenue Streams | `revenue_event` |
| Cost Structure | `expense_event` |
| Customer Relationships | `stakeholder_feedback` |

### Version tracking

Each update creates a `canvas_version` snapshot with diff tracking.

### CLI

```bash
# Create an empty canvas
python3 -m services.analytics.business_model_canvas create --location-id UUID

# 1-click auto-populate from platform data
python3 -m services.analytics.business_model_canvas create-from-data --location-id UUID

# List canvases
python3 -m services.analytics.business_model_canvas list --location-id UUID

# Get a canvas
python3 -m services.analytics.business_model_canvas get --canvas-id UUID

# Update a specific block
python3 -m services.analytics.business_model_canvas update-block \
  --canvas-id UUID --block key_partners --items '[{"name":"Coop A"}]'

# Create a version snapshot
python3 -m services.analytics.business_model_canvas version --canvas-id UUID

# Compute health score
python3 -m services.analytics.business_model_canvas health --canvas-id UUID

# Read-only suggestion preview
python3 -m services.analytics.business_model_canvas suggest --location-id UUID
```

## Revenue Model

Revenue streams, pricing models, cost structures, break-even analysis,
sensitivity analysis, and revenue forecasting.

### Revenue streams

Nine stream types: `one_time`, `recurring`, `subscription`, `licensing`,
`brokerage`, `advertising`, `grant`, `carbon_credit`, `biodiversity_credit`.

### Pricing models

Seven pricing types: `per_unit`, `per_kg`, `per_hectare`, `subscription_tier`,
`volume_discount`, `dynamic`, `flat_rate`.

### Cost structures

Three cost types: `fixed`, `variable`, `semi_variable`. Six frequencies:
`one_time`, `daily`, `weekly`, `monthly`, `quarterly`, `annually`.

### Break-even analysis

Standard break-even with contribution margin, margin of safety, and operating
leverage. Sensitivity analysis across variable inputs.

### CLI

```bash
# Create a revenue stream
python3 -m services.analytics.revenue_model create-stream \
  --location-id UUID --stream-name "Maize Sales" --stream-type one_time

# List revenue streams
python3 -m services.analytics.revenue_model list-streams --location-id UUID

# Create a pricing model
python3 -m services.analytics.revenue_model create-pricing \
  --location-id UUID --product-name "Maize" --pricing-type per_kg --base-price 0.45

# Create a cost structure
python3 -m services.analytics.revenue_model create-cost \
  --location-id UUID --cost-category "Seeds" --cost-type variable --amount 800

# Compute break-even
python3 -m services.analytics.revenue_model break-even \
  --location-id UUID --fixed-costs 5000 --variable-cost 2 --price 5

# Sensitivity analysis
python3 -m services.analytics.revenue_model sensitivity --break-even-id UUID

# Revenue forecast
python3 -m services.analytics.revenue_model forecast --location-id UUID --periods 12
```

## Reference-class forecasting

A core business-plan safeguard against optimism bias. The subject location's
self-projection (from the forecast engine) is blended with the realized median
of comparable established locations:

```
damped = alpha * projected + (1 - alpha) * reference_median
```

`alpha` weights the subject's own (optimistic) projection. Lower alpha leans
more on the reference class (more conservative). Comparable locations are those
sharing the subject's organization with a `noi_snapshot`, excluding the subject.

### Return values

| Key | Description |
|-----|-------------|
| `metric` | The metric being dampened (default: `crop_noi`) |
| `alpha` | Weight on subject's projection |
| `projected` | Subject's own latest projection |
| `reference_median` | Median of comparable locations (`PERCENTILE_CONT(0.5)`) |
| `comparable_locations` | Count of comparable locations |
| `damped_estimate` | The blended result |
| `note` | Explanation of the result |

### CLI

```bash
python3 -m services.forecast.cli --reference-class --location-id UUID \
  [--rc-metric crop_noi] [--rc-alpha 0.5]
```

## Forecast Engine

The forecast engine (`services/forecast/engine.py`, 612 lines) produces
15+ output metrics per scenario with per-cycle breakdowns.

### Output metrics

| Metric | Description |
|--------|-------------|
| `projected_revenue_usd` | Total projected revenue |
| `projected_noi_usd` | Net operating income |
| `operating_margin_pct` | Operating margin percentage |
| `total_yield_tonnes` | Total projected yield |
| `loss_adjusted_yield_tonnes` | Yield after loss rate |
| `projected_cash_flow_usd` | Projected cash flow |
| `public_goods_allocation_usd` | Allocated to public goods |
| `ecological_score_forecast` | Ecological score projection |
| `risk_adjusted_noi_usd` | NOI adjusted for drought/risks |
| `carbon_sequestration_tonnes` | Projected carbon sequestration |
| `carbon_credit_value_usd` | Value of carbon credits |
| `biodiversity_credit_value_usd` | Value of biodiversity credits |
| `retained_value_usd` | Value retained on-farm |
| `retention_rate_pct` | Retention rate |
| `production_per_sqm` | Production per square meter |
| `revenue_per_sqm_usd` | Revenue per square meter |

Per-cycle outputs: `crop_noi_usd`, `crop_projected_revenue_usd`, `crop_survival_rate_pct`, `crop_margin_pct`.

### Data flow

Reads from: `forecast_scenario`, `crop_cycle`, `crop`, `noi_snapshot`, `value_flow_event`, `capex_breakdown`, `location`

Writes to: `forecast_output`, `prediction_ledger`, `dashboard_dataset`, `forecast_scenario` (status update)

### Configuration

- `CALCULATION_VERSION`: date-based (`vYYYY.MM`), auto-bumps monthly
- `CONFIDENCE_LEVEL`: 80% confidence intervals

### Default assumptions

| Category | Defaults |
|----------|----------|
| Prices | Maize $280/t, Cassava $180/t, Beans $650/t, Sweet Potato $220/t |
| Yields | Maize 2.8 t/ha, Cassava 7.5 t/ha, Beans 1.1 t/ha, Sweet Potato 5.5 t/ha |
| Costs | Fertilizer $120/ha, Seeds $80/ha, Labor $200/ha, Irrigation $60/ha |
| Growth | Area +10%, Yield +5%, Price +8% |
| Macro | Inflation 5%, Exchange rate 155 KES/USD, Discount rate 12% |

### CLI

```bash
# List forecast scenarios
python3 -m services.forecast.cli --list

# Show scenario details
python3 -m services.forecast.cli --details --scenario-id UUID

# Compare two scenarios
python3 -m services.forecast.cli --compare ID1 ID2

# Sensitivity analysis
python3 -m services.forecast.cli --sensitivity --scenario-id UUID --variable price

# Reference-class dampening
python3 -m services.forecast.cli --reference-class --location-id UUID
```

## Pitch & Presentation

Audience-segmented pitch generation pulling live data from 9 platform sources.

### Six audiences

| Audience | Focus |
|----------|-------|
| `funders` | ROI, financial projections, risk dampening |
| `operators` | Operational efficiency, yield, scalability |
| `developers` | Technical architecture, APIs, integration |
| `refi` | Regenerative finance, on-chain attestations, credits |
| `impact` | Environmental outcomes, social impact, GNH alignment |
| `elevator` | 60-second summary |

### Evidence sources

Live queries from: `v_public_farm_summary`, `v_crisp_composite_rating`, `v_public_revenue_streams`, `harvest_event`, `v_public_impact_claim_summary`, `v_public_attestation_summary`, `v_public_stakeholder_feedback_summary`, `v_public_carbon_credit_inventory`, `species_observation`.

### Output formats

CLI stdout, Markdown, HTML, PDF-ready.

### CLI

```bash
# Generate a pitch
python3 -m services.analytics.pitch generate --location-id UUID --audience funders

# Elevator pitch
python3 -m services.analytics.pitch elevator --location-id UUID

# Evidence summary
python3 -m services.analytics.pitch evidence --location-id UUID

# List templates
python3 -m services.analytics.pitch templates list

# Get a template
python3 -m services.analytics.pitch templates get --audience funders

# Create/update a template
python3 -m services.analytics.pitch templates create \
  --audience funders --hook "..." --problem "..." --solution "..." \
  --proof "..." --cta-label "Apply" --cta-url "https://..."

# Report type
python3 -m services.export.report_generator --type pitch_deck --location-id UUID
```

## Channel Orchestration

Multi-channel delivery configuration, per-segment preferences, fallback rules,
interaction tracking, and automated health scoring.

### Channel types

`sms`, `whatsapp`, `mobile_app`, `email`, `voice_call`

### Health scoring

Composite 0–100 score: engagement (30%) + satisfaction (30%) + recency (20%) + frequency (20%).

### CLI

```bash
# Configure a channel
python3 -m services.analytics.channel_orchestration create-channel \
  --location-id UUID --channel-name "SMS Alerts" --channel-type sms

# List channels
python3 -m services.analytics.channel_orchestration list-channels --location-id UUID

# Set preference
python3 -m services.analytics.channel_orchestration set-preference \
  --location-id UUID --segment-type farmer --channel-type sms --priority 10 --is-primary

# Delivery plan
python3 -m services.analytics.channel_orchestration delivery-plan \
  --location-id UUID --segment-type farmer

# Create fallback rule
python3 -m services.analytics.channel_orchestration create-fallback \
  --location-id UUID --rule-name "SMS fallback" --primary-channel sms \
  --fallback-channels whatsapp voice_call

# Log interaction
python3 -m services.analytics.channel_orchestration log-interaction \
  --location-id UUID --customer-type farmer --customer-id UUID \
  --interaction-type message_sent

# Health score
python3 -m services.analytics.channel_orchestration compute-health \
  --location-id UUID --customer-type farmer --customer-id UUID
```

## Partner Lifecycle

Formal partnership management with lifecycle stages, evaluations, and scorecards.

### Lifecycle stages

`prospect → negotiation → pilot → active → review → renewal → suspended → exited`

### Evaluation scoring

Weighted: technical (30%) + financial (25%) + reliability (25%) + compliance (20%).

### Scorecard scoring

Weighted: quality (30%) + deliveries on-time (25%) + responsiveness (20%) + cost (15%) + innovation (10%).

### CLI

```bash
# Create a lifecycle entry
python3 -m services.analytics.partner_lifecycle create --partner-id UUID --stage prospect

# Advance stage
python3 -m services.analytics.partner_lifecycle advance --lifecycle-id UUID --stage active

# List lifecycles
python3 -m services.analytics.partner_lifecycle list --location-id UUID

# Create evaluation
python3 -m services.analytics.partner_lifecycle evaluate \
  --lifecycle-id UUID --partner-id UUID --evaluation-type quarterly \
  --technical 80 --financial 70 --reliability 75 --compliance 85

# Create scorecard
python3 -m services.analytics.partner_lifecycle scorecard \
  --lifecycle-id UUID --partner-id UUID \
  --period-start 2026-01-01 --period-end 2026-03-31 \
  --quality 88 --deliveries-on-time 92 --responsibility 80 --cost 75 --innovation 70
```

## Running

```bash
# Generate a business plan (org grain)
python3 -m services.export.business_plan --org-id UUID

# Generate a business plan (location grain)
python3 -m services.export.business_plan --location-id UUID

# Via report generator
python3 -m services.export.report_generator --type business_plan --location-id UUID

# SWOT report
python3 -m services.export.report_generator --type swot --location-id UUID

# BMC report
python3 -m services.export.report_generator --type business_model_canvas --location-id UUID

# Pitch deck report
python3 -m services.export.report_generator --type pitch_deck --location-id UUID
```

## Testing

```bash
python3 -m pytest tests/test_business_plan.py tests/test_swot.py tests/test_reference_class.py -v
```

| Test File | Tests | What It Validates |
|-----------|-------|-------------------|
| `test_business_plan.py` | 3 | Module shape, location grain, org grain — asserts all section keys present |
| `test_swot.py` | 3 | Module shape, create + list roundtrip, suggest returns all 4 quadrants |
| `test_reference_class.py` | 2 | Module shape, reference-class formula correctness (damped = 0.5 × projected + 0.5 × median) |
