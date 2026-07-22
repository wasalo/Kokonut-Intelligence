# Ecological Modeling Hub

The ecological modeling modules describe trophic interactions, energy flow,
population dynamics, soil inputs, pest observations, biocontrol, resource use,
training, revenue streams, and model-validation records for syntropic farms.

The analytics implementation is primarily **read-only**. Functions calculate
results from a supplied database connection; they do not create governed metric
values, persist model runs, verify source records, or publish reports. Public
views expose only records that satisfy their lifecycle and farm-registry gates.
Model outputs are advisory estimates and require human interpretation.

## Module Inventory

| Module | Responsibility | Persistence |
|--------|----------------|-------------|
| `services/analytics/ecological_modeling.py` | Trophic balance, energy flow, population stability, pyramid | Read-only |
| `services/analytics/ecological_modeling_v2.py` | Soil retention, pest trends, biocontrol, resource efficiency, conservation status | Read-only |
| `services/analytics/resource_efficiency.py` | Labor efficiency and crop-level resource use | Read-only |
| `services/analytics/economic_performance.py` | Revenue per acre, revenue streams, training impact | Read-only |
| `services/analytics/model_validation.py` | Regression, error metrics, field aggregation, geographic folds | Read-only |
| `services/agents/ecological_modeling_agent.py` | In-memory synthesis across ecological outputs | Read-only |

None of these modules exposes an `argparse`/`typer` CLI entry point. The
analytics functions are called by reports, agents, tests, or application code.
The agent also has no CLI and is not a dedicated task in
`services/agents/tasks.py`.

## Schema Inventory

### Core Ecological Tables

Defined in `schemas/postgres/046_ecological_modeling.sql`:

| Table | Purpose | Important fields |
|-------|---------|------------------|
| `ecological_interaction` | Species relationship observation | species names, interaction type, strength, evidence, status |
| `ecological_model_run` | Model input/output record | model type, input parameters, output predictions, status |
| `energy_flow_measurement` | Biomass transfer between trophic levels | source/destination levels, biomass transferred, conversion efficiency |
| `population_dynamics_record` | Species population time series | species, population count, density, growth rate, carrying capacity |

Extensions from the same migration:

- `species_observation.trophic_level`
- `species_observation.population_density_per_m2`
- `farm_zone.strata_layer`

### Soil, Pest, And Resources

Defined in `schemas/postgres/047_ecological_modeling_v2.sql`:

| Table | Purpose | Important fields |
|-------|---------|------------------|
| `soil_input_application` | Organic input application and residual tracking | input type, quantity, residual percentage, decomposition status |
| `pest_observation` | Pest incidence and weather context | pest species, category, incidence, severity, outbreak probability, predators |
| `biocontrol_release` | Predator or biocontrol release | predator species, target pest, release count, effectiveness, pest reduction |
| `resource_consumption` | Metered or estimated resource use | resource type, quantity, unit, crop cycle, period, estimated flag |

Extensions include `species_observation.conservation_status`.
`resource_consumption` uses generic `quantity` and `unit`; it does not have
separate canonical `energy_kwh`, `water_liters`, and `labor_hours` columns.

### Economic, Social, And Validation Tables

| Table | Purpose | Important fields |
|-------|---------|------------------|
| `training_session` | Training participation and outcomes | participant name, pre/post scores, improvement, hours |
| `revenue_stream_contribution` | Revenue stream profitability | stream name, gross revenue, direct/allocated costs, net contribution |
| `prediction_accuracy_record` | Governed predicted-versus-actual record | predicted, actual, absolute error, MAE, RMSE, MAPE, R² |
| `feature_importance_record` | Model sensitivity record | feature, importance, direction, correlation, p-value, sample size |

These are defined in migrations 048 and 049.

### Later Extensions

Migration 050 adds:

- `pest_observation.predation_count`
- `pest_observation.predation_rate_per_day`
- `leaf_litter_measurement`
- `livestock_group`
- `feed_intake_record`
- `decomposition_measurement`
- `token_reward_distribution`
- `reward_calibration_model`

Migration 051 adds:

- `species_observation.status`
- `resource_consumption.irrigation_mm_used`
- `resource_consumption.rainfall_mm_during_period`
- `v_public_rainfall_vs_irrigation`
- `v_public_species_richness_per_ha`
- `v_public_location_species_richness`

Migration 052 adds:

- `v_public_weather_growth_correlation`
- `v_public_endangered_species_survival`

The later views and extensions are part of the current schema even though they
are not all consumed by the Python analytics modules.

## Trophic Levels

| Level | Definition | Examples |
|-------|-------------|----------|
| `producer` | Photosynthetic organism | Coconut, passion fruit, cover crops |
| `primary_consumer` | Herbivore or pollinator | Bees, chickens, herbivorous insects |
| `secondary_consumer` | Predator | Ladybugs, lacewings, frogs |
| `decomposer` | Decomposing organism | Earthworms, fungi, bacteria, compost microbes |
| `omnivore` | Feeds across levels | Chickens eating plants and insects |

`species_observation.trophic_level` and `farm_zone.strata_layer` support
syntropic vertical and trophic analysis. Species are represented by text names,
not a separate species foreign-key table.

## Interaction Types

The schema supports:

| Type | Meaning |
|------|---------|
| `mutualism` | Both species benefit |
| `competition` | Species compete for a resource |
| `predation` | One species consumes another |
| `facilitation` | One species benefits without materially affecting the other |
| `commensalism` | One benefits and the other is unaffected |
| `parasitism` | One benefits while harming the other |

`compute_trophic_balance()` reads verified or published interactions and
calculates:

```text
mutualism / max(mutualism + competition, 1)
```

It also returns average interaction strength by type and an average of those
type-level averages. The report generator uses a different mutualism-versus-
predation calculation, so report and analytics results should not be assumed to
be identical.

## Soil Inputs, Pests, And Biocontrol

### Soil Inputs

`compute_soil_input_retention()` groups verified or published applications by
input type/name and returns quantity-weighted residual percentage. Common domain
types include biochar, leaf litter, compost, vermicompost, manure, and green
manure, but the analytics function aggregates stored values rather than applying
a fixed decomposition timetable.

### Pest Trends

`compute_pest_trends()` groups verified or published observations by month,
species, common name, and category. It returns incidence, severity, weather,
predator, natural-enemy, and observation-count-weighted outbreak-probability
aggregates.

The system stores `outbreak_probability_pct`; the Python module aggregates that
field. It does not independently derive probability from severity, incidence,
and weather.

### Biocontrol

`compute_biocontrol_effectiveness()` groups verified or published releases by
predator and target pest. It returns average effectiveness and pest reduction.
Overall reduction is weighted by release-event count, not organism count.

## Resource And Economic Analytics

### Resource Efficiency

`compute_resource_efficiency()` separately returns:

- labor hours per kilogram harvested;
- energy kWh per kilogram;
- water liters per kilogram.

It does not calculate the seeded composite `resource_intensity_index`.
`compute_resource_consumption_by_crop()` groups resource use by resource type,
crop cycle, and crop. `compute_labor_efficiency()` joins completed/harvested
crop cycles to harvest and labor events and returns harvest kg per labor hour
plus an experience-curve efficiency measure.

The metric seed formula for resource intensity is recorded as:

```text
(sum(energy_kwh) + sum(water_liters) / 1000) / sum(harvest_kg)
```

The intended precedence should be confirmed before implementing it because the
stored formula can be read differently without explicit parentheses.

### Revenue Performance

`compute_revenue_per_acre()` converts hectares to acres using `2.47105` and
returns revenue per acre and ROI:

```text
revenue / area_acres
(revenue - expenses) / expenses * 100
```

Its SQL joins revenue and expense events in one query; multiple rows on both
sides can multiply amounts. Review this before using the result as an audited
financial figure.

`compute_revenue_stream_contribution()` returns gross revenue, direct costs,
allocated costs, net contribution, and the most profitable stream.

### Training Impact

`compute_training_impact()` aggregates verified or published training sessions,
including participant counts, hours, pre/post scores, and weighted improvement.
It aggregates the stored `improvement_pct`; it does not recompute improvement
from pre- and post-score values.

## Model Validation

The implemented functions in `model_validation.py` are:

```python
from services.analytics.model_validation import (
    compute_rmse,
    compute_mae,
    compute_me,
    compute_r_squared,
    compute_mec,
    compute_regression_metrics,
    geographic_cross_validation,
    aggregate_to_field_level,
)
```

`compute_regression_metrics()` returns R², RMSE, MAE, ME, MEC, intercept, slope,
and sample count. `geographic_cross_validation()` creates plot/field fold
partitions with an unseeded shuffle; it does not train or evaluate a model.
`aggregate_to_field_level()` aggregates predicted and measured SOC by plot.

These functions do not include the nonexistent imports
`compute_prediction_accuracy`, `compute_feature_importance`, or
`compute_backtest_summary`.

## Public Views And Gates

Most `v_public_*` ecological views require:

- an active location;
- source status `verified` or `published`;
- a related `farm_registry_record` with status `verified` or `published`.

Core views from migration 046:

- `v_public_ecological_interaction_summary`
- `v_public_energy_flow_summary`
- `v_public_population_dynamics_summary`
- `v_public_ecological_model_summary`
- `v_trophic_balance`
- `v_energy_flow_efficiency`

V2 views from migration 047:

- `v_public_pest_trends`
- `v_public_biocontrol_effectiveness`
- `v_public_resource_efficiency`
- `v_public_soil_input_retention`

Economic and validation views:

- `v_public_training_impact`
- `v_public_revenue_streams`
- `v_public_prediction_accuracy`
- `v_public_feature_importance`

The internal aggregate views `v_trophic_balance` and
`v_energy_flow_efficiency` apply source status filters but have weaker public
location and registry semantics. “Public” does not guarantee minimal disclosure:
the training view includes participant names, the model view includes input and
output JSON, and prediction views expose model details. Review privacy before
external publication.

## Governed Metrics

Seeded metric definitions include:

| Metric | Meaning | Implementation note |
|--------|---------|---------------------|
| `ecological_interaction_count` | Documented interactions | Seed evidence rule differs from analytics filter |
| `trophic_balance_index` | Mutualism/competition balance | Analytics uses mutualism and competition |
| `energy_flow_efficiency_pct` | Biomass conversion efficiency | Analytics uses biomass-weighted averaging |
| `population_stability_index` | Population stability | Analytics returns `1 - average(CV)`, clamped 0–1 |
| `pest_outbreak_probability` | Pest outbreak probability | Aggregates stored probability field |
| `biocontrol_effectiveness_pct` | Biocontrol success | Release-event-count weighted overall result |
| `labor_efficiency_kg_per_hour` | Harvest per labor hour | Calculated by resource-efficiency module |
| `resource_intensity_index` | Energy/water per harvest kg | Seeded but not calculated by `compute_resource_efficiency` |
| `training_improvement_pct` | Training improvement | Uses stored improvement percentages |
| `revenue_per_acre_usd` | Revenue per acre | Uses hectare-to-acre conversion |
| `forecast_mae` | Mean absolute forecast error | Validation record metric |
| `forecast_accuracy_pct` | Accuracy derived from MAPE | Validation metric definition |

Additional later definitions include `predation_rate_per_day` and
`rainfall_irrigation_delta_mm`.

Metric computation creates draft, unverified `metric_value` rows. It is not
verification and does not make the underlying public views eligible.

## Reports

There are seven ecological-domain report registrations:

```bash
python3 -m services.export.report_generator --type ecological_modeling --location-id UUID
python3 -m services.export.report_generator --type trophic_pyramid --location-id UUID
python3 -m services.export.report_generator --type pest_management --location-id UUID
python3 -m services.export.report_generator --type resource_efficiency --location-id UUID
python3 -m services.export.report_generator --type training_impact --location-id UUID
python3 -m services.export.report_generator --type revenue_streams --location-id UUID
python3 -m services.export.report_generator --type model_validation --location-id UUID
```

The global report registry contains many unrelated reports; the ecological
domain count is seven, not 49.

Report generators calculate report payloads in memory. A report snapshot is a
separate persistence operation. Period arguments are accepted by report
interfaces but several ecological SQL queries do not apply them consistently.
`generate_ecological_modeling` includes soil inputs but does not include every
v2 pest, biocontrol, and resource result.

## Agent Synthesis

`synthesize_ecological_modeling(conn, location_id)` calls the v1/v2 ecological
analytics functions plus livestock-feed and reward-calibration analytics. It
returns an in-memory dictionary containing trophic, energy, population, soil,
pest, biocontrol, resource, conservation, livestock, reward, safety, and
limitation sections.

The agent:

- does not expose a CLI;
- is not a dedicated task-catalogue entry;
- does not create an `ai_summary` row;
- does not persist a draft;
- does not verify or publish any source or output.

Its result is advisory and requires human review before use in a governed report
or public claim.

## Tests And Known Gaps

Relevant tests:

- `tests/test_ecological_modeling.py`
- `tests/test_ecological_modeling_v2.py`

Coverage includes schema/view presence, metric seeds, report registration,
public report shape, trophic balance, energy flow, population stability,
pyramid, soil retention, pest trends, biocontrol, resource efficiency,
conservation, economic/social structures, and regression metrics.

Known test/documentation gaps:

- Tests do not provide complete PostgreSQL integration coverage for public gates.
- Formula parity between seed definitions and runtime analytics is incomplete.
- Privacy minimization of public views is not comprehensively tested.
- Stale test calls reference nonexistent prediction-accuracy,
  feature-importance, and backtest analytics functions.
- The geographic cross-validation test does not actually invoke the geographic
  cross-validation function.
- There is no persistence workflow for analytics results or agent synthesis.

## Design Decisions And Limitations

- Species are stored by name rather than a species foreign key for flexible farm
  species lists.
- Model input/output uses JSONB because model structures vary.
- Interaction strength uses a normalized 0–1 scale.
- Population dynamics are separate from simple species observations because
  temporal population analysis requires density and growth fields.
- Energy flow is separate from crop yield so trophic transfer can be modeled.
- Soil retention uses periodic residual measurements rather than continuous
  decomposition monitoring.
- Resource consumption can be estimated; `is_estimated` must be considered.
- `crop_cycle_id` is nullable, so resource-to-crop-cycle linkage is optional.
- Prediction records have lifecycle fields and public views, but no dedicated
  persistence/calibration workflow is guaranteed by the analytics modules.

Ecological outputs are advisory estimates. Interaction strength depends on
observation quality; population dynamics depend on survey method; energy flow
may be estimated; pest probabilities aggregate stored model outputs; biocontrol
depends on timing and conditions; resource values may be estimated; soil
retention varies by soil and climate; and validation metrics from limited data do
not guarantee future performance.

## Source References

- `schemas/postgres/046_ecological_modeling.sql`
- `schemas/postgres/047_ecological_modeling_v2.sql`
- `schemas/postgres/048_economic_social_enhancement.sql`
- `schemas/postgres/049_model_validation.sql`
- `schemas/postgres/050_remaining_gaps.sql`
- `schemas/postgres/051_gap_closures.sql`
- `schemas/postgres/052_final_gaps.sql`
- `schemas/seeds/046_ecological_modeling.sql`
- `schemas/seeds/047_ecological_modeling_v2.sql`
- `schemas/seeds/048_economic_social_enhancement.sql`
- `schemas/seeds/049_model_validation.sql`
- `services/analytics/ecological_modeling.py`
- `services/analytics/ecological_modeling_v2.py`
- `services/analytics/resource_efficiency.py`
- `services/analytics/economic_performance.py`
- `services/analytics/model_validation.py`
- `services/agents/ecological_modeling_agent.py`
- `services/export/report_generator.py`
