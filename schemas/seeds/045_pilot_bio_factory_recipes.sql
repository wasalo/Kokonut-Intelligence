-- ============================================================
-- 045_pilot_bio_factory_recipes.sql — Additional recipes and input provenance for Bio Factory pilot
-- Phase 3 gap closure: adds recipes 5-8 and input provenance rows for coffee pulp + fish waste
-- ============================================================

-- Input provenance: coffee pulp (Dominican Republic)
INSERT INTO bio_input_provenance (
    id, location_id, farm_id, batch_id, input_name, input_category,
    supplier_name, supplier_verified, organic_certified, origin_country, origin_region,
    input_kg, moisture_pct, nutrient_n_pct, nutrient_p_pct, nutrient_k_pct,
    quality_warnings, input_summary, public_summary, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001714',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    NULL,
    'Coffee pulp (composted)',
    'agricultural_byproduct',
    'Local Monte Plata coffee cooperative',
    TRUE,
    TRUE,
    'Dominican Republic',
    'Monte Plata',
    35.00,
    70.00,
    2.00,
    0.30,
    1.50,
    ARRAY['Requires 2-3 months composting to neutralize acidity and caffeine', 'May contain pesticide residues from conventional coffee farming'],
    'Composted coffee pulp from a local Monte Plata coffee cooperative. Composted 3 months to neutralize acidity and caffeine content before use as feedstock.',
    'Coffee pulp (composted): 35 kg from a local Monte Plata coffee cooperative (Dominican Republic). Composted 3 months to neutralize acidity and caffeine. Nutrient profile: 2% N, 0.3% P, 1.5% K. Moisture 70%. Organic-certified.',
    3,
    'published',
    '{"region":"caribbean","feedstock_for":"aerobic_compost","composting_months":3}'::jsonb,
    'pilot_seed',
    'adelphi-input-coffee-pulp-2026',
    '{"record_type":"bio_input_provenance","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    input_name = EXCLUDED.input_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Input provenance: fish waste (local)
INSERT INTO bio_input_provenance (
    id, location_id, farm_id, batch_id, input_name, input_category,
    supplier_name, supplier_verified, organic_certified, origin_country, origin_region,
    input_kg, moisture_pct, nutrient_n_pct, nutrient_p_pct, nutrient_k_pct,
    quality_warnings, input_summary, public_summary, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001715',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    NULL,
    'Fish waste (fresh scraps)',
    'fish_waste',
    'Local fishing cooperative',
    TRUE,
    TRUE,
    'Dominican Republic',
    'Bayahibe coastal area',
    15.00,
    60.00,
    4.50,
    1.00,
    1.00,
    ARRAY['Requires fermentation to reduce pathogens and odor', 'Handle with gloves; may contain parasites', 'Use within 24 hours of collection or freeze'],
    'Fresh fish scraps from a local fishing cooperative in Bayahibe. Used as feedstock for fish emulsion production. High nitrogen content suitable for liquid fertilizer.',
    'Fish waste (fresh scraps): 15 kg from a local fishing cooperative (Bayahibe, Dominican Republic). Fresh scraps for fish emulsion production. Nutrient profile: 4.5% N, 1% P, 1% K. Moisture 60%. Handle with gloves; requires fermentation.',
    3,
    'published',
    '{"region":"caribbean","feedstock_for":"fish_emulsion","precaution":"fermentation_required"}'::jsonb,
    'pilot_seed',
    'adelphi-input-fish-waste-2026',
    '{"record_type":"bio_input_provenance","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    input_name = EXCLUDED.input_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 5: Fish emulsion (anaerobic fermented)
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_c_n_ratio,
    target_moisture_pct, target_temperature_c, target_ph, dilution_ratio,
    application_method, quality_warnings, source_reference,
    recipe_summary, public_summary, limitations, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001804',
    'a0000000-0000-0000-0000-000000000001',
    'Fish emulsion (anaerobic fermented)',
    'liquid_fertilizer',
    'fish_emulsion',
    'Anaerobic fermented fish emulsion using fresh fish scraps, sawdust carrier, and molasses. 4-week fermentation with periodic stirring. High-nitrogen liquid fertilizer for foliar or soil application.',
    '[
        {"name": "fish_scraps_fresh", "category": "fish_waste", "kg_per_batch": 5, "notes": "Fresh scraps from local fishing cooperative"},
        {"name": "sawdust", "category": "plant_residue", "kg_per_batch": 2, "notes": "Dry carrier material, absorbs moisture"},
        {"name": "molasses", "category": "other", "kg_per_batch": 0.5, "notes": "Energy source for fermentation microbes"},
        {"name": "water", "category": "water", "liters_per_batch": 10, "notes": "Chlorine-free water"}
    ]'::jsonb,
    '{"fish_concentration_pct": 25, "fermentation_temp_c": 25, "dilution_ratio": "1:5-10"}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Chop fish scraps into small pieces (2-3 cm)", "temperature_c": null, "notes": "Increase surface area for fermentation"},
        {"step": 2, "day": 0, "action": "Layer fish, sawdust, and molasses in sealed bucket", "temperature_c": null, "notes": "Alternate layers for even distribution"},
        {"step": 3, "day": 0, "action": "Add water to cover mixture, seal bucket with airlock", "temperature_c": null, "notes": "Anaerobic conditions required"},
        {"step": 4, "day": 3, "action": "First stir — break surface crust", "temperature_c": null, "notes": "Gas release expected; work outdoors"},
        {"step": 5, "day": 7, "action": "Stir every 2-3 days for first 2 weeks", "temperature_c": null, "notes": "Strong odor is normal; keep sealed between stirs"},
        {"step": 6, "day": 14, "action": "Reduce stirring to weekly", "temperature_c": null, "notes": "Fermentation should be slowing"},
        {"step": 7, "day": 28, "action": "Strain liquid through mesh, discard solids", "temperature_c": null, "notes": "Solids can be composted separately"},
        {"step": 8, "day": 28, "action": "Dilute 1:5-10 for soil drench or foliar spray", "temperature_c": null, "notes": "Apply in evening; strong smell dissipates in soil"}
    ]'::jsonb,
    28,
    NULL,
    100.00,
    25.00,
    5.50,
    '1:5-10 for soil drench or foliar spray',
    'Soil drench or foliar spray in evening; dilute heavily',
    ARRAY['Strong odor during fermentation — work outdoors', 'Handle with gloves; may contain pathogens before full fermentation', 'Dilute heavily to avoid burning plants'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A 28-day anaerobic fish emulsion recipe. Ingredients: 5 kg fresh fish scraps, 2 kg sawdust, 500 g molasses, 10 L water. Ferment 4 weeks with periodic stirring. Dilute 1:5-10 before application.',
    'Fish emulsion (anaerobic fermented): 28-day fermentation. Ingredients: fish scraps (5 kg), sawdust (2 kg), molasses (500 g), water (10 L). Dilute 1:5-10 for soil drench or foliar spray. Strong odor during fermentation.',
    ARRAY['Strong odor during fermentation', 'Requires outdoor workspace', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":28}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-fish-emulsion-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 6: Manure tea (steeped)
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_moisture_pct,
    target_ph, dilution_ratio, application_method, quality_warnings,
    source_reference, recipe_summary, public_summary, limitations,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001805',
    'a0000000-0000-0000-0000-000000000001',
    'Manure tea (steeped)',
    'liquid_fertilizer',
    'manure_tea',
    'Steeped manure tea using aged chicken manure and molasses. 7-14 day steeping process with periodic stirring. Dilute heavily for foliar or soil application.',
    '[
        {"name": "chicken_manure_aged", "category": "animal_manure", "kg_per_batch": 5, "notes": "Aged 6+ months to reduce pathogens"},
        {"name": "water", "category": "water", "liters_per_batch": 20, "notes": "Chlorine-free water"},
        {"name": "molasses", "category": "other", "kg_per_batch": 0.1, "notes": "Optional microbial feed (1 tsp per gallon)"}
    ]'::jsonb,
    '{"manure_concentration_pct": 25, "steeping_duration_days": 10, "dilution_ratio": "1:10-20"}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Place aged manure in mesh bag or burlap sack", "temperature_c": null, "notes": "Mesh bag keeps solids contained while allowing nutrient leaching"},
        {"step": 2, "day": 0, "action": "Submerge in 20 L water, add molasses, stir", "temperature_c": null, "notes": "Molasses feeds beneficial microbes"},
        {"step": 3, "day": 0, "action": "Cover bucket and place in shaded area", "temperature_c": null, "notes": "Direct sunlight degrades nutrients"},
        {"step": 4, "day": 3, "action": "Stir daily", "temperature_c": null, "notes": "Aerates and distributes nutrients"},
        {"step": 5, "day": 7, "action": "Check smell (earthy = good; putrid = restart)", "temperature_c": null, "notes": "Putrid smell indicates anaerobic problems"},
        {"step": 6, "day": 10, "action": "Remove mesh bag, strain if needed", "temperature_c": null, "notes": "Liquid should be dark brown, not black"},
        {"step": 7, "day": 10, "action": "Dilute 1:10-20 for application", "temperature_c": null, "notes": "More dilute for foliar; less for soil drench"}
    ]'::jsonb,
    10,
    100.00,
    7.00,
    '1:10-20 for soil drench or foliar spray',
    'Soil drench or foliar spray; dilute heavily',
    ARRAY['Use only aged manure (6+ months) to reduce pathogen risk', 'Do not apply undiluted — will burn plants', 'Strong odor during steeping'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A 10-day steeped manure tea recipe. Ingredients: 5 kg aged chicken manure, 20 L water, 100 g molasses. Steep 7-14 days with daily stirring. Dilute 1:10-20 before application.',
    'Manure tea (steeped): 10-day steeping recipe. Ingredients: aged chicken manure (5 kg), water (20 L), molasses (100 g). Dilute 1:10-20 for soil drench or foliar spray. Use only aged manure.',
    ARRAY['Use only aged manure to reduce pathogens', 'Strong odor during steeping', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":10}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-manure-tea-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 7: Tropical aerobic compost
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_c_n_ratio,
    target_moisture_pct, target_temperature_c, target_ph, dilution_ratio,
    application_method, quality_warnings, source_reference,
    recipe_summary, public_summary, limitations, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001806',
    'a0000000-0000-0000-0000-000000000001',
    'Tropical aerobic compost',
    'solid_fertilizer',
    'compost',
    'Aerobic composting recipe using coffee pulp, sugarcane bagasse, rice husks, and chicken manure. 60-day turned pile method optimized for tropical conditions with high ambient temperature.',
    '[
        {"name": "coffee_pulp_composted", "category": "agricultural_byproduct", "kg_per_batch": 40, "notes": "Composted 3 months to reduce acidity"},
        {"name": "sugarcane_bagasse", "category": "plant_residue", "kg_per_batch": 30, "notes": "High C bulking agent"},
        {"name": "rice_husks", "category": "plant_residue", "kg_per_batch": 15, "notes": "Aeration and structure"},
        {"name": "chicken_manure_aged", "category": "animal_manure", "kg_per_batch": 20, "notes": "Aged 6+ months, N source"},
        {"name": "water", "category": "water", "liters_per_batch": 20, "notes": "For moisture adjustment"}
    ]'::jsonb,
    '{"C:N": 30, "moisture_pct": 55, "pile_height_m": 1.2, "turn_interval_days": 14}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Chop bagasse and mix dry materials (coffee pulp, bagasse, rice husks)", "temperature_c": null, "notes": "Target C:N ~30:1"},
        {"step": 2, "day": 0, "action": "Add aged chicken manure and mix thoroughly", "temperature_c": null, "notes": "N source to balance high-C materials"},
        {"step": 3, "day": 0, "action": "Moisten to 55% (squeeze test: damp, not dripping)", "temperature_c": null, "notes": "Add water gradually while mixing"},
        {"step": 4, "day": 0, "action": "Build pile to 1.2 m height in shaded area", "temperature_c": null, "notes": "Large pile retains heat in tropical conditions"},
        {"step": 5, "day": 7, "action": "Check internal temperature (target 55-65 C)", "temperature_c": 60, "notes": "Thermophilic phase kills pathogens and weed seeds"},
        {"step": 6, "day": 14, "action": "First turn: move outer material to center", "temperature_c": null, "notes": "Re-aerates and redistributes moisture"},
        {"step": 7, "day": 28, "action": "Second turn", "temperature_c": null, "notes": "Temperature should start declining"},
        {"step": 8, "day": 42, "action": "Third turn; check for dark crumbly texture", "temperature_c": null, "notes": "Should smell earthy, not sour"},
        {"step": 9, "day": 60, "action": "Harvest finished compost", "temperature_c": null, "notes": "Expected yield: 50-60% of input dry weight"}
    ]'::jsonb,
    60,
    30.00,
    55.00,
    60.00,
    7.50,
    NULL,
    'Apply 5-10 cm as topdress or mix 20-30% into potting soil',
    ARRAY['Ensure pile reaches 55 C to kill pathogens', 'Turn regularly to prevent anaerobic conditions', 'Finished compost should be dark, crumbly, earthy-smelling'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A 60-day aerobic compost recipe using coffee pulp, sugarcane bagasse, rice husks, and aged chicken manure. Target C:N 30:1, moisture 55%, internal temperature 55-65 C. Turn every 14 days.',
    'Tropical aerobic compost: 60-day turned pile method. Ingredients: coffee pulp (40 kg), sugarcane bagasse (30 kg), rice husks (15 kg), aged chicken manure (20 kg), water (20 L). Target C:N 30:1, moisture 55%. Turn every 14 days.',
    ARRAY['Requires regular turning to maintain aerobic conditions', 'Tropical heat may accelerate decomposition; monitor temperature', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":60}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-aerobic-compost-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 8: Seaweed extract (kelp steep)
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_moisture_pct,
    target_ph, dilution_ratio, application_method, quality_warnings,
    source_reference, recipe_summary, public_summary, limitations,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001807',
    'a0000000-0000-0000-0000-000000000001',
    'Seaweed extract (kelp steep)',
    'liquid_fertilizer',
    'seaweed_extract',
    'Kelp meal steeping recipe for liquid seaweed extract. 2-3 day steep with periodic stirring. Low NPK but high K and micronutrients. Suitable for foliar application during vegetative growth.',
    '[
        {"name": "kelp_meal", "category": "marine_material", "kg_per_batch": 1, "notes": "Dried and ground Ascophyllum nodosum or local kelp"},
        {"name": "water", "category": "water", "liters_per_batch": 20, "notes": "Chlorine-free water"}
    ]'::jsonb,
    '{"kelp_concentration_pct": 5, "steeping_duration_days": 2, "dilution_ratio": "1:10"}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Add 1 kg kelp meal to 20 L water in bucket", "temperature_c": null, "notes": "Use room temperature or slightly warm water"},
        {"step": 2, "day": 0, "action": "Stir vigorously to break up clumps", "temperature_c": null, "notes": "Kelp meal absorbs water quickly"},
        {"step": 3, "day": 0, "action": "Cover bucket and place in shaded area", "temperature_c": null, "notes": "Direct sunlight may degrade some nutrients"},
        {"step": 4, "day": 1, "action": "Stir twice daily", "temperature_c": null, "notes": "Distributes nutrients and prevents settling"},
        {"step": 5, "day": 2, "action": "Strain through fine mesh or cheesecloth", "temperature_c": null, "notes": "Solids can be composted or used as mulch"},
        {"step": 6, "day": 2, "action": "Dilute 1:10 for foliar spray", "temperature_c": null, "notes": "Apply in early morning or evening"}
    ]'::jsonb,
    2,
    100.00,
    7.00,
    '1:10 for foliar spray',
    'Foliar spray during vegetative growth; soil drench for micronutrients',
    ARRAY['Low NPK — supplement with N source if needed', 'Kelp meal quality varies; use food-grade or agricultural-grade only'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A 2-day kelp meal steeping recipe. Ingredients: 1 kg kelp meal, 20 L water. Steep 2-3 days with daily stirring. Dilute 1:10 for foliar application. High K and micronutrients, low NPK.',
    'Seaweed extract (kelp steep): 2-day steeping recipe. Ingredients: kelp meal (1 kg), water (20 L). Dilute 1:10 for foliar spray. High K and micronutrients; supplement with N source if needed.',
    ARRAY['Low NPK content — not a complete fertilizer', 'Quality varies by kelp source', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":2}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-seaweed-kelp-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();
