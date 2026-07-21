# Bio Factory Operations Hub

The Bio Factory Operations Hub is the Kokonut Intelligence Platform's evidence-governed module for bio-organic fertilizer production, knowledge, and regional adaptation — with an initial focus on Latin America and the Caribbean.

## Purpose

Open-source the components, knowledge, and recipes produced across Kokonut Biofactories. Turn scattered research and production knowledge into a practical, reusable body of documentation that supports both field application and open-source knowledge sharing.

**Audience:** Bio-factory operators, smallholder networks, researchers, regenerative agriculture community, and contributors.

**What this module covers:**

- **Solid fertilizers**: compost, vermicompost, bokashi, biochar, bone meal, blood meal, feather meal, neem cake.
- **Liquid fertilizers**: compost tea, manure tea, fish emulsion, seaweed extract, sargassum extract.
- **Microbial biofertilizers**: Rhizobium, Azospirillum, Azolla, Pseudomonas, Trichoderma, Bacillus subtilis, lactic acid bacteria, mycorrhizal fungi.
- **Composition matrix**: typical N-P-K ranges, micronutrients, and production notes for 24 common ingredients (including 5 microbial inoculants).
- **Regional adaptation**: LAC-specific inputs (sargassum, coffee pulp, cocoa pod husks, banana residues, sesbania, Ascophyllum nodosum, coconut coir) with sourcing notes, seasonality, and cautions.

## Database schema

### `bio_factory_batch`

Production batch records (`schemas/postgres/043_bio_factory_operations.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `farm_id` | UUID | FK to `farm` |
| `batch_name` | VARCHAR(255) | Batch name |
| `batch_type` | VARCHAR(100) | `compost`, `vermicompost`, `bokashi`, `biochar`, `compost_tea`, `manure_tea`, `fish_emulsion`, `seaweed_extract`, `liquid_biofertilizer`, `microbial_biofertilizer`, `bone_meal`, `blood_meal`, `feather_meal`, `neem_cake`, `other` |
| `production_method` | VARCHAR(100) | `aerobic`, `anaerobic`, `vermicomposting`, `fermentation`, `extraction`, `inoculation`, `grinding`, `steeping`, `aerated_brewing`, `other` |
| `production_start_date` | DATE | Start date |
| `production_end_date` | DATE | End date |
| `input_kg_total` | NUMERIC(12,2) | Total input weight |
| `output_kg_total` | NUMERIC(12,2) | Total output weight |
| `output_liters_total` | NUMERIC(12,2) | Total output volume (liquid) |
| `batch_yield_pct` | NUMERIC(10,4) | Yield percentage |
| `moisture_pct` | NUMERIC(5,2) | Moisture (0–100) |
| `temperature_c` | NUMERIC(5,2) | Temperature in °C |
| `ph_level` | NUMERIC(4,2) | pH (0–14) |
| `microbial_strain` | VARCHAR(100) | `rhizobium`, `azospirillum`, `azolla`, `pseudomonas`, `trichoderma`, `bacillus_subtilis`, `lactic_acid_bacteria`, `mycorrhizal_fungi`, `mixed_culture`, `other` |
| `batch_summary` | TEXT | Internal summary |
| `public_summary` | TEXT | Public-safe summary |
| `limitations` | TEXT[] | Known limitations |
| `evidence_maturity` | INTEGER | FK to `evidence_maturity_level` (1–6) |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `metadata` | JSONB | Additional metadata |
| `source_system` | VARCHAR(100) | Source system |
| `source_id` | VARCHAR(255) | Source record ID |
| `source_raw` | JSONB | Raw source data |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |
| `created_by` | UUID | Creator |
| `updated_by` | UUID | Last updater |

### `bio_input_provenance`

Ingredient sourcing records (`schemas/postgres/043_bio_factory_operations.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `farm_id` | UUID | FK to `farm` |
| `batch_id` | UUID | FK to `bio_factory_batch` |
| `input_name` | VARCHAR(255) | Ingredient name |
| `input_category` | VARCHAR(100) | `plant_residue`, `animal_manure`, `agricultural_byproduct`, `marine_material`, `microbial_inoculum`, `mineral_amendment`, `water`, `fish_waste`, `other` |
| `supplier_name` | VARCHAR(255) | Supplier name |
| `supplier_verified` | BOOLEAN | Supplier verified |
| `organic_certified` | BOOLEAN | Organic certified |
| `origin_country` | VARCHAR(100) | Country of origin |
| `origin_region` | VARCHAR(255) | Region of origin |
| `input_kg` | NUMERIC(12,2) | Input weight |
| `moisture_pct` | NUMERIC(5,2) | Moisture (0–100) |
| `nutrient_n_pct` | NUMERIC(5,2) | Nitrogen % (0–100) |
| `nutrient_p_pct` | NUMERIC(5,2) | Phosphorus % (0–100) |
| `nutrient_k_pct` | NUMERIC(5,2) | Potassium % (0–100) |
| `quality_warnings` | TEXT[] | Safety/quality warnings |
| `input_summary` | TEXT | Internal summary |
| `public_summary` | TEXT | Public-safe summary |
| `evidence_maturity` | INTEGER | FK to `evidence_maturity_level` |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `metadata` | JSONB | Additional metadata |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `bio_recipe_library`

Recipe knowledge base (`schemas/postgres/043_bio_factory_operations.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `recipe_name` | VARCHAR(255) | Recipe name |
| `recipe_type` | VARCHAR(100) | `solid_fertilizer`, `liquid_fertilizer`, `microbial_biofertilizer`, `soil_amendment`, `foliar_spray`, `seed_treatment`, `other` |
| `recipe_category` | VARCHAR(100) | Category |
| `description` | TEXT | Recipe description |
| `ingredients` | JSONB | Ingredients array (see JSONB schemas below) |
| `ratios` | JSONB | Ratios object (C:N, moisture, dilution) |
| `process_steps` | JSONB | Step-by-step process (see JSONB schemas below) |
| `fermentation_days` | INTEGER | Fermentation duration |
| `target_c_n_ratio` | NUMERIC(6,2) | Target C:N ratio |
| `target_moisture_pct` | NUMERIC(5,2) | Target moisture % |
| `target_temperature_c` | NUMERIC(5,2) | Target temperature °C |
| `target_ph` | NUMERIC(4,2) | Target pH |
| `dilution_ratio` | VARCHAR(50) | Dilution ratio |
| `application_method` | VARCHAR(255) | Application method |
| `quality_warnings` | TEXT[] | Safety/quality warnings |
| `source_reference` | TEXT | Source reference |
| `recipe_summary` | TEXT | Internal summary |
| `public_summary` | TEXT | Public-safe summary |
| `limitations` | TEXT[] | Known limitations |
| `evidence_maturity` | INTEGER | FK to `evidence_maturity_level` |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `metadata` | JSONB | Additional metadata |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `bio_factory_distribution`

Distribution tracking (`schemas/postgres/043_bio_factory_operations.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `farm_id` | UUID | FK to `farm` |
| `batch_id` | UUID | FK to `bio_factory_batch` |
| `recipient_type` | VARCHAR(100) | `farm_internal`, `smallholder_network`, `cooperative`, `public_agency`, `research`, `commercial`, `community_seedbank`, `other` |
| `recipient_name` | VARCHAR(255) | Recipient name |
| `recipient_region` | VARCHAR(255) | Recipient region |
| `distribution_date` | DATE | Distribution date |
| `quantity_kg` | NUMERIC(12,2) | Quantity in kg |
| `quantity_liters` | NUMERIC(12,2) | Quantity in liters |
| `unit` | VARCHAR(50) | Unit of measure |
| `application_purpose` | VARCHAR(255) | Application purpose |
| `distribution_summary` | TEXT | Internal summary |
| `public_summary` | TEXT | Public-safe summary |
| `evidence_maturity` | INTEGER | FK to `evidence_maturity_level` |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `bio_factory_quality_test`

Quality test results (`schemas/postgres/043_bio_factory_operations.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `location_id` | UUID | FK to `location` |
| `farm_id` | UUID | FK to `farm` |
| `batch_id` | UUID | FK to `bio_factory_batch` |
| `test_date` | DATE | Test date |
| `test_type` | VARCHAR(100) | `nutrient_analysis`, `ph_test`, `microbial_count`, `moisture_test`, `contamination_screen`, `germination_test`, `heavy_metal_screen`, `salinity_test`, `other` |
| `parameter_name` | VARCHAR(255) | Parameter tested |
| `measured_value` | NUMERIC(12,4) | Measured value |
| `unit` | VARCHAR(50) | Unit |
| `target_min` | NUMERIC(12,4) | Minimum target |
| `target_max` | NUMERIC(12,4) | Maximum target |
| `pass_fail` | VARCHAR(20) | `pass`, `fail`, `marginal`, `pending` |
| `lab_name` | VARCHAR(255) | Laboratory name |
| `lab_accredited` | BOOLEAN | Lab accredited |
| `test_summary` | TEXT | Internal summary |
| `public_summary` | TEXT | Public-safe summary |
| `evidence_maturity` | INTEGER | FK to `evidence_maturity_level` |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

### `bio_ingredient_composition_reference`

Static composition reference data (`schemas/postgres/043_bio_factory_operations.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `ingredient_name` | VARCHAR(255) | Ingredient name (UNIQUE) |
| `ingredient_category` | VARCHAR(100) | `animal_manure`, `plant_meal`, `animal_concentrate`, `marine_material`, `microbial_inoculant`, `mineral_amendment`, `compost`, `other` |
| `n_pct_min` | NUMERIC(5,2) | N minimum % |
| `n_pct_typical` | NUMERIC(5,2) | N typical % |
| `n_pct_max` | NUMERIC(5,2) | N maximum % |
| `p_pct_min` | NUMERIC(5,2) | P minimum % |
| `p_pct_typical` | NUMERIC(5,2) | P typical % |
| `p_pct_max` | NUMERIC(5,2) | P maximum % |
| `k_pct_min` | NUMERIC(5,2) | K minimum % |
| `k_pct_typical` | NUMERIC(5,2) | K typical % |
| `k_pct_max` | NUMERIC(5,2) | K maximum % |
| `micronutrients` | JSONB | Micronutrients or microbial properties |
| `typical_source` | TEXT | Typical source |
| `state` | VARCHAR(50) | `solid` or `liquid` |
| `composition_summary` | TEXT | Summary |
| `source_reference` | TEXT | Source reference |
| `evidence_maturity` | INTEGER | FK to `evidence_maturity_level` |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

**Microbial inoculant composition** uses different JSONB keys in `micronutrients`:

```json
{
  "fixes_nitrogen": true,
  "solubilizes_phosphorus": false,
  "biocontrol": false,
  "carrier_type": "peat/rice bran"
}
```

### `bio_regional_input_availability`

LAC regional inputs (`schemas/postgres/043_bio_factory_operations.sql`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `region_scope` | VARCHAR(100) | `caribbean`, `central_america`, `south_america`, `mexico`, `latin_america_general`, `other` |
| `input_name` | VARCHAR(255) | Input name (UNIQUE with region_scope) |
| `input_category` | VARCHAR(100) | `marine_material`, `plant_residue`, `agricultural_byproduct`, `animal_manure`, `green_manure`, `other` |
| `country` | VARCHAR(100) | Country |
| `subregion` | VARCHAR(255) | Subregion |
| `seasonality` | TEXT | Seasonality notes |
| `sourcing_notes` | TEXT | Sourcing notes |
| `cautions` | TEXT[] | Safety cautions |
| `quality_considerations` | TEXT | Quality considerations |
| `typical_suppliers` | TEXT | Typical suppliers |
| `source_reference` | TEXT | Source reference |
| `regional_summary` | TEXT | Regional summary |
| `public_summary` | TEXT | Public-safe summary |
| `evidence_maturity` | INTEGER | FK to `evidence_maturity_level` |
| `status` | VARCHAR(50) | `draft`, `submitted`, `verified`, `published`, `rejected` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

## JSONB data structures

### Recipe `ingredients` array

Each ingredient in `bio_recipe_library.ingredients`:

```json
[
  {
    "name": "Banana stems (chopped)",
    "category": "plant_residue",
    "kg_per_batch": 50,
    "notes": "Chopped to 5-10 cm pieces"
  }
]
```

Note: microbial recipes use `ml_per_batch` instead of `kg_per_batch` for liquid cultures.

### Recipe `ratios` object

```json
{
  "c_n_ratio": "25:1",
  "moisture_pct": 65,
  "dilution_ratio": "1:10"
}
```

### Recipe `process_steps` array

```json
[
  {
    "step": 1,
    "day": "Day 1",
    "action": "Layer chopped banana stems with coconut coir",
    "temperature_c": 28,
    "notes": "Maintain moisture at 65%"
  },
  {
    "step": 2,
    "day": "Day 7",
    "action": "Turn pile, add chicken manure",
    "temperature_c": 45,
    "notes": "Target 45-55°C for pathogen kill"
  }
]
```

## Records

| Table | Purpose |
|-------|---------|
| `bio_factory_batch` | Production batch records: type, method, inputs, outputs, conditions, microbial strain |
| `bio_input_provenance` | Ingredient sourcing: supplier, origin, organic certification, NPK, quality warnings |
| `bio_recipe_library` | Recipe knowledge base: ingredients, ratios, process steps, fermentation conditions, quality warnings |
| `bio_factory_distribution` | Distribution tracking: recipient type, quantity, region, application purpose |
| `bio_factory_quality_test` | Quality test results: NPK, pH, microbial count, pass/fail, lab accreditation |
| `bio_ingredient_composition_reference` | Composition matrix: typical NPK ranges, micronutrients, source, state for 24 ingredients (19 nutrient-based + 5 microbial inoculants) |
| `bio_regional_input_availability` | LAC regional inputs: region scope, country, subregion, seasonality, cautions, quality considerations |

## Composition Reference

`bio_ingredient_composition_reference` contains 24 ingredients with typical NPK ranges drawn from agronomy literature and the Kokonut Biofactory research base:

| Ingredient | N-P-K (typical %) | State | Source |
|------------|-------------------|-------|--------|
| Bone meal | 4.5-21-0 | Solid | Slaughterhouse byproducts |
| Blood meal | 12-1-0.5 | Solid | Slaughterhouse byproducts |
| Feather meal | 12-0-0 | Solid | Poultry processing |
| Poultry manure (chicken) | 3.5-1.5-1.5 | Solid | Poultry farming |
| Cattle manure (cow) | 2.5-0.75-1.5 | Solid | Cattle farming |
| Swine manure (pig) | 3-1-1.5 | Solid | Pig farming |
| Alfalfa meal | 3-1-2 | Solid | Dried and ground alfalfa |
| Cottonseed meal | 6-2.5-1.5 | Solid | Cotton processing |
| Neem cake | 5-1-1.5 | Solid | Neem seed processing |
| Kelp meal (Ascophyllum) | 1.25-0.75-7.5 | Solid | Dried and ground kelp |
| Sargassum (Caribbean) | 1-0.3-5 | Solid | Caribbean sargassum (washed) |
| Vermicompost | 1.5-1-1.5 | Solid | Kitchen/garden waste + worms |
| Aerobic compost (mixed) | 2-1-1.5 | Solid | Mixed organic waste |
| Compost tea (aerated) | 0.1-0.5 NPK | Liquid | Aerated compost brew |
| Fish emulsion (fermented) | 4-5-1-1 | Liquid | Fermented fish scraps |
| Seaweed extract (kelp tea) | Low NPK, high K | Liquid | Dried kelp steeped |
| Manure tea | Dilute NPK | Liquid | Aged manure steeped |
| Green manure (legume) | 3-0.25-2 | Solid | Cover crops tilled in |
| Humic acid (leonardite) | Low NPK, high humic | Solid | Processed leonardite |
| Rhizobium inoculant | N-fixation (biological) | Solid | Carrier-based bacterial culture |
| Trichoderma harzianum | Biocontrol (biological) | Solid | Rice bran carrier fungus |
| Bacillus subtilis | P-solubilization (biological) | Liquid | PGPR bacterial culture |
| Mycorrhizal fungi (AMF) | Nutrient uptake extension | Solid | Granular/seed-coat spores |
| Azospirillum brasilense | N-fixation (biological) | Liquid | Associative N-fixer for grasses |

## Recipe Library

Ten seeded recipes in `bio_recipe_library` with full `ingredients`, `ratios`, and `process_steps` JSONB data:

| Recipe | Type | Duration | Key Ingredients |
|--------|------|----------|-----------------|
| Adelphi vermicompost recipe v1 | solid_fertilizer | 45 days | Banana stems, coconut coir, kitchen waste, chicken manure, red wigglers |
| Tropical bokashi recipe | solid_fertilizer | 14 days | Wheat bran, rice bran, molasses, EM inoculant |
| Compost tea aerated brew | liquid_fertilizer | 3 days | Mature vermicompost, water, molasses |
| Sargassum extract (Caribbean) | liquid_fertilizer | 21 days | Washed sargassum, water, optional molasses |
| Fish emulsion (anaerobic fermented) | liquid_fertilizer | 28 days | Fish scraps, sawdust, molasses, water |
| Manure tea (steeped) | liquid_fertilizer | 10 days | Aged chicken manure, water, molasses |
| Tropical aerobic compost | solid_fertilizer | 60 days | Coffee pulp, sugarcane bagasse, rice husks, chicken manure |
| Seaweed extract (kelp steep) | liquid_fertilizer | 2 days | Kelp meal, water |
| Rhizobium inoculant (carrier-based seed treatment) | microbial_biofertilizer | 2 days | Rhizobium culture, peat/rice bran carrier, skim milk powder |
| Trichoderma biofertilizer (rice bran carrier) | microbial_biofertilizer | 14 days | Trichoderma culture, rice bran, corn starch |

Each recipe includes `ingredients` (kg/batch or ml/batch for microbial), `ratios` (C:N, moisture, dilution), `process_steps` (day-by-day with temperature targets), `quality_warnings`, and `application_method`. Recipes are public knowledge for adaptation, not commercial endorsements.

## LAC Regional Inputs

`bio_regional_input_availability` contains 8 LAC-specific entries:

| Region | Input | Notes |
|--------|-------|-------|
| Caribbean | Sargassum seaweed | Requires washing (3-5 rinses) to reduce salts and arsenic. See "Red Diamond Compost Supreme Sea" model. |
| Caribbean | Cocoa pod husks | Best composted due to tannin content and potential pesticide residues. |
| Caribbean | Banana residues | High K; vermicomposting recommended. |
| Central America | Coffee pulp | Requires 2-3 months composting to neutralize acidity and caffeine. |
| South America | Sugarcane bagasse | High C bulking agent; combine with N-rich manures. |
| Latin America general | Sesbania green manure | Fast-growing N-fixing legume. Tilled in at flowering. |
| Mexico | Ascophyllum nodosum | Coastal kelp; regulated harvest for sustainability. |
| Caribbean | Coconut coir and husks | Excellent vermicompost bedding; slow-decomposing husks. |

## Public Views

Five public-safe views expose published, evidence-mature, registry-backed records:

- `v_public_bio_factory_batch_summary` — batches with type, method, yield, conditions.
- `v_public_bio_input_provenance_summary` — ingredients with origin, NPK, quality warnings.
- `v_public_bio_recipe_library_summary` — recipes with type, ingredients, ratios, process steps.
- `v_public_bio_factory_quality_test_summary` — quality tests with parameters, pass/fail.
- `v_public_bio_regional_input_summary` — LAC regional inputs with cautions.

All views require:
- `status = 'published'`
- `evidence_maturity >= 3`
- `public_summary IS NOT NULL`
- For location-scoped views: a verified/published `farm_registry_record` must exist for the location
- Exception: `v_public_bio_regional_input_summary` has no `farm_registry_record` gate (regional data is location-independent)

## Agent synthesis

The bio factory agent (`services/agents/bio_factory_agent.py`, 298 lines) synthesizes public-safe records into a structured summary.

### Data sources

All agent functions read from **public-safe views only**:

| Function | View |
|----------|------|
| `_synthesize_batches()` | `v_public_bio_factory_batch_summary` |
| `_synthesize_provenance()` | `v_public_bio_input_provenance_summary` |
| `_synthesize_recipes()` | `v_public_bio_recipe_library_summary` |
| `_synthesize_quality()` | `v_public_bio_factory_quality_test_summary` |
| `_synthesize_regional()` | `v_public_bio_regional_input_summary` |

### Computed outputs

| Field | Computation |
|-------|-------------|
| `batch_count` | Count of batch rows |
| `provenance_count` | Count of provenance rows |
| `recipe_count` | Count of recipe rows |
| `quality_test_count` | Count of quality test rows |
| `regional_input_count` | Count of regional input rows |
| `total_kg_produced` | Sum of `output_kg_total` across batches |
| `total_liters_produced` | Sum of `output_liters_total` across batches |
| `lac_input_count` | Provenance rows matching LAC keywords |
| `lac_input_share_pct` | `lac_input_count / provenance_count * 100` |
| `unique_input_categories` | Sorted set of input categories |
| `recipe_type_breakdown` | Count per recipe type |
| `quality_pass_rate_pct` | `pass_count / total_tests * 100` |
| `ingredients_with_warnings` | Count of provenance rows with non-empty `quality_warnings` |
| `recipes_with_warnings` | Count of recipe rows with non-empty `quality_warnings` |

### LAC detection

The agent identifies LAC-sourced inputs using keyword matching on `origin_region`:

```
caribbean, central america, south america, monte plata, dominican,
mexico, latin america, sabana grande, greater antilles
```

### Safety integration

- `assert_agent_action_allowed("read", "bio_factory_batch", ...)` on entry
- `assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})` on store
- `validate_output("bio_factory_synthesis", output)` checks for required `summary` field
- Stored summaries are `status='draft'` and require human review

## Report generators

Five registered report types in `services/export/report_generator.py`:

| Report Type | Function | Location-scoped | Period Filter |
|-------------|----------|-----------------|---------------|
| `bio_factory_batch` | `generate_bio_factory_batch()` | Yes | Yes |
| `bio_input_provenance` | `generate_bio_input_provenance()` | Yes | Yes |
| `bio_recipe_library` | `generate_bio_recipe_library()` | No (network-wide) | No |
| `bio_quality_test` | `generate_bio_quality_test()` | Yes | Yes |
| `bio_regional_input` | `generate_bio_regional_input()` | No (network-wide) | No |

Each report returns a `limitations` array with advisory disclaimers specific to the report type. `bio_input_provenance` computes `lac_input_count` and `lac_input_share_pct` using the same LAC keyword matching as the agent.

## Governance & safety

All 7 bio factory tables are registered as governed collections in `services/agents/safety.py`:

```
bio_factory_batch, bio_input_provenance, bio_recipe_library,
bio_factory_distribution, bio_factory_quality_test,
bio_ingredient_composition_reference, bio_regional_input_availability
```

The agent task `bio_factory_synthesis` is registered in `services/agents/tasks.py`:

| Field | Value |
|-------|-------|
| Risk | `medium` |
| Writes | `["ai_summary:draft"]` |
| High-risk | `False` |
| Inputs | `location_id` (optional UUID), `store` (optional boolean) |
| Outputs | `summary` (required object), `ai_summary_id` (optional UUID) |

## EAS Attestation

`kokonut-bio-batch` schema registered on Celo mainnet.

- **Schema UID:** `0x9306a4cf6cc5a9c8aa6598a43bc62cfaa729f7490fe6b2e4cc0df10ec738ff29`
- **Tx hash:** `0x3ea19ac015736d886b0827075a473ef9f3fe47b1878468902e6a7878f1e36694`
- **Block:** 71069923
- **Resolver:** `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` (KokonutResolver)
- **Attester:** `0x3394C45b5938127EB56603A6051dF26CFAF08C26`

Schema fields:

- `locationId` (string) — Kokonut location UUID
- `farmId` (string) — Kokonut farm UUID
- `batchType` (string) — e.g. `vermicompost`, `compost_tea`, `bokashi`, `fish_emulsion`
- `batchId` (string) — bio_factory_batch UUID
- `quantityKg` (uint256) — output weight
- `unit` (string) — e.g. `kg`, `L`
- `productionDate` (uint256) — unix timestamp
- `qualityGrade` (string) — pass/fail/marginal/pending or free-form
- `evidenceHash` (string) — SHA-256 of off-chain evidence
- `payloadCid` (string) — IPFS CID or local content reference

## Dashboards

Five Metabase dashboard cards with daily refresh:

| Card | View | Refresh |
|------|------|---------|
| `57_bio_factory_batches` | `v_public_bio_factory_batch_summary` | Daily 6 AM |
| `58_input_provenance` | `v_public_bio_input_provenance_summary` | Daily 6 AM |
| `59_recipe_library` | `v_public_bio_recipe_library_summary` | Daily 6 AM |
| `60_quality_distribution` | `v_public_bio_factory_quality_test_summary` | Daily 6 AM |
| `61_regional_inputs` | `v_public_bio_regional_input_summary` | Daily 6 AM |

Dashboard datasets are owned by `operations_guild` with `privacy=public_safe`.

## Quality Warnings

`bio_input_provenance` and `bio_recipe_library` include a first-class `quality_warnings TEXT[]` field for documenting known safety considerations:

- Sargassum: `untreated_sargassum_may_contain_salts_and_arsenic`, `requires_washing_and_controlled_extraction`, `heavy_metal_contamination_possible`
- Manure: `requires_aging_to_reduce_pathogens`, `may_contain_bedding_material`
- Compost tea: `use_within_24_hours_for_microbial_benefit`, `do_not_apply_in_direct_sunlight`
- Bokashi: `acidic_do_not_apply_directly_to_roots`, `requires_soil_microbial_activity`

## Commands

```bash
# Run the synthesis agent (location-specific or all)
python3 -m services.agents.bio_factory_agent --location-id UUID
python3 -m services.agents.bio_factory_agent --location-id UUID --store

# Generate report types
python3 -m services.export.report_generator --type bio_factory_batch --location-id UUID
python3 -m services.export.report_generator --type bio_input_provenance --location-id UUID
python3 -m services.export.report_generator --type bio_recipe_library --location-id UUID
python3 -m services.export.report_generator --type bio_quality_test --location-id UUID
python3 -m services.export.report_generator --type bio_regional_input --location-id UUID

# Run module tests
python3 -m tests.test_bio_factory_operations

# Register EAS schema on Celo mainnet (requires ATTESTER_PRIVATE_KEY)
python3 -m services.attestation.cli schema register --name kokonut-bio-batch --chain celo
```

## Testing

```bash
python3 -m tests.test_bio_factory_operations
```

11 tests validating:

| Test | What It Validates |
|------|-------------------|
| `test_bio_factory_schema_defines_records_and_public_views` | All 7 tables, 5 views exist; evidence_maturity >= 3, farm_registry_record, quality_warnings, microbial_strain |
| `test_bio_factory_seed_and_dashboards_exist` | 6 metric keys, 5 dashboard SQL files, 5 dashboard JSON files |
| `test_composition_reference_seeded_with_pdf_data` | 24 ingredients seeded with NPK fields, microbial categories, arsenic warning |
| `test_regional_input_availability_seeded_with_lac_data` | 8 LAC entries, 5 region scopes, "salts and arsenic", "Red Diamond Compost" |
| `test_pilot_seed_has_lac_aware_bio_factory_examples` | Pilot batch names, ingredients, recipe names, microbial recipes |
| `test_bio_factory_agent_task_catalogue_and_validation` | Task registered, writes, risk level, validation error message |
| `test_bio_factory_agent_summarizes_public_safe_records` | Mock cursor with 5 queries; validates synthesis fields, LAC detection, quality pass rate, warnings |
| `test_bio_factory_report_generators_registered` | 5 report types in REPORT_GENERATORS |
| `test_bio_factory_report_generators_public_safe` | Mock cursor; validates report_type fields, limitations for each type |
| `test_eas_bio_batch_placeholder_is_inactive` | EAS schema UID is not placeholder, is active |
| `test_regional_input_seed_evidence_maturity_and_idempotency` | evidence_maturity=3, status='published', ON CONFLICT idempotency |

## Disclaimer

Bio-factory batch yields, input provenance records, and quality test results are **smallholder pilot evidence**, not commercial production guarantees. Recipes are **public knowledge for adaptation**, not commercial endorsements. Quality test results are **advisory**, not certification or regulatory compliance. Sargassum and other marine materials require proper washing and processing before use. Animal-derived materials require aging or composting to reduce pathogen risk.
