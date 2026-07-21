# CRISP Risk Scoring

Internal farm risk intelligence engine adapted from Solid World's SW-CRISP framework (Carbon Risk Identification and Scoring Principles). Five risk dimensions scored per-location per-assessment-period with configurable weights and a composite AAA–D rating. Higher scores indicate higher risk; AAA (0–<20) is the lowest risk band.

CRISP version is date-based (`v{YYYY.MM}`), auto-bumps monthly, stored in `services/crisp/config.py`.

## Architecture

```text
services/crisp/
├── config.py              Constants: version, weights, rating bands, confidence thresholds
├── models.py              DimensionScore, CompositeRating dataclasses
├── normalization.py       Five normalization helpers
├── scoring_engine.py      Orchestrator: weight query, rating, confidence, composite, persistence
├── cli.py                 CLI entry point (argparse, 8 flags)
├── __main__.py            python -m services.crisp shim
├── carbon_yield.py        Carbon yield risk dimension (286 lines)
├── climate_risk.py        Climate catastrophe risk dimension (365 lines)
├── policy_risk.py         Policy and legal risk dimension (295 lines)
├── financial_risk.py      Financial viability risk dimension (299 lines)
└── implementation_risk.py Implementation risk dimension (310 lines)
```

Total: 2,219 lines across 12 files. Each dimension module queries its own source tables and returns a `DimensionScore`. The scoring engine orchestrates weight resolution, composite calculation, rating assignment, and persistence.

## Risk Dimensions

| Dimension | Default Weight | Data Sources | Description |
|-----------|---------------|--------------|-------------|
| Carbon Yield | 40% | tree_inventory, soil_carbon_measurement, harvest_event, remote_sensing, carbon_benchmark | Likelihood of meeting carbon/biomass yield targets via scenario modeling |
| Climate | 25% | weather_observation, emergency_incident, risk_mitigation_register | Probability of drought, flood, heat, fire, storm, water stress |
| Policy & Legal | 15% | organic_certification, adoption_barrier, land_stewardship, governance_inclusion | Certification, regulatory, carbon rights, land tenure, community alignment |
| Financial | 10% | financial_sustainability_plan, unit_economics, revenue_event, expense_event | Revenue diversity, cost structure, liquidity, market price exposure |
| Implementation | 10% | farm_onboarding, regenerative_practice_checklist, stakeholder_feedback, training_event | Track record, team strength, network, transparency |

Default weights are defined in `services/crisp/config.py`:

```python
DEFAULT_WEIGHTS = {
    "carbon_yield": 0.40,
    "climate": 0.25,
    "policy": 0.15,
    "financial": 0.10,
    "implementation": 0.10,
}
```

## Rating Scale

| Rating | Score Range | Interpretation |
|--------|-------------|----------------|
| AAA | 0–<20 | Prime — lowest risk |
| AA | 20–<44 | Very low risk |
| A | 44–<69 | Low risk |
| B | 69–<80 | Neutral — moderate risk |
| C | 80–<91 | High risk |
| D | 91–100 | Junk — highest risk |

**Direction:** Lower composite score = healthier position. The situation assessor inverts CRISP scores (`100 - risk = health`) for the OODA Orient phase. Migration 166 (`optimism_bias_integrity.sql`) fixed a historical direction mismatch.

## Scoring Engine

`scoring_engine.py` orchestrates the full pipeline:

### 1. Weight Resolution

`_query_location_weights(conn, location_id)` reads `crisp_location_weight` rows for the location. If overrides exist, they replace defaults. Weights are normalized to sum to 1.0.

### 2. Dimension Scoring

Each dimension module queries its source tables and returns a `DimensionScore` with `risk_score` 0–100. The engine calls all five, or a subset if `dimensions=` is provided.

### 3. Composite Calculation

```
weighted_average_risk(scores, weights) = Σ(score_i × weight_i) / Σ(weight_i)
```

Normalized by active weight sum to handle missing dimensions.

### 4. Rating Assignment

`_assign_rating(composite_score)` maps via `RATING_BANDS`:

```python
RATING_BANDS = {        # [low, high) -- exclusive upper bound
    "AAA": (0, 20),
    "AA":  (20, 44),
    "A":   (44, 69),
    "B":   (69, 80),
    "C":   (80, 91),
    "D":   (91, 101),    # upper bound > 100 for safety
}
```

Falls back to "D" for out-of-range values.

### 5. Confidence Computation

`_compute_confidence(dimensions)` takes the **minimum** evidence maturity level across all scored dimensions and maps via `CONFIDENCE_THRESHOLDS`:

| Evidence Level | Confidence |
|---------------|------------|
| 6 | high |
| 5 | high |
| 4 | moderate |
| 3 | moderate |
| 2 | low |
| 1 | insufficient_evidence |

### 6. Design Note

Every `CompositeRating` includes a `design_note`:

> "The AAA-D band is a competence/merit signal, not an extrinsic bribe. Per persuasive-technology guidance (overjustification effect), gamified scores increase intrinsic motivation only when seen as reflecting verified competence — never as a coercive reward."

This note is computed but **not persisted** to the database — it appears in CLI JSON output only.

## Normalization Functions

`normalization.py` provides five helpers used across all dimensions:

| Function | Purpose |
|----------|---------|
| `clamp_risk_score(value)` | Clamp to [0, 100] range |
| `normalize_to_risk(value, minimum, maximum, invert=False)` | Map arbitrary range to 0–100 risk; `invert=True` flips direction |
| `likelihood_to_risk_score(likelihood)` | Convert 0–1 likelihood to risk: `risk = (1 - likelihood) × 100` |
| `hazard_score_to_risk(hazard_total, max_hazard=15.0)` | Map hazard sum (0–15) to 0–100 risk |
| `weighted_average_risk(scores, weights)` | Weighted average normalized by active weight sum |

## Models

`models.py` defines two dataclasses:

### DimensionScore

```python
@dataclass
class DimensionScore:
    dimension_key: str          # "carbon_yield", "climate", etc.
    dimension_name: str         # "Carbon Yield Risk"
    risk_score: float           # 0-100
    confidence_level: str       # "high", "moderate", "low", "insufficient_evidence"
    evidence_maturity_level: int # 1-6
    weight: float               # effective weight after normalization
    factors: dict               # sub-factor breakdown
    evidence_summary: str       # human-readable evidence notes
    uncertainty_notes: str      # caveats and data gaps
```

### CompositeRating

```python
@dataclass
class CompositeRating:
    location_id: str
    period_start: str           # ISO date
    period_end: str             # ISO date
    carbon_yield_score: DimensionScore
    climate_score: DimensionScore
    policy_score: DimensionScore
    financial_score: DimensionScore
    implementation_score: DimensionScore
    composite_score: float      # 0-100 weighted average
    rating: str                 # AAA, AA, A, B, C, D
    confidence_level: str
    methodology_version: str
    weights: dict               # effective weights used
    dimensions: dict            # all dimension scores
    design_note: str            # persuasive technology notice
```

## Carbon Yield Risk

Default weight: 40%. Adapted from SW-CRISP Annexure 1.

### Scenario Modeling

Builds three scenarios from tree inventory, soil carbon, harvest data, and benchmarks:

| Scenario | Multiplier | Mortality | SOC | Growth Bonus |
|----------|-----------|-----------|-----|-------------|
| Minimum (conservative) | 60% | Full | No | No |
| Realistic (moderate) | 85% | Partial | Yes | No |
| Optimistic (liberal) | 100% | Low | Yes | Yes |

### Yield Likelihood

Maps ex-ante estimate position among scenarios:

| Position | Likelihood | Risk |
|----------|-----------|------|
| ≤ minimum | 1.0 (extremely likely) | 0 |
| Between minimum and realistic | 0.75–1.0 (quite likely) | 0–25 |
| Between realistic and optimistic | 0.25–0.75 (neutral) | 25–75 |
| > optimistic | 0.0 (extremely unlikely) | 100 |

### Constants

```python
CARBON_FRACTION = 0.47       # Carbon fraction of dry biomass
CO2E_CONVERSION = 3.67       # CO2 to CO2e conversion
BELOW_GROUND_RATIO = 0.25   # Root:shoot ratio
SOC_DEFAULT_RATE = 0.5       # Default soil organic carbon rate
```

### Evidence Queries

- `_query_tree_summary` — species, count, diameter, height → total_co2e_tonnes
- `_query_soil_carbon` — depth, organic_matter_pct, carbon_pct → soil_co2e
- `_query_harvest_summary` — crop, quantity, area → harvest co2e
- `_query_ndvi_latest` — latest NDVI value
- `_query_carbon_benchmark` — species-specific benchmark co2e_per_ha

## Climate Catastrophe Risk

Default weight: 25%. Adapted from SW-CRISP Annexure 2.

### Per-Hazard Scoring (0–3 each)

| Hazard | Low (0) | Medium (1) | High (2) | Critical (3) |
|--------|---------|-----------|----------|-------------|
| Drought | Dry day ratio < threshold | Moderate | High | Extreme |
| Flood | Rainfall < threshold | Moderate | High | Extreme |
| Heatwave | Temp < threshold | Moderate | High | Extreme |
| Fire | Dry+hot combination low | Moderate | High | Extreme |
| Storm | Wind < threshold | Moderate | High | Extreme |
| Water stress | Arid conditions low | Moderate | High | Extreme |

Thresholds are defined in `HAZARD_THRESHOLDS` in `climate_risk.py`.

### Natural Risk Rating

`natural_risk_rating = Σ(hazard_scores)` — range 0–15.

### Mitigation Factor

Active entries in `risk_mitigation_register` reduce risk. Each mitigation reduces risk by 5%, with a minimum factor of 0.5:

```
mitigation_factor = max(1.0 - (mitigation_count × 0.05), 0.5)
climate_catastrophe_factor = natural_risk_rating × mitigation_factor / 15.0
```

### SSP Scenarios

`ssp_scenario` accepts `SSP1`, `SSP2`, or `SSP5`. Stored in the assessment and recorded in `uncertainty_notes` when not `SSP2`. **Note:** The SSP parameter does not currently modify scoring thresholds or calculations — the same weather data produces the same scores regardless of scenario. This is a known limitation.

## Policy & Legal Risk

Default weight: 15%. Adapted from SW-CRISP Annexure 3.

### Sub-Factor Scoring (0–1 strength each)

| Sub-Factor | Data Source | Scoring |
|-----------|------------|---------|
| National policy | organic_certification_record | certified = 1.0, none = 0.0 |
| Carbon rights | land_stewardship_commitment | Ownership model clarity |
| Land tenure | farm_onboarding_profile | Dependency risk level |
| Community alignment | governance_inclusion_observation + stakeholder_feedback | Representation coverage, marginalized voices, satisfaction |
| Certification risk | adoption_barrier_assessment | Regulatory barrier severity |

`article_6_score` exists in the schema but is **not written by the scoring engine** — the column remains NULL in all persisted assessments.

## Financial Viability Risk

Default weight: 10%. Adapted from SW-CRISP Section 4.

### Sub-Factor Weights

| Factor | Weight | Data Source |
|--------|--------|------------|
| Revenue risk | 35% | grant dependency, volatility, stream count |
| Cost risk | 25% | payback period, cost concentration |
| Liquidity risk | 25% | runway months |
| Market price risk | 15% | revenue coefficient of variation |

### Data Queries

- `_query_financial_sustainability` — runway_months, revenue_diversity, grant_dependency
- `_query_unit_economics` — break_even_year, payback_period
- `_query_revenue_summary` — total revenue, stream count, volatility
- `_query_expense_summary` — total expenses, concentration

`vintage_year` is accepted as a parameter but does not currently affect scoring.

## Implementation Risk

Default weight: 10%. Adapted from SW-CRISP Annexure 4.

### Sub-Factor Scoring (0–1 strength each)

| Sub-Factor | Data Source | Scoring |
|-----------|------------|---------|
| Track record | farm_onboarding_profile + regenerative_practice_checklist | Onboarding readiness, practice adoption |
| Team strength | training_event + farm_onboarding_profile | Training completion, activity, engagement |
| Network strength | farm_onboarding_profile | Implementation partners, infrastructure readiness |
| Community alignment | governance_inclusion_observation | Representation coverage |
| Transparency | governance_inclusion_observation + stakeholder_feedback | Governance method, feedback volume |

## Database Tables

Schema: `schemas/postgres/076_crisp_risk_scoring.sql` (295 lines). Seed: `schemas/seeds/076_crisp_risk_scoring.sql`.

### `crisp_risk_dimension`

Per-dimension configuration. Seeded with 5 rows.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `dimension_key` | VARCHAR(50) | NOT NULL, UNIQUE |
| `dimension_name` | VARCHAR(100) | NOT NULL |
| `description` | TEXT | |
| `default_weight` | NUMERIC(4,3) | NOT NULL, CHECK 0..1 |
| `data_sources` | TEXT[] | DEFAULT '{}' |
| `scoring_methodology` | TEXT | |
| `status` | VARCHAR(50) | DEFAULT 'active', CHECK IN ('active','inactive') |
| `metadata` | JSONB | DEFAULT '{}' |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### `crisp_location_weight`

Per-location weight overrides. Unique on `(location_id, dimension_id)`.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `location_id` | UUID | FK → location(id), CASCADE |
| `dimension_id` | UUID | FK → crisp_risk_dimension(id), CASCADE |
| `weight` | NUMERIC(4,3) | NOT NULL, CHECK 0..1 |
| `override_reason` | TEXT | |
| `status` | VARCHAR(50) | DEFAULT 'active' |
| `metadata` | JSONB | DEFAULT '{}' |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### `crisp_risk_assessment`

Master assessment record. Unique on `(location_id, period_start, period_end, methodology_version)`.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `location_id` | UUID | FK → location(id), RESTRICT |
| `farm_id` | UUID | FK → farm(id), SET NULL |
| `period_start` / `period_end` | DATE | NOT NULL |
| `methodology_version` | VARCHAR(50) | NOT NULL |
| `carbon_yield_score` | NUMERIC(5,2) | CHECK 0..100 |
| `climate_score` | NUMERIC(5,2) | CHECK 0..100 |
| `policy_score` | NUMERIC(5,2) | CHECK 0..100 |
| `financial_score` | NUMERIC(5,2) | CHECK 0..100 |
| `implementation_score` | NUMERIC(5,2) | CHECK 0..100 |
| `composite_score` | NUMERIC(5,2) | CHECK 0..100 |
| `rating` | VARCHAR(5) | CHECK IN ('AAA','AA','A','B','C','D') |
| `confidence_level` | VARCHAR(30) | CHECK IN ('high','moderate','low','insufficient_evidence') |
| `score_computed_at` | TIMESTAMPTZ | |
| `evidence_maturity_level` | INTEGER | FK → evidence_maturity_level(level) |
| `status` | VARCHAR(50) | DEFAULT 'draft', CHECK IN ('draft','submitted','verified','published','rejected') |
| `reviewer_notes` | TEXT | |
| `metadata` | JSONB | DEFAULT '{}' |
| `source_system` / `source_id` / `source_raw` | audit cols | |
| `created_by` / `updated_by` | UUID | |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### `crisp_carbon_yield_risk`

Carbon yield detail. FK → `crisp_risk_assessment(id)` CASCADE.

| Column | Type | Notes |
|--------|------|-------|
| `tree_inventory_snapshot` | JSONB | |
| `soil_carbon_snapshot` | JSONB | |
| `harvest_snapshot` | JSONB | |
| `allometric_source` | VARCHAR(255) | |
| `growth_model_reference` | VARCHAR(255) | |
| `planting_density_per_ha` | NUMERIC(10,2) | |
| `mortality_rate_pct` | NUMERIC(5,2) | |
| `ndvi_pre_project` | NUMERIC(5,3) | |
| `scenario_minimum` | NUMERIC(12,4) | |
| `scenario_realistic` | NUMERIC(12,4) | |
| `scenario_optimistic` | NUMERIC(12,4) | |
| `ex_ante_estimate` | NUMERIC(12,4) | |
| `yield_unit` | VARCHAR(50) | DEFAULT 'tonnes_co2e' |
| `yield_likelihood` | NUMERIC(5,4) | CHECK 0..1 |
| `risk_score` | NUMERIC(5,2) | CHECK 0..100 |
| `uncertainty_pct` | NUMERIC(5,2) | |
| `carbon_pool_breakdown` | JSONB | DEFAULT '{}' |
| `evidence_maturity_level` | INTEGER | FK |

### `crisp_climate_risk`

Climate detail. FK → `crisp_risk_assessment(id)` CASCADE.

| Column | Type | Constraints |
|--------|------|-------------|
| `drought_risk_score` | NUMERIC(4,2) | CHECK 0..3 |
| `flood_risk_score` | NUMERIC(4,2) | CHECK 0..3 |
| `heatwave_risk_score` | NUMERIC(4,2) | CHECK 0..3 |
| `fire_risk_score` | NUMERIC(4,2) | CHECK 0..3 |
| `storm_risk_score` | NUMERIC(4,2) | CHECK 0..3 |
| `water_stress_score` | NUMERIC(4,2) | CHECK 0..3 |
| `natural_risk_rating` | NUMERIC(5,2) | CHECK 0..15 |
| `mitigation_factor` | NUMERIC(4,2) | DEFAULT 1.0, CHECK 0..1 |
| `climate_catastrophe_factor` | NUMERIC(5,4) | CHECK 0..1 |
| `ssp_scenario` | VARCHAR(10) | DEFAULT 'SSP2', CHECK IN ('SSP1','SSP2','SSP5') |
| `risk_score` | NUMERIC(5,2) | CHECK 0..100 |
| `historical_events` | JSONB | DEFAULT '[]' |
| `climate_projections_source` | VARCHAR(255) | |
| `evidence_maturity_level` | INTEGER | FK |

### `crisp_policy_risk`

Policy detail. FK → `crisp_risk_assessment(id)` CASCADE.

| Column | Type | Constraints |
|--------|------|-------------|
| `national_policy_score` | NUMERIC(4,2) | CHECK 0..1 |
| `article_6_score` | NUMERIC(4,2) | CHECK 0..1 (not written by engine) |
| `carbon_rights_score` | NUMERIC(4,2) | CHECK 0..1 |
| `land_tenure_score` | NUMERIC(4,2) | CHECK 0..1 |
| `community_alignment_score` | NUMERIC(4,2) | CHECK 0..1 |
| `certification_risk_score` | NUMERIC(4,2) | CHECK 0..1 |
| `risk_score` | NUMERIC(5,2) | CHECK 0..100 |
| `policy_indicators` | JSONB | DEFAULT '{}' |
| `evidence_maturity_level` | INTEGER | FK |

### `crisp_financial_risk`

Financial detail. FK → `crisp_risk_assessment(id)` CASCADE.

| Column | Type | Constraints |
|--------|------|-------------|
| `break_even_year` | INTEGER | |
| `revenue_risk_factor` | NUMERIC(5,4) | CHECK 0..1 |
| `cost_risk_factor` | NUMERIC(5,4) | CHECK 0..1 |
| `market_price_risk` | NUMERIC(5,4) | CHECK 0..1 |
| `liquidity_risk` | NUMERIC(5,4) | CHECK 0..1 |
| `vintage_year` | INTEGER | |
| `financial_risk_factor` | NUMERIC(5,4) | CHECK 0..1 |
| `risk_score` | NUMERIC(5,2) | CHECK 0..100 |
| `financial_snapshot` | JSONB | DEFAULT '{}' |
| `evidence_maturity_level` | INTEGER | FK |

### `crisp_implementation_risk`

Implementation detail. FK → `crisp_risk_assessment(id)` CASCADE.

| Column | Type | Constraints |
|--------|------|-------------|
| `track_record_score` | NUMERIC(4,2) | CHECK 0..1 |
| `team_strength_score` | NUMERIC(4,2) | CHECK 0..1 |
| `network_strength_score` | NUMERIC(4,2) | CHECK 0..1 |
| `community_alignment_score` | NUMERIC(4,2) | CHECK 0..1 |
| `transparency_score` | NUMERIC(4,2) | CHECK 0..1 |
| `risk_score` | NUMERIC(5,2) | CHECK 0..100 |
| `implementation_evidence` | JSONB | DEFAULT '{}' |
| `evidence_maturity_level` | INTEGER | FK |

### Views

**`v_crisp_composite_rating`** — Public composite (published assessments only). Joins `crisp_risk_assessment` to `location` and `farm`. Resolves per-location weight overrides for all 5 dimensions. Exposes `carbon_yield_weight`, `climate_weight`, `policy_weight`, `financial_weight`, `implementation_weight`. Gated on published assessments only.

**`v_crisp_latest_assessment`** — Internal view (all statuses). `DISTINCT ON (location_id)` ordered by `period_end DESC, created_at DESC`.

## Adaptive Per-Location Weights

Weights can be overridden per-location via `crisp_location_weight`:

```sql
INSERT INTO crisp_location_weight (location_id, dimension_id, weight, override_reason)
SELECT 'LOCATION_UUID', cd.id, 0.35,
  'Drought-prone region requires higher climate risk weighting'
FROM crisp_risk_dimension cd WHERE cd.dimension_key = 'climate';
```

Overrides are resolved by `_query_location_weights()` and normalized to sum to 1.0. If a dimension has an override, it replaces the default; otherwise the default is used.

## CLI Reference

All flags are mutually exclusive (if-elif chain). Entry point: `python3 -m services.crisp`.

```bash
# Individual dimension scoring
python3 -m services.crisp --carbon-yield --location-id UUID [--ex-ante 50.0]
python3 -m services.crisp --climate --location-id UUID [--ssp SSP5]
python3 -m services.crisp --policy --location-id UUID
python3 -m services.crisp --financial --location-id UUID
python3 -m services.crisp --implementation --location-id UUID

# Composite rating (read-only, returns JSON)
python3 -m services.crisp --composite --location-id UUID \
  --period-start 2026-01-01 --period-end 2026-12-31 \
  [--ssp SSP5] [--methodology-version v2026.07]

# Compute and persist assessment (returns assessment_id)
python3 -m services.crisp --rate --location-id UUID \
  --period-start 2026-01-01 --period-end 2026-12-31 \
  [--ssp SSP5] [--methodology-version v2026.07]

# Show effective weights for a location
python3 -m services.crisp --weights --location-id UUID
```

## Integration Points

CRISP feeds into 20+ downstream services:

| Service | How CRISP is Used |
|---------|-------------------|
| **Orientation / Situation Assessor** | `_gather_crisp_signals()` reads latest assessment, inverts scores (`100 - risk = health`), emits `crisp_dimension` signals for OODA Orient phase. Stores `crisp_rating` and `crisp_composite_score` in `situation_assessment`. |
| **Report Generator** | `fetch_public_interest_context()` queries `v_crisp_composite_rating`, produces findings `CRISP_HIGH_RISK` (score ≥ 69) and `CRISP_INSUFFICIENT_EVIDENCE` (confidence low/insufficient). All reports inherit this context. |
| **LLM Chat** | Intent `get_crisp` → `_handle_crisp()` handler. **Known bug:** queries `crisp_dimension_score` view which does not exist. |
| **Digital Finance** | Insurance premium calculation uses `crisp_factor = max(1.0 - crisp_score/100.0, 0.0)`. Loan eligibility checks `crisp_risk_assessment`. |
| **Pitch** | `_query_crisp()` reads `v_crisp_composite_rating`; CRISP rating/score included in pitch deck evidence and elevator pitch. |
| **SWOT** | Reads `crisp_risk_assessment` to auto-generate threat factors from dimension scores. |
| **Environment Scanning** | Reads `crisp_risk_assessment` during auto-populate. |
| **Strategy Investment Case** | `strategy_investment_case.crisp_assessment_id` FK. View `v_strategy_investment_risk_evidence`. |
| **Backcasting Principles** | `backcast_principle.source_system='crisp'` and `crisp_dimension` column for principle alignment scoring. |
| **Objective KPIs** | `objective_kpi.crisp_dimension` column. |
| **Leverage Points** | Counts `crisp_risk_assessment` rows as data sources. |
| **Archetypes** | Reads `crisp_risk_assessment` to detect archetypes; uses `crisp_composite_score` as active variable. |
| **Double Loop** | Reads `crisp_risk_assessment` for paradigm shift detection; uses `crisp_declining_trend` signal. |
| **Feedback Loop** | `'crisp_weight'` as valid entity_type for feedback loop targets. |
| **Agent Safety** | `crisp_risk_assessment` is in `GOVERNED_COLLECTIONS` — agents cannot set status to 'verified' or 'published'. |
| **Cache Invalidation** | `handle_crisp_scored()` invalidates `crisp` computation cache on `crisp_scored` events. **Note:** `persist_assessment()` does not emit this event. |
| **Gateway REST** | `GET /crisp/{location_id}` endpoint. **Known bug:** imports `CRISPEngine` from `services.crisp` which does not exist. |

### Event Bus

The event bus schema registers handler `crisp_cache_invalidator` for `crisp_scored` events. However, `persist_assessment()` does **not** emit a `crisp_scored` event — cache invalidation would only trigger from external event producers.

## Evidence Maturity

Each dimension tracks evidence maturity (1–6) based on available data:

| Level | Description | Confidence |
|-------|-------------|------------|
| 6 | Comprehensive evidence with external validation | high |
| 5 | Comprehensive evidence | high |
| 4 | Multiple data sources | moderate |
| 3 | Basic data present (e.g., tree inventory exists) | moderate |
| 2 | Minimal data | low |
| 1 | No relevant data | insufficient_evidence |

The overall assessment confidence is the **minimum** evidence maturity across all scored dimensions.

### Per-Dimension Evidence Sources

- **Carbon Yield:** tree_inventory completeness, soil_carbon_measurement recency, harvest_event history, NDVI availability, benchmark match
- **Climate:** weather_observation history length, emergency_incident count, risk_mitigation_register entries
- **Policy:** organic_certification status, adoption_barrier assessments, land_stewardship records, governance_inclusion data
- **Financial:** financial_sustainability_plan completeness, unit_economics data, revenue_event history, expense_event coverage
- **Implementation:** farm_onboarding readiness score, regenerative_practice_checklist completion, stakeholder_feedback volume, training_event count

## Known Limitations & Gaps

| # | Gap | Severity | Status |
|---|-----|----------|--------|
| 1 | `CRISPEngine` class referenced by gateway router does not exist | High | Gateway `/crisp/{location_id}` endpoint would fail at runtime |
| 2 | `article_6_score` column in schema but never written by scoring engine | Low | Column remains NULL in all assessments |
| 3 | `crisp_dimension_score` view referenced in LLM chat handler does not exist | Medium | `get_crisp` intent would fail at runtime |
| 4 | No dedicated CRISP report type | Low | Data surfaces via `fetch_public_interest_context()` |
| 5 | No Metabase dashboard for CRISP visualization | Low | — |
| 6 | Dimension key mismatch between seeds (`crisp_operational`, etc.) and engine (`carbon_yield`, etc.) | Low | Different taxonomies for `impact_dimension` vs scoring engine |
| 7 | `vintage_year` parameter accepted but does not affect scoring | Low | — |
| 8 | `ex_ante_estimate` fallback mixes per-ha and total-area units | Medium | When tree inventory total is 0 and benchmark exists, per-ha benchmark is used without area multiplication |
| 9 | SSP scenario accepted but does not modify scoring thresholds | Low | Only recorded in `uncertainty_notes` when not SSP2 |
| 10 | No event emission after `persist_assessment()` | Medium | `crisp_scored` event bus handler is wired but never triggered from scoring engine |
| 11 | `design_note` computed but not persisted to database | Low | Appears in CLI output only |
| 12 | Direction confusion historically fixed by migration 166 | Info | Code is now consistent; migration exists as evidence of past mismatch |

## Cross-References

- [Agent Safety](agent-safety.md) — `crisp_risk_assessment` in governed collections
- [Orientation](ooda-loop.md) — CRISP signals in the O Orient phase
- [Metric Verification](metric-verification.md) — evidence maturity levels
- [Platform Integrity](platform-integrity.md) — schema constraints and migrations
- `schemas/postgres/076_crisp_risk_scoring.sql` — database schema
- `schemas/seeds/076_crisp_risk_scoring.sql` — seed data
- `schemas/postgres/166_optimism_bias_integrity.sql` — direction fix migration
- `tests/test_crisp_scoring.py` — 38 unit tests (542 lines)
