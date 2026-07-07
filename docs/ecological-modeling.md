# Ecological Modeling Hub

The Ecological Modeling module captures trophic interactions, energy flow, population dynamics, and ecological model outputs for syntropic farms — enabling simulation and optimization of nutrient cycling, pest dynamics, and biomass yields.

## Purpose

Model and track the ecological relationships that make syntropic farms self-regulating systems: which species interact, how energy flows across trophic levels, how populations change over time, and what ecological models predict.

**Audience:** Ecology guild members, farm designers, researchers, regenerative agriculture practitioners.

## Tables

| Table | Purpose |
|-------|---------|
| `ecological_interaction` | Species-species relationships: mutualism, competition, predation, facilitation |
| `ecological_model_run` | Simulation model inputs and outputs: nutrient cycling, pest dynamics, yield prediction |
| `energy_flow_measurement` | Biomass transfer between trophic levels with conversion efficiency |
| `population_dynamics_record` | Species population tracking over time with density and growth rate |

## Extensions to Existing Tables

| Table | New Column | Purpose |
|-------|-----------|---------|
| `species_observation` | `trophic_level` | Classify species as producer/primary_consumer/secondary_consumer/decomposer/omnivore |
| `species_observation` | `population_density_per_m2` | Population density for insects and soil organisms |
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

## Syntropic Strata Layers

| Layer | Description | Farm Examples |
|-------|-------------|---------------|
| **Emergent** | Tallest trees breaking canopy | Mature coconut palms |
| **Canopy** | Primary tree canopy | Coconut, mango, fruit trees |
| **Sub-canopy** | Small trees and large shrubs | Passion fruit vines, coffee |
| **Shrub** | Medium shrubs | Neem, moringa |
| **Herbaceous** | Non-woody ground layer | Legumes, vegetables, cover crops |
| **Ground cover** | Low-growing spreaders | Mucuna, jack bean |
| **Root** | Below-ground root zone | Root vegetables, tubers |
| **Decomposer** | Soil decomposer habitat | Compost beds, vermicompost zones |

## Ecological Model Types

| Model Type | Inputs | Outputs |
|-----------|--------|---------|
| **Nutrient cycling** | Soil NPK, litter rate, decomposition rate, rainfall | Projected soil N, biomass gain, intercrop ratios |
| **Pest dynamics** | Aphid rate, predator density, temperature | Outbreak probability, release thresholds |
| **Yield prediction** | Planting density, soil health, weather | Projected yield per crop |
| **Carbon projection** | Tree inventory, soil carbon, SOM change | Sequestration rate, credit value |
| **Population dynamics** | Species counts, carrying capacity, growth rate | Population projections |
| **Energy flow** | Biomass per trophic level, conversion rates | Energy transfer efficiency |
| **Water balance** | Rainfall, evapotranspiration, soil moisture | Irrigation needs, water stress |

## Public Views

- `v_public_ecological_interaction_summary` — published interactions with location/zone context
- `v_public_energy_flow_summary` — published energy flow measurements
- `v_public_population_dynamics_summary` — published population records
- `v_public_ecological_model_summary` — published model run inputs/outputs
- `v_trophic_balance` — aggregated interaction counts by trophic transfer
- `v_energy_flow_efficiency` — aggregated biomass transfer and efficiency by trophic level

## Governed Metrics

- `ecological_interaction_count` — number of documented interactions per location
- `trophic_balance_index` — ratio of mutualistic to competitive interactions
- `energy_flow_efficiency_pct` — average biomass conversion efficiency
- `population_stability_index` — coefficient of variation of species populations

## Commands

```bash
# Compute trophic balance
python3 -m services.analytics.ecological_modeling --trophic-balance --location-id UUID

# Compute energy flow efficiency
python3 -m services.analytics.ecological_modeling --energy-flow --location-id UUID

# Compute population stability
python3 -m services.analytics.ecological_modeling --population-stability --location-id UUID

# Run synthesis agent
python3 -m services.agents.ecological_modeling_agent --location-id UUID

# Generate reports
python3 -m services.export.report_generator --type ecological_modeling --location-id UUID
python3 -m services.export.report_generator --type trophic_pyramid --location-id UUID

# Run module tests
python3 -m tests.test_ecological_modeling
```

## Design Decisions

- **Species by name, not FK**: Ecological models reference species by scientific name. This allows flexible species lists without a separate `species` table.
- **JSONB model I/O**: Ecological models vary widely (nutrient cycling, pest dynamics, carbon projection). JSONB allows flexible input/output without rigid schema.
- **Interaction strength 0-1 scale**: Normalized strength allows comparison across interaction types and species pairs.
- **Population dynamics separate from species_observation**: Population tracking requires temporal analysis with density, carrying capacity, and growth rate — beyond simple observation counts.
- **Energy flow as dedicated table**: Trophic-level biomass transfer is distinct from crop yields and enables pyramid analysis.

## Disclaimer

Ecological modeling outputs are **advisory estimates**, not deterministic predictions. Interaction strength values are observational estimates requiring ground-truth verification. Population dynamics records depend on survey method accuracy and observer skill. Energy flow measurements use estimation methods; direct measurement is preferred. Agent synthesis is a draft and requires human review before publication.
