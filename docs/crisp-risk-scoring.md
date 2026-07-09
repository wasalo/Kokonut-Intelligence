# CRISP Risk Scoring

Internal farm risk intelligence engine adapted from Solid World's SW-CRISP framework (Carbon Risk Identification and Scoring Principles). Five risk dimensions scored per-location per-assessment-period with configurable weights and a composite AAA-D rating.

## Risk Dimensions

| Dimension | Default Weight | Data Sources | Description |
|-----------|---------------|--------------|-------------|
| Carbon Yield | 40% | tree_inventory, soil_carbon_measurement, harvest_event, remote_sensing, carbon_benchmark | Likelihood of meeting carbon/biomass yield targets via scenario modeling |
| Climate | 25% | weather_observation, emergency_incident, risk_mitigation_register | Probability of drought, flood, heat, fire, storm, water stress |
| Policy & Legal | 15% | organic_certification, adoption_barrier, land_stewardship, governance_inclusion | Certification, regulatory, carbon rights, land tenure, community alignment |
| Financial | 10% | financial_sustainability_plan, unit_economics, revenue_event, expense_event | Revenue diversity, cost structure, liquidity, market price exposure |
| Implementation | 10% | farm_onboarding, regenerative_practice_checklist, stakeholder_feedback, training_event | Track record, team strength, network, transparency |

## Rating Scale

| Rating | Score Range | Interpretation |
|--------|-------------|----------------|
| AAA | 91–100 | Prime — lowest risk |
| AA | 80–91 | Very low risk |
| A | 69–80 | Low risk |
| B | 44–69 | Neutral — moderate risk |
| C | 20–44 | High risk |
| D | 0–20 | Junk — highest risk |

## Scoring Formula

```
Composite = (CarbonYield × 0.40) + (Climate × 0.25) + (Policy × 0.15) + (Financial × 0.10) + (Implementation × 0.10)
```

Weights are configurable per-location via `crisp_location_weight` table. Default weights are defined in `services/crisp/config.py`.

## Database Tables

| Table | Purpose |
|-------|---------|
| `crisp_risk_dimension` | Dimension definitions with default weights and data sources |
| `crisp_location_weight` | Per-location weight overrides |
| `crisp_risk_assessment` | Master assessment record per location per period |
| `crisp_carbon_yield_risk` | Carbon yield scenario modeling detail |
| `crisp_climate_risk` | Climate hazard scoring detail |
| `crisp_policy_risk` | Policy & legal risk detail |
| `crisp_financial_risk` | Financial viability risk detail |
| `crisp_implementation_risk` | Implementation/developer risk detail |
| `v_crisp_composite_rating` | Public composite view (published only) |
| `v_crisp_latest_assessment` | Internal latest-assessment view |

## Commands

```bash
# Individual dimension scoring
python3 -m services.crisp --carbon-yield --location-id UUID
python3 -m services.crisp --climate --location-id UUID
python3 -m services.crisp --policy --location-id UUID
python3 -m services.crisp --financial --location-id UUID
python3 -m services.crisp --implementation --location-id UUID

# Composite rating
python3 -m services.crisp --composite --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31

# Compute and persist assessment
python3 -m services.crisp --rate --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31

# Show effective weights for a location
python3 -m services.crisp --weights --location-id UUID

# Climate with specific SSP scenario
python3 -m services.crisp --climate --location-id UUID --ssp SSP5

# Carbon yield with ex-ante estimate
python3 -m services.crisp --carbon-yield --location-id UUID --ex-ante 50.0
```

## Methodology

### Carbon Yield Risk (40%)

Adapted from SW-CRISP Annexure 1. Builds three scenarios:
- **Minimum** (conservative): 60% of base carbon, full mortality, no SOC
- **Realistic** (moderate): 85% of base, partial mortality, SOC included
- **Optimistic** (liberal): 100% of base, low mortality, SOC + growth bonus

Yield likelihood maps ex-ante estimate position among scenarios:
- ≤ minimum: extremely likely (likelihood = 1.0)
- between minimum and realistic: quite likely (0.75–1.0)
- between realistic and optimistic: neutral (0.25–0.75)
- > optimistic: extremely unlikely (0.0)

### Climate Catastrophe Risk (25%)

Adapted from SW-CRISP Annexure 2. Per-hazard scoring (0–3 each):
- Drought: dry day ratio, low rainfall, historical drought incidents
- Flood: high rainfall, historical flood incidents
- Heatwave: extreme temperature, historical heat events
- Fire: dry+hot combination, historical fire events
- Storm: high wind speed, historical storm events
- Water stress: arid conditions, water crisis incidents

Natural risk rating = sum of all hazard scores (0–15). Mitigation factor from active climate risk register entries (each mitigation reduces risk by 5%, min 0.5).

### Policy & Legal Risk (15%)

Adapted from SW-CRISP Annexure 3. Sub-factor scoring (0–1 strength):
- National policy: certification status (certified=1.0, none=0.0)
- Carbon rights: ownership model clarity
- Land tenure: dependency risk level
- Community alignment: representation coverage, marginalized voices, satisfaction
- Certification risk: regulatory barrier severity

### Financial Viability Risk (10%)

Adapted from SW-CRISP Section 4. Composite risk factor from:
- Revenue risk (35%): grant dependency, volatility, stream count
- Cost risk (25%): payback period, cost concentration
- Liquidity risk (25%): runway months
- Market price risk (15%): revenue coefficient of variation

### Implementation Risk (10%)

Adapted from SW-CRISP Annexure 4. Sub-factor scoring (0–1 strength):
- Track record: onboarding readiness, practice adoption
- Team strength: training completion, activity, community engagement
- Network strength: implementation partners, infrastructure readiness
- Community alignment: representation coverage
- Transparency: governance method, stakeholder feedback volume

## Adaptive Per-Location Weights

Weights can be overridden per-location via `crisp_location_weight`:

```sql
-- Example: increase climate weight for drought-prone location
INSERT INTO crisp_location_weight (location_id, dimension_id, weight, override_reason)
SELECT 'LOCATION_UUID', cd.id, 0.35, 'Drought-prone region requires higher climate risk weighting'
FROM crisp_risk_dimension cd WHERE cd.dimension_key = 'climate';
```

## Evidence Maturity

Each dimension tracks evidence maturity (1–6) based on available data:
- Level 1: No relevant data
- Level 3: Basic data present (e.g., tree inventory exists)
- Level 4: Multiple data sources
- Level 5–6: Comprehensive evidence with external validation

Confidence levels map from evidence maturity:
- High: levels 5–6
- Moderate: levels 3–4
- Low: level 2
- Insufficient evidence: level 1
