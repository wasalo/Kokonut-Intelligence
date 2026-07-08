# Ecological Modeling Hub

The Ecological Modeling module captures trophic interactions, energy flow, population dynamics, soil inputs, pest management, biocontrol, resource consumption, and ecological model outputs for syntropic farms — enabling simulation and optimization of nutrient cycling, pest dynamics, biomass yields, and resource efficiency.

## Purpose

Model and track the ecological relationships that make syntropic farms self-regulating systems: which species interact, how energy flows across trophic levels, how populations change over time, what ecological models predict, how organic inputs persist in soil, how pest pressure responds to biocontrol, and how efficiently resources are used per kilogram of yield.

**Audience:** Ecology guild members, farm designers, researchers, regenerative agriculture practitioners.

## Tables

### Core Ecological Tables (v1)

| Table | Purpose |
|-------|---------|
| `ecological_interaction` | Species-species relationships: mutualism, competition, predation, facilitation |
| `ecological_model_run` | Simulation model inputs and outputs: nutrient cycling, pest dynamics, yield prediction |
| `energy_flow_measurement` | Biomass transfer between trophic levels with conversion efficiency |
| `population_dynamics_record` | Species population tracking over time with density and growth rate |

### Soil and Pest Tables (v2)

| Table | Purpose |
|-------|---------|
| `soil_input_application` | Organic input tracking: biochar, leaf litter, compost application and decomposition |
| `pest_observation` | Monthly pest incidence tracking with severity, weather conditions, and outbreak probability |
| `biocontrol_release` | Deliberate predator/biocontrol introductions with effectiveness follow-up |
| `resource_consumption` | Actual metered resource use: energy (kWh), water (liters), labor (hours) |

### Economic and Social Tables (v2)

| Table | Purpose |
|-------|---------|
| `training_session` | Individual training participation with pre/post score improvement |
| `revenue_stream_contribution` | Revenue stream breakdown linked to profitability |

### Model Validation Tables (v2)

| Table | Purpose |
|-------|---------|
| `prediction_accuracy_record` | Predicted vs actual comparisons with MAE, RMSE, MAPE metrics |
| `feature_importance_record` | Sensitivity analysis: which input variables most strongly predict outcomes |

## Extensions to Existing Tables

| Table | New Column | Purpose |
|-------|-----------|---------|
| `species_observation` | `trophic_level` | Classify species as producer/primary_consumer/secondary_consumer/decomposer/omnivore |
| `species_observation` | `population_density_per_m2` | Population density for insects and soil organisms |
| `species_observation` | `conservation_status` | IUCN conservation status: critically_endangered through least_concern |
| `farm_zone` | `strata_layer` | Syntropic vertical layer: emergent/canopy/sub_canopy/shrub/herbaceous/ground_cover/root/decomposer |

## Trophic Levels

| Level | Definition | Farm Examples |
|-------|-----------|---------------|
| **Producer** | Photosynthetic organisms | Coconut palm, passion fruit, jack bean, cover crops |
| **Primary Consumer** | Herbivores and pollinators | Honey bees, free-range chickens, herbivorous insects |
| **Secondary Consumer** | Predators | House sparrows, ladybugs, lacewings, frogs |
| **Decomposer** | Decomposing organisms | Earthworms, fungi, bacteria, compost microbes |
| **Omnivore** | Feeds at multiple levels | Chickens (eats plants + insects) |

## Interaction Types

| Type | Definition | Farm Example |
|------|-----------|--------------|
| **Mutualism** | Both species benefit | Honey bee ↔ passion fruit (pollination ↔ nectar) |
| **Competition** | Species compete for resources | Two crop species competing for soil nitrogen |
| **Predation** | One species consumes another | House sparrow → honey bee |
| **Facilitation** | One species benefits, other unaffected | Inga edulis N-fixation → passion fruit soil enrichment |
| **Commensalism** | One benefits, other unaffected | Epiphytic moss on coconut trunk |
| **Parasitism** | One benefits, other harmed | Root-knot nematode → coconut roots |

## Soil Input Types

| Type | Description | Decomposition Timeline |
|------|-------------|----------------------|
| **Biochar** | Charred organic matter for soil amendment | 5-10 years to fully incorporate |
| **Leaf litter** | Natural leaf fall from canopy species | 3-6 months to partial decomposition |
| **Compost** | Aerobically decomposed organic matter | 1-3 months to full decomposition |
| **Vermicompost** | Worm-processed organic matter | 1-2 months to full decomposition |
| **Manure** | Animal waste for nutrient input | 2-4 months to decomposition |
| **Green manure** | Cover crops incorporated into soil | 1-2 months to decomposition |

## Pest Categories

| Category | Examples | Monitoring Method |
|----------|----------|-------------------|
| **Insect** | Fall armyworm, aphids, bean fly | Visual scouting, sticky traps |
| **Fungal** | Powdery mildew, root rot | Visual inspection, lab analysis |
| **Bacterial** | Bacterial wilt, leaf blight | Lab analysis |
| **Viral** | Bean common mosaic virus | Lab analysis |
| **Mite** | Spider mites | Hand lens inspection |

## Resource Types

| Type | Unit | Source | Linked to Yield |
|------|------|--------|-----------------|
| **Energy** | kWh | Meter reading or estimate | Yes (per crop cycle) |
| **Water** | liters | Meter reading or irrigation program | Yes (per crop cycle) |
| **Labor** | hours | Activity tracking | Yes (per crop cycle) |
| **Fuel** | liters | Purchase records | Yes (per activity) |

## Public Views

### Core Ecological Views

- `v_public_ecological_interaction_summary` — published interactions with location/zone context
- `v_public_energy_flow_summary` — published energy flow measurements
- `v_public_population_dynamics_summary` — published population records
- `v_public_ecological_model_summary` — published model run inputs/outputs
- `v_trophic_balance` — aggregated interaction counts by trophic transfer
- `v_energy_flow_efficiency` — aggregated biomass transfer and efficiency by trophic level

### Soil and Pest Views

- `v_public_pest_trends` — monthly pest incidence by plot with outbreak probability
- `v_public_biocontrol_effectiveness` — biocontrol release outcomes and pest reduction
- `v_public_resource_efficiency` — resource consumption per kg of yield
- `v_public_soil_input_retention` — organic input persistence over time

### Economic and Social Views

- `v_public_training_impact` — training participation and improvement scores
- `v_public_revenue_streams` — revenue by stream linked to profitability

### Model Validation Views

- `v_public_prediction_accuracy` — predicted vs actual comparisons with error metrics
- `v_public_feature_importance` — which input variables most strongly predict outcomes

## Governed Metrics

### Core Ecological Metrics

- `ecological_interaction_count` — number of documented interactions per location
- `trophic_balance_index` — ratio of mutualistic to competitive interactions
- `energy_flow_efficiency_pct` — average biomass conversion efficiency
- `population_stability_index` — coefficient of variation of species populations

### Soil and Pest Metrics

- `pest_outbreak_probability` — monthly pest probability per plot
- `biocontrol_effectiveness_pct` — predator release success rate
- `labor_efficiency_kg_per_hour` — harvest output per labor hour
- `resource_intensity_index` — composite energy+water per kg yield

### Economic and Social Metrics

- `training_improvement_pct` — average pre/post score improvement
- `revenue_per_acre_usd` — gross revenue per acre of cultivated area

### Model Validation Metrics

- `forecast_mae` — mean absolute error for predictions
- `forecast_accuracy_pct` — 100 minus MAPE for yield predictions

## Analytics API

```python
from services.analytics.ecological_modeling import (
    compute_trophic_balance,
    compute_energy_flow_efficiency,
    compute_population_stability,
    trophic_pyramid_summary,
)
from services.analytics.ecological_modeling_v2 import (
    compute_soil_input_retention,
    compute_pest_trends,
    compute_biocontrol_effectiveness,
    compute_resource_efficiency,
    compute_conservation_status_summary,
)
from services.analytics.resource_efficiency import (
    compute_labor_efficiency,
    compute_resource_consumption_by_crop,
)
from services.analytics.economic_performance import (
    compute_revenue_per_acre,
    compute_revenue_stream_contribution,
    compute_training_impact,
)
from services.analytics.model_validation import (
    compute_prediction_accuracy,
    compute_feature_importance,
    compute_backtest_summary,
)
```

## Commands

```bash
# Core ecological analytics
python3 -m services.analytics.ecological_modeling --trophic-balance --location-id UUID
python3 -m services.analytics.ecological_modeling --energy-flow --location-id UUID
python3 -m services.analytics.ecological_modeling --population-stability --location-id UUID

# V2 ecological analytics
python3 -m services.analytics.ecological_modeling_v2 --soil-inputs --location-id UUID
python3 -m services.analytics.ecological_modeling_v2 --pest-trends --location-id UUID
python3 -m services.analytics.ecological_modeling_v2 --biocontrol --location-id UUID
python3 -m services.analytics.ecological_modeling_v2 --resource-efficiency --location-id UUID

# Economic analytics
python3 -m services.analytics.economic_performance --revenue-per-acre --location-id UUID
python3 -m services.analytics.economic_performance --revenue-streams --location-id UUID
python3 -m services.analytics.economic_performance --training --location-id UUID

# Model validation
python3 -m services.analytics.model_validation --prediction-accuracy --location-id UUID
python3 -m services.analytics.model_validation --feature-importance --location-id UUID

# Agent synthesis
python3 -m services.agents.ecological_modeling_agent --location-id UUID

# Reports (49 total)
python3 -m services.export.report_generator --type ecological_modeling --location-id UUID
python3 -m services.export.report_generator --type trophic_pyramid --location-id UUID
python3 -m services.export.report_generator --type pest_management --location-id UUID
python3 -m services.export.report_generator --type resource_efficiency --location-id UUID
python3 -m services.export.report_generator --type training_impact --location-id UUID
python3 -m services.export.report_generator --type revenue_streams --location-id UUID
python3 -m services.export.report_generator --type model_validation --location-id UUID

# Tests
python3 -m tests.test_ecological_modeling
python3 -m tests.test_ecological_modeling_v2
```

## Design Decisions

- **Species by name, not FK**: Ecological models reference species by scientific name. This allows flexible species lists without a separate `species` table.
- **JSONB model I/O**: Ecological models vary widely (nutrient cycling, pest dynamics, carbon projection). JSONB allows flexible input/output without rigid schema.
- **Interaction strength 0-1 scale**: Normalized strength allows comparison across interaction types and species pairs.
- **Population dynamics separate from species_observation**: Population tracking requires temporal analysis with density, carrying capacity, and growth rate — beyond simple observation counts.
- **Energy flow as dedicated table**: Trophic-level biomass transfer is distinct from crop yields and enables pyramid analysis.
- **Soil input retention via residual_pct**: Organic input decomposition tracked through periodic residual measurements rather than continuous monitoring.
- **Pest outbreak probability as model output**: Outbreak probability is computed from severity, incidence, and weather conditions — not a simple threshold.
- **Resource consumption linked to crop cycles**: Energy, water, and labor linked to specific crop cycles for per-kg yield efficiency calculations.
- **Conservation status on species_observation**: IUCN status field enables endangered species tracking without a separate table.
- **Prediction accuracy as governed records**: Model validation stored as formal records with status workflow, enabling audit and governance.

## Disclaimer

Ecological modeling outputs are **advisory estimates**, not deterministic predictions. Interaction strength values are observational estimates requiring ground-truth verification. Population dynamics records depend on survey method accuracy and observer skill. Energy flow measurements use estimation methods; direct measurement is preferred. Pest outbreak probability is a model estimate based on historical incidence and weather. Biocontrol effectiveness depends on environmental conditions and timing. Resource consumption may include estimated values where metering is unavailable. Soil input retention rates vary with soil type and climate. Prediction accuracy metrics are computed from limited pilot data and do not guarantee future model performance. Agent synthesis is a draft and requires human review before publication.
