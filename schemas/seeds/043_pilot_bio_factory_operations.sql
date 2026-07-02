-- ============================================================
-- 043_pilot_bio_factory_operations.sql — Adelphi bio-organic fertilizer pilot examples
-- ============================================================

-- Batch 1: Vermicompost (45-day cycle)
INSERT INTO bio_factory_batch (
    id, location_id, farm_id, batch_name, batch_type, production_method,
    production_start_date, production_end_date, input_kg_total, output_kg_total,
    batch_yield_pct, moisture_pct, temperature_c, ph_level, batch_summary,
    public_summary, limitations, evidence_maturity, status, metadata,
    source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001700',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'Adelphi 2026 vermicompost batch A',
    'vermicompost',
    'vermicomposting',
    '2026-04-01',
    '2026-05-15',
    180.00,
    153.00,
    85.00,
    65.00,
    22.50,
    7.20,
    'A 45-day vermicompost cycle using kitchen waste, banana stems, coconut coir, and chicken manure as feedstock. Red wiggler worms (Eisenia fetida) processed the material into nutrient-rich castings. Yield is approximate based on feedstock moisture and worm activity.',
    'Adelphi 2026 vermicompost batch A: 45-day cycle processing 180 kg of feedstock (banana stems, coconut coir, kitchen waste, chicken manure) into 153 kg of worm castings (85% yield). Moisture 65%, pH 7.2. Recipe v1 reusable across the network.',
    ARRAY['Yield varies with feedstock moisture and worm activity', 'Batch-scale evidence; not a commercial guarantee'],
    3,
    'published',
    '{"recipe_id":"a0000000-0000-0000-0000-000000001800","input_categories":["plant_residue","animal_manure"],"scale":"smallholder_pilot"}'::jsonb,
    'pilot_seed',
    'adelphi-vermicompost-2026-A',
    '{"record_type":"bio_factory_batch","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    batch_name = EXCLUDED.batch_name,
    output_kg_total = EXCLUDED.output_kg_total,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Batch 2: Compost tea (3-day aerated brew)
INSERT INTO bio_factory_batch (
    id, location_id, farm_id, batch_name, batch_type, production_method,
    production_start_date, production_end_date, input_kg_total, output_liters_total,
    batch_yield_pct, ph_level, batch_summary, public_summary, limitations,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001701',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'Adelphi 2026 compost tea batch B',
    'compost_tea',
    'aerated_brewing',
    '2026-05-20',
    '2026-05-23',
    5.00,
    50.00,
    1000.00,
    6.80,
    'A 3-day aerated compost tea brew using 5 kg of mature vermicompost (from batch A) in 50 L of water. Aquarium pump provides continuous aeration. Molasses added at 0.5% to feed microbial activity.',
    'Adelphi 2026 compost tea batch B: 3-day aerated brew producing 50 L of liquid from 5 kg mature vermicompost (10% w/v). Dilute 1:10 for foliar application. pH 6.8.',
    ARRAY['Microbial activity varies with aeration and temperature', 'Use within 24 hours for maximum microbial benefit'],
    3,
    'published',
    '{"recipe_id":"a0000000-0000-0000-0000-000000001801","input_categories":["compost"],"scale":"smallholder_pilot"}'::jsonb,
    'pilot_seed',
    'adelphi-compost-tea-2026-B',
    '{"record_type":"bio_factory_batch","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    batch_name = EXCLUDED.batch_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Batch 3: Bokashi (14-day anaerobic fermentation)
INSERT INTO bio_factory_batch (
    id, location_id, farm_id, batch_name, batch_type, production_method,
    production_start_date, production_end_date, input_kg_total, output_kg_total,
    batch_yield_pct, moisture_pct, ph_level, batch_summary, public_summary,
    limitations, evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001702',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'Adelphi 2026 bokashi batch C',
    'bokashi',
    'anaerobic',
    '2026-06-01',
    '2026-06-15',
    60.00,
    57.00,
    95.00,
    40.00,
    4.50,
    'A 14-day anaerobic bokashi fermentation using wheat bran, rice bran, molasses, and effective microorganism (EM) inoculant. Sealed bucket with weekly liquid drain. Final product is a fermented solid ready for soil application.',
    'Adelphi 2026 bokashi batch C: 14-day anaerobic fermentation producing 57 kg of fermented bran from 60 kg feedstock (95% yield). pH 4.5 (typical for fermented bokashi). Apply to soil 2 weeks before planting.',
    ARRAY['Bokashi is acidic; do not apply directly to plant roots', 'Requires soil microbial activity to stabilize'],
    3,
    'published',
    '{"recipe_id":"a0000000-0000-0000-0000-000000001802","input_categories":["plant_residue","microbial_inoculum"],"scale":"smallholder_pilot"}'::jsonb,
    'pilot_seed',
    'adelphi-bokashi-2026-C',
    '{"record_type":"bio_factory_batch","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    batch_name = EXCLUDED.batch_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Input provenance: banana stems (Dominican Republic)
INSERT INTO bio_input_provenance (
    id, location_id, farm_id, batch_id, input_name, input_category,
    supplier_name, supplier_verified, organic_certified, origin_country, origin_region,
    input_kg, moisture_pct, nutrient_n_pct, nutrient_p_pct, nutrient_k_pct,
    quality_warnings, input_summary, public_summary, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001710',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000001700',
    'Banana stems (chopped)',
    'plant_residue',
    'Adelphi on-site production',
    TRUE,
    TRUE,
    'Dominican Republic',
    'Sabana Grande de Boya, Monte Plata',
    50.00,
    85.00,
    0.80,
    0.10,
    1.50,
    ARRAY['May contain fungicide residues from conventional banana production'],
    'Banana stems harvested from Adelphi on-site banana plants. Chopped and used as feedstock for vermicompost batch A. Local and organic-certified source.',
    'Banana stems: 50 kg sourced from Adelphi on-site production, Dominican Republic (Sabana Grande de Boya, Monte Plata). Local, organic-certified. Nutrient profile: 0.8% N, 0.1% P, 1.5% K (typical for banana residue). Moisture 85%.',
    3,
    'published',
    '{"region":"caribbean","feedstock_for":"vermicompost"}'::jsonb,
    'pilot_seed',
    'adelphi-input-banana-2026',
    '{"record_type":"bio_input_provenance","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    input_name = EXCLUDED.input_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Input provenance: coconut coir (Dominican Republic)
INSERT INTO bio_input_provenance (
    id, location_id, farm_id, batch_id, input_name, input_category,
    supplier_name, supplier_verified, organic_certified, origin_country, origin_region,
    input_kg, moisture_pct, nutrient_n_pct, nutrient_p_pct, nutrient_k_pct,
    quality_warnings, input_summary, public_summary, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001711',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000001700',
    'Coconut coir',
    'plant_residue',
    'Local Caribbean coconut cooperative',
    TRUE,
    TRUE,
    'Dominican Republic',
    'Caribbean coast',
    30.00,
    20.00,
    0.50,
    0.10,
    0.80,
    ARRAY['May contain salt if not properly processed'],
    'Coconut coir sourced from a local Caribbean coconut cooperative. Used as bedding material and C source for vermicompost batch A. High water retention.',
    'Coconut coir: 30 kg sourced from a local Caribbean coconut cooperative (Dominican Republic). Used as vermicompost bedding. Nutrient profile: 0.5% N, 0.1% P, 0.8% K. Moisture 20% (dried). Organic-certified.',
    3,
    'published',
    '{"region":"caribbean","feedstock_for":"vermicompost"}'::jsonb,
    'pilot_seed',
    'adelphi-input-coconut-2026',
    '{"record_type":"bio_input_provenance","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    input_name = EXCLUDED.input_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Input provenance: chicken manure (Dominican Republic, local supplier)
INSERT INTO bio_input_provenance (
    id, location_id, farm_id, batch_id, input_name, input_category,
    supplier_name, supplier_verified, organic_certified, origin_country, origin_region,
    input_kg, moisture_pct, nutrient_n_pct, nutrient_p_pct, nutrient_k_pct,
    quality_warnings, input_summary, public_summary, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001712',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000001700',
    'Chicken manure (aged)',
    'animal_manure',
    'Local Monte Plata poultry farm',
    TRUE,
    TRUE,
    'Dominican Republic',
    'Monte Plata',
    40.00,
    30.00,
    3.50,
    1.50,
    1.50,
    ARRAY['Aged 6 months to reduce pathogens and ammonia', 'May contain bedding material (rice hulls, sawdust)'],
    'Aged chicken manure from a local Monte Plata poultry farm. Used as N source for vermicompost batch A. Composted 6 months before use to reduce pathogens.',
    'Chicken manure (aged): 40 kg from a local Monte Plata poultry farm (Dominican Republic). Aged 6 months to reduce pathogens. Nutrient profile: 3.5% N, 1.5% P, 1.5% K. Moisture 30%. Organic-certified supplier.',
    3,
    'published',
    '{"region":"caribbean","feedstock_for":"vermicompost"}'::jsonb,
    'pilot_seed',
    'adelphi-input-chicken-manure-2026',
    '{"record_type":"bio_input_provenance","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    input_name = EXCLUDED.input_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Input provenance: sargassum (Caribbean regional, with quality warnings)
INSERT INTO bio_input_provenance (
    id, location_id, farm_id, batch_id, input_name, input_category,
    supplier_name, supplier_verified, organic_certified, origin_country, origin_region,
    input_kg, moisture_pct, nutrient_n_pct, nutrient_p_pct, nutrient_k_pct,
    quality_warnings, input_summary, public_summary, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001713',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    NULL,
    'Sargassum seaweed (washed)',
    'marine_material',
    'Caribbean sargassum processor (washed and processed)',
    TRUE,
    TRUE,
    'Caribbean region',
    'Caribbean Sargassum Belt',
    25.00,
    15.00,
    1.00,
    0.30,
    5.00,
    ARRAY['Untreated sargassum may contain salts and arsenic', 'Requires washing and controlled extraction', 'Heavy metal contamination possible from ocean pollution'],
    'Washed and processed sargassum from a Caribbean processor. Stored for future use in seaweed extract production and as a soil amendment. Washed to remove salts and reduce arsenic risk.',
    'Sargassum (washed): 25 kg from a Caribbean sargassum processor. Washed and processed to reduce salt and arsenic content. Nutrient profile: 1% N, 0.3% P, 5% K (typical for sargassum). WARNING: untreated sargassum may contain salts and arsenic; washing required.',
    3,
    'published',
    '{"region":"caribbean","feedstock_for":"seaweed_extract","reference":"Red_Diamond_Compost_Supreme_Sea"}'::jsonb,
    'pilot_seed',
    'adelphi-input-sargassum-2026',
    '{"record_type":"bio_input_provenance","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    input_name = EXCLUDED.input_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 1: Adelphi vermicompost recipe v1
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_c_n_ratio,
    target_moisture_pct, target_temperature_c, target_ph, dilution_ratio,
    application_method, quality_warnings, source_reference,
    recipe_summary, public_summary, limitations, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001800',
    'a0000000-0000-0000-0000-000000000001',
    'Adelphi vermicompost recipe v1',
    'solid_fertilizer',
    'vermicompost',
    'Smallholder vermicompost recipe using banana stems, coconut coir, kitchen waste, and chicken manure. Adapted for Caribbean tropical conditions with locally available feedstocks.',
    '[
        {"name": "banana_stems_chopped", "category": "plant_residue", "kg_per_batch": 50, "notes": "Chop into 2-5 cm pieces"},
        {"name": "coconut_coir", "category": "plant_residue", "kg_per_batch": 30, "notes": "Rehydrated bedding material"},
        {"name": "kitchen_waste", "category": "plant_residue", "kg_per_batch": 60, "notes": "Vegetable scraps, coffee grounds, no meat or dairy"},
        {"name": "chicken_manure_aged", "category": "animal_manure", "kg_per_batch": 40, "notes": "Aged 6+ months to reduce pathogens"},
        {"name": "red_wigglers", "category": "microbial_inoculum", "kg_per_batch": 2, "notes": "Eisenia fetida, ~2000 worms"}
    ]'::jsonb,
    '{"C:N": 30, "moisture_pct": 65, "worm_density_per_m2": 5000}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Set up bin with moist coconut coir bedding (5-10 cm layer)", "temperature_c": null, "notes": "Bedding should be moist but not dripping"},
        {"step": 2, "day": 0, "action": "Add aged chicken manure and kitchen waste in alternating layers with banana stems", "temperature_c": null, "notes": "Maintain ~30:1 C:N ratio"},
        {"step": 3, "day": 0, "action": "Introduce red wiggler worms on top", "temperature_c": null, "notes": "Worms will migrate down naturally"},
        {"step": 4, "day": 1, "action": "Cover with breathable burlap or cardboard", "temperature_c": null, "notes": "Maintains moisture and darkness"},
        {"step": 5, "day": 7, "action": "Check moisture and worm activity", "temperature_c": null, "notes": "Add water if too dry; add dry material if too wet"},
        {"step": 6, "day": 14, "action": "First feeding: add 10 kg kitchen waste to one side", "temperature_c": null, "notes": "Worms will migrate to fresh food"},
        {"step": 7, "day": 30, "action": "Second feeding: add 10 kg kitchen waste to other side", "temperature_c": null, "notes": "Rotate feeding sides"},
        {"step": 8, "day": 45, "action": "Stop feeding 1 week before harvest", "temperature_c": null, "notes": "Worms will finish remaining material"},
        {"step": 9, "day": 52, "action": "Harvest castings by moving finished compost to one side, add fresh bedding to other side", "temperature_c": null, "notes": "Worms migrate to fresh side in 3-5 days"},
        {"step": 10, "day": 60, "action": "Collect castings, store in breathable container", "temperature_c": null, "notes": "Expected yield: 80-90% of input dry weight"}
    ]'::jsonb,
    45,
    30.00,
    65.00,
    22.50,
    7.00,
    NULL,
    'Side-dress 2-5 cm around plant base, or mix 10-20% into potting soil',
    ARRAY['Temperature below 10C slows worm activity', 'Avoid citrus, onion, garlic, meat, dairy in feedstock'],
    'Adelphi pilot (Adelphi 2026 vermicompost batch A); Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A 45-day vermicompost recipe adapted for Caribbean tropical conditions. Uses banana stems, coconut coir, kitchen waste, and aged chicken manure as feedstock. Target C:N 30:1, moisture 65%, pH 7.0, temperature 20-25C. Expected yield 80-90% of input dry weight.',
    'Adelphi vermicompost recipe v1: 45-day cycle for Caribbean tropical conditions. Ingredients: banana stems (50 kg), coconut coir (30 kg), kitchen waste (60 kg), aged chicken manure (40 kg), red wigglers (2 kg). Target C:N 30:1, moisture 65%, pH 7.0. Expected yield 80-90%.',
    ARRAY['Yield varies with feedstock moisture and worm activity', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"caribbean","duration_days":45}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-vermicompost-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 2: Tropical bokashi recipe
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_c_n_ratio,
    target_moisture_pct, target_ph, dilution_ratio, application_method,
    quality_warnings, source_reference, recipe_summary, public_summary,
    limitations, evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001801',
    'a0000000-0000-0000-0000-000000000001',
    'Tropical bokashi recipe',
    'solid_fertilizer',
    'bokashi',
    'Anaerobic fermented bran recipe using wheat bran, rice bran, molasses, and effective microorganism (EM) inoculant. Fast 14-day fermentation for tropical conditions.',
    '[
        {"name": "wheat_bran", "category": "plant_residue", "kg_per_batch": 30, "notes": "Dry substrate base"},
        {"name": "rice_bran", "category": "plant_residue", "kg_per_batch": 20, "notes": "Dry substrate base"},
        {"name": "molasses", "category": "other", "kg_per_batch": 2, "notes": "Energy source for EM"},
        {"name": "em_inoculant", "category": "microbial_inoculum", "kg_per_batch": 1, "notes": "Effective microorganism culture"},
        {"name": "water", "category": "water", "kg_per_batch": 10, "notes": "Moisten to ~40%"}
    ]'::jsonb,
    '{"C:N": 25, "moisture_pct": 40, "fermentation_temp_c": 25}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Mix wheat bran and rice bran in clean bucket", "temperature_c": null, "notes": "Dry mix thoroughly"},
        {"step": 2, "day": 0, "action": "Dissolve molasses in 10 L warm water", "temperature_c": null, "notes": "Water should be ~30C (not hot)"},
        {"step": 3, "day": 0, "action": "Add EM inoculant to molasses water", "temperature_c": null, "notes": "Mix well"},
        {"step": 4, "day": 0, "action": "Pour molasses-EM solution over bran mix and combine thoroughly", "temperature_c": null, "notes": "Target moisture 40% (squeeze test: drop, not stream)"},
        {"step": 5, "day": 0, "action": "Press mixture firmly into sealed bucket, remove air pockets", "temperature_c": null, "notes": "Anaerobic conditions required"},
        {"step": 6, "day": 0, "action": "Seal bucket with lid and valve for liquid drain", "temperature_c": null, "notes": "Gas release expected"},
        {"step": 7, "day": 7, "action": "Drain liquid (bokashi tea) from valve", "temperature_c": null, "notes": "Dilute 1:100 for use as liquid fertilizer"},
        {"step": 8, "day": 14, "action": "Harvest fermented bokashi", "temperature_c": null, "notes": "Sweet-sour smell indicates successful fermentation"}
    ]'::jsonb,
    14,
    25.00,
    40.00,
    4.50,
    '1:100 for bokashi tea',
    'Apply to soil 2 weeks before planting (do not apply directly to roots)',
    ARRAY['Bokashi is acidic; do not apply directly to plant roots', 'Requires soil microbial activity to stabilize'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A 14-day anaerobic bokashi recipe using wheat bran, rice bran, molasses, and EM inoculant. Target C:N 25:1, moisture 40%, pH 4.5. Produces bokashi tea (liquid) as a byproduct.',
    'Tropical bokashi recipe: 14-day anaerobic fermentation. Ingredients: wheat bran (30 kg), rice bran (20 kg), molasses (2 kg), EM inoculant (1 kg), water (10 L). Target C:N 25:1, moisture 40%, pH 4.5. Produces bokashi tea (1:100 dilution) as byproduct.',
    ARRAY['Bokashi is acidic; soil application only', 'Requires soil microbial activity to stabilize', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":14}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-bokashi-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 3: Compost tea (aerated)
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_moisture_pct,
    target_ph, dilution_ratio, application_method, quality_warnings,
    source_reference, recipe_summary, public_summary, limitations,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001802',
    'a0000000-0000-0000-0000-000000000001',
    'Compost tea aerated brew',
    'liquid_fertilizer',
    'compost_tea',
    'Aerated compost tea recipe using mature vermicompost. 3-day brew with continuous aeration and molasses for microbial feed.',
    '[
        {"name": "mature_vermicompost", "category": "compost", "kg_per_batch": 5, "notes": "Mature castings from vermicompost batch"},
        {"name": "water", "category": "water", "liters_per_batch": 50, "notes": "Chlorine-free water preferred"},
        {"name": "molasses", "category": "other", "kg_per_batch": 0.25, "notes": "0.5% microbial feed"}
    ]'::jsonb,
    '{"compost_concentration_pct": 10, "molasses_pct": 0.5, "aeration_duration_hours": 72}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Fill bucket with 50 L chlorine-free water", "temperature_c": null, "notes": "Let tap water sit 24 hours to dechlorinate if needed"},
        {"step": 2, "day": 0, "action": "Add 5 kg mature vermicompost in mesh bag", "temperature_c": null, "notes": "Mesh bag allows microbial access while keeping solids contained"},
        {"step": 3, "day": 0, "action": "Add 250 g molasses and stir to dissolve", "temperature_c": null, "notes": "Molasses feeds beneficial bacteria"},
        {"step": 4, "day": 0, "action": "Insert aquarium pump and start aeration", "temperature_c": null, "notes": "Continuous bubbling required"},
        {"step": 5, "day": 1, "action": "Check foam and smell (earthy sweet = good)", "temperature_c": null, "notes": "Anaerobic smell = problem, restart"},
        {"step": 6, "day": 3, "action": "Remove mesh bag and stop aeration", "temperature_c": null, "notes": "Use within 24 hours for maximum benefit"},
        {"step": 7, "day": 3, "action": "Dilute 1:10 for foliar application", "temperature_c": null, "notes": "Apply in early morning or evening"}
    ]'::jsonb,
    3,
    100.00,
    6.80,
    '1:10 for foliar spray',
    'Foliar spray in early morning or evening; soil drench undiluted',
    ARRAY['Use within 24 hours of brewing for maximum microbial benefit', 'Do not apply in direct sunlight'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research); Adelphi pilot',
    'A 3-day aerated compost tea recipe. Ingredients: 5 kg mature vermicompost, 50 L water, 250 g molasses. Continuous aeration with aquarium pump. Dilute 1:10 for foliar spray.',
    'Compost tea aerated brew: 3-day aerated recipe. Ingredients: mature vermicompost (5 kg), water (50 L), molasses (250 g). Continuous aeration. Dilute 1:10 for foliar application.',
    ARRAY['Use within 24 hours for maximum microbial benefit', 'Microbial activity varies with aeration and temperature', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":3}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-compost-tea-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 4: Sargassum extract (Caribbean)
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_moisture_pct,
    target_ph, dilution_ratio, application_method, quality_warnings,
    source_reference, recipe_summary, public_summary, limitations,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001803',
    'a0000000-0000-0000-0000-000000000001',
    'Sargassum extract (Caribbean)',
    'liquid_fertilizer',
    'seaweed_extract',
    'Sargassum seaweed extract recipe for Caribbean conditions. Uses washed sargassum to reduce salt and arsenic content. 2-4 week steeping process.',
    '[
        {"name": "sargassum_washed", "category": "marine_material", "kg_per_batch": 10, "notes": "Washed to remove salts and reduce arsenic"},
        {"name": "water", "category": "water", "liters_per_batch": 40, "notes": "Chlorine-free water"},
        {"name": "molasses", "category": "other", "kg_per_batch": 0.4, "notes": "Optional microbial feed"}
    ]'::jsonb,
    '{"seaweed_concentration_pct": 25, "steeping_duration_days": 21, "dilution_ratio": "1:10"}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Collect fresh sargassum from beach or supplier", "temperature_c": null, "notes": "Rinse with seawater to remove sand and debris"},
        {"step": 2, "day": 0, "action": "Wash sargassum thoroughly with fresh water (3-5 rinses)", "temperature_c": null, "notes": "Critical for salt and arsenic reduction"},
        {"step": 3, "day": 0, "action": "Chop sargassum into 5-10 cm pieces", "temperature_c": null, "notes": "Increases surface area for extraction"},
        {"step": 4, "day": 0, "action": "Pack into barrel and cover with 40 L water", "temperature_c": null, "notes": "Some recipes use 1:4 seaweed:water by volume"},
        {"step": 5, "day": 0, "action": "Cover with lid (allow gas release)", "temperature_c": null, "notes": "Anaerobic or aerobic steeping both work"},
        {"step": 6, "day": 0, "action": "Stir weekly", "temperature_c": null, "notes": "Aerates and distributes nutrients"},
        {"step": 7, "day": 21, "action": "Strain liquid through mesh", "temperature_c": null, "notes": "Discard solids or compost them"},
        {"step": 8, "day": 21, "action": "Dilute 1:10 for foliar application", "temperature_c": null, "notes": "Apply in early morning or evening"}
    ]'::jsonb,
    21,
    100.00,
    7.00,
    '1:10 for foliar spray',
    'Foliar spray or soil drench; apply during vegetative growth',
    ARRAY['Untreated sargassum may contain salts and arsenic', 'Washing with fresh water is critical (3-5 rinses)', 'Heavy metal contamination possible from ocean pollution', 'Test on small area before full application'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research); Caribbean biofertilizer initiatives (Red Diamond Compost Supreme Sea)',
    'A 21-day sargassum extract recipe for Caribbean conditions. Uses washed sargassum (3-5 fresh water rinses) to reduce salt and arsenic content. Dilute 1:10 for foliar application. WARNING: washing is critical.',
    'Sargassum extract (Caribbean): 21-day steeping recipe. Ingredients: washed sargassum (10 kg), water (40 L), optional molasses (400 g). Dilute 1:10 for foliar application. WARNING: washing is critical to reduce salts and arsenic.',
    ARRAY['Untreated sargassum may contain salts and arsenic', 'Washing is critical and time-consuming', 'Heavy metal contamination possible', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"caribbean","duration_days":21,"reference":"Red_Diamond_Compost"}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-sargassum-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Distribution: vermicompost to smallholder network
INSERT INTO bio_factory_distribution (
    id, location_id, farm_id, batch_id, recipient_type, recipient_name,
    recipient_region, distribution_date, quantity_kg, unit, application_purpose,
    distribution_summary, public_summary, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001720',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000001700',
    'smallholder_network',
    'Adelphi smallholder network (3 farms)',
    'Sabana Grande de Boya, Monte Plata',
    '2026-05-20',
    120.00,
    'kg',
    'Soil amendment for kitchen gardens',
    'Distributed 120 kg of vermicompost from batch A to 3 smallholder farms in the Adelphi network for kitchen garden soil amendment. Each farm received 40 kg.',
    'Adelphi vermicompost batch A: 120 kg distributed to 3 smallholder farms in the Adelphi network (Sabana Grande de Boya, Monte Plata) on 2026-05-20 for kitchen garden soil amendment. Each farm received 40 kg.',
    3,
    'published',
    '{"region":"caribbean","recipient_count":3,"fertilizer_type":"vermicompost"}'::jsonb,
    'pilot_seed',
    'adelphi-distribution-vermicompost-2026',
    '{"record_type":"bio_factory_distribution","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    distribution_summary = EXCLUDED.distribution_summary,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Quality test: NPK analysis on vermicompost batch A
INSERT INTO bio_factory_quality_test (
    id, location_id, farm_id, batch_id, test_date, test_type, parameter_name,
    measured_value, unit, target_min, target_max, pass_fail, lab_name, lab_accredited,
    test_summary, public_summary, evidence_maturity, status, metadata,
    source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001730',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000001700',
    '2026-05-25',
    'nutrient_analysis',
    'NPK total',
    4.20,
    'pct',
    3.00,
    6.00,
    'pass',
    'Adelphi on-site lab',
    FALSE,
    'NPK analysis of vermicompost batch A showing 1.5% N, 1.4% P, 1.3% K (total 4.2%). Within expected range for vermicompost. On-site lab (not accredited).',
    'Adelphi vermicompost batch A quality test: NPK analysis on 2026-05-25 shows 4.2% total NPK (1.5% N, 1.4% P, 1.3% K). Result: pass. On-site lab (not externally accredited).',
    3,
    'published',
    '{"lab_accreditation":"none","test_method":"on_site_kjeldahl"}'::jsonb,
    'pilot_seed',
    'adelphi-quality-vermicompost-2026-A',
    '{"record_type":"bio_factory_quality_test","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    test_summary = EXCLUDED.test_summary,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();
