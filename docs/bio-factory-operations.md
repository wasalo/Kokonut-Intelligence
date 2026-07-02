# Bio Factory Operations Hub

The Bio Factory Operations Hub is the Kokonut Intelligence Platform's evidence-governed module for bio-organic fertilizer production, knowledge, and regional adaptation — with an initial focus on Latin America and the Caribbean.

## Purpose

Open-source the components, knowledge, and recipes produced across Kokonut Biofactories. Turn scattered research and production knowledge into a practical, reusable body of documentation that supports both field application and open-source knowledge sharing.

**Audience:** Bio-factory operators, smallholder networks, researchers, regenerative agriculture community, and contributors.

**What this module covers:**

- **Solid fertilizers**: compost, vermicompost, bokashi, biochar, bone meal, blood meal, feather meal, neem cake.
- **Liquid fertilizers**: compost tea, manure tea, fish emulsion, seaweed extract, sargassum extract.
- **Microbial biofertilizers**: Rhizobium, Azospirillum, Azolla, Pseudomonas, Trichoderma, Bacillus subtilis, lactic acid bacteria, mycorrhizal fungi.
- **Composition matrix**: typical N-P-K ranges, micronutrients, and production notes for 20 common ingredients.
- **Regional adaptation**: LAC-specific inputs (sargassum, coffee pulp, cocoa pod husks, banana residues, sesbania, Ascophyllum nodosum, coconut coir) with sourcing notes, seasonality, and cautions.

## Records

| Table | Purpose |
|-------|---------|
| `bio_factory_batch` | Production batch records: type, method, inputs, outputs, conditions, microbial strain |
| `bio_input_provenance` | Ingredient sourcing: supplier, origin, organic certification, NPK, quality warnings |
| `bio_recipe_library` | Recipe knowledge base: ingredients, ratios, process steps, fermentation conditions, quality warnings |
| `bio_factory_distribution` | Distribution tracking: recipient type, quantity, region, application purpose |
| `bio_factory_quality_test` | Quality test results: NPK, pH, microbial count, pass/fail, lab accreditation |
| `bio_ingredient_composition_reference` | Composition matrix: typical NPK ranges, micronutrients, source, state for 20 ingredients |
| `bio_regional_input_availability` | LAC regional inputs: region scope, country, subregion, seasonality, cautions, quality considerations |

## Composition Reference

`bio_ingredient_composition_reference` contains 20 ingredients with typical NPK ranges drawn from agronomy literature and the Kokonut Biofactory research base:

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

## Governed Metrics

Six metric definitions in `metric_definition`:

- `bio_batch_yield_pct` — output kg recovered per input kg.
- `bio_input_provenance_rate_pct` — share of inputs with supplier_verified = TRUE.
- `bio_recipe_reuse_count` — number of batches referencing the same recipe.
- `bio_quality_test_pass_rate_pct` — share of quality tests with pass_fail = pass.
- `bio_distribution_recipient_count` — unique recipient names across distributions.
- `bio_lac_input_share_pct` — share of inputs with origin_region in LAC.

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

## EAS Attestation

`kokonut-bio-batch` schema registered on Celo mainnet. Schema fields:

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

## Quality Warnings

`bio_input_provenance` and `bio_recipe_library` include a first-class `quality_warnings TEXT[]` field for documenting known safety considerations:

- Sargassum: `untreated_sargassum_may_contain_salts_and_arsenic`, `requires_washing_and_controlled_extraction`, `heavy_metal_contamination_possible`
- Manure: `requires_aging_to_reduce_pathogens`, `may_contain_bedding_material`
- Compost tea: `use_within_24_hours_for_microbial_benefit`, `do_not_apply_in_direct_sunlight`
- Bokashi: `acidic_do_not_apply_directly_to_roots`, `requires_soil_microbial_activity`

## Disclaimer

Bio-factory batch yields, input provenance records, and quality test results are **smallholder pilot evidence**, not commercial production guarantees. Recipes are **public knowledge for adaptation**, not commercial endorsements. Quality test results are **advisory**, not certification or regulatory compliance. Sargassum and other marine materials require proper washing and processing before use. Animal-derived materials require aging or composting to reduce pathogen risk.
