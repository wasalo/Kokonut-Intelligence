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

-- Recipe 9: Rhizobium inoculant (carrier-based seed treatment)
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_moisture_pct,
    target_ph, dilution_ratio, application_method, quality_warnings,
    source_reference, recipe_summary, public_summary, limitations,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001808',
    'a0000000-0000-0000-0000-000000000001',
    'Rhizobium inoculant (carrier-based seed treatment)',
    'microbial_biofertilizer',
    'seed_treatment',
    'Carrier-based Rhizobium inoculant for legume seed coating. Uses peat or rice bran as carrier with skim milk powder adhesive. Fixes atmospheric N in legume root nodules. 2-3 day production and drying.',
    '[
        {"name": "rhizobium_culture", "category": "microbial_inoculant", "ml_per_batch": 500, "notes": "Fresh liquid Rhizobium culture (10^8 CFU/ml minimum)"},
        {"name": "carrier_material", "category": "other", "kg_per_batch": 5, "notes": "Sterilized peat, lignite, or rice bran"},
        {"name": "skim_milk_powder", "category": "other", "kg_per_batch": 0.5, "notes": "Adhesive to help carrier stick to seeds"},
        {"name": "water", "category": "water", "liters_per_batch": 2, "notes": "Chlorine-free water for mixing"}
    ]'::jsonb,
    '{"carrier_ratio_kg_per_L": 10, "drying_days": 2, "target_CFU_per_g": "10^7"}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Sterilize carrier material (autoclave or solar heat to 60 C for 2 hours)", "temperature_c": 60, "notes": "Kills competing microbes; essential for pure culture"},
        {"step": 2, "day": 0, "action": "Mix carrier with skim milk powder in clean container", "temperature_c": null, "notes": "Skim milk acts as adhesive and nutrient source"},
        {"step": 3, "day": 0, "action": "Add Rhizobium culture to carrier mixture, mix thoroughly", "temperature_c": null, "notes": "Wear gloves; avoid contamination"},
        {"step": 4, "day": 0, "action": "Add water gradually to achieve damp (not wet) consistency", "temperature_c": null, "notes": "Squeeze test: carrier should hold shape but not drip"},
        {"step": 5, "day": 0, "action": "Spread mixture thinly on clean trays in shaded area", "temperature_c": null, "notes": "Direct sunlight kills Rhizobium; UV-sensitive"},
        {"step": 6, "day": 1, "action": "Turn mixture once during drying", "temperature_c": null, "notes": "Ensures even drying"},
        {"step": 7, "day": 2, "action": "Check moisture: carrier should be crumbly-dry, not powdery", "temperature_c": null, "notes": "Target ~20-30% moisture for storage stability"},
        {"step": 8, "day": 2, "action": "Store in sealed dark container at room temperature", "temperature_c": null, "notes": "Use within 6 months; viability declines over time"}
    ]'::jsonb,
    2,
    30.00,
    7.00,
    null,
    'Coat legume seeds immediately before planting: mix 10-20 g inoculant per kg seed with small amount of water to form slurry, coat seeds evenly, shade-dry 15-30 minutes, then plant',
    ARRAY['Use within 6 months of production — viability declines', 'Store in cool dark place; UV and heat kill Rhizobium', 'Do not mix with chemical seed treatments (fungicides/insecticides)', 'Inoculant must match target legume species (host specificity)', 'Sterilize carrier before use to prevent contamination'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A carrier-based Rhizobium inoculant recipe. Ingredients: 500 ml liquid Rhizobium culture (10^8 CFU/ml), 5 kg sterilized peat/rice bran carrier, 500 g skim milk powder adhesive, 2 L water. Mix, shade-dry 2 days, store sealed. Coat legume seeds at 10-20 g/kg before planting.',
    'Rhizobium inoculant (carrier-based seed treatment): 2-day production. Ingredients: Rhizobium culture (500 ml), carrier material (5 kg), skim milk powder (500 g), water (2 L). Shade-dry 2 days. Coat legume seeds at 10-20 g/kg. Use within 6 months; UV-sensitive.',
    ARRAY['Not a fertilizer — provides living organisms for N-fixation, not nutrients', 'Requires legume host plants (bean, cowpea, groundnut, etc.)', 'Carrier must be sterilized to prevent contamination', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":2,"microbial_type":"rhizobium"}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-rhizobium-inoculant-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();

-- Recipe 10: Trichoderma biofertilizer (rice bran carrier)
INSERT INTO bio_recipe_library (
    id, location_id, recipe_name, recipe_type, recipe_category, description,
    ingredients, ratios, process_steps, fermentation_days, target_c_n_ratio,
    target_moisture_pct, target_temperature_c, target_ph, dilution_ratio,
    application_method, quality_warnings, source_reference,
    recipe_summary, public_summary, limitations, evidence_maturity, status,
    metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001809',
    'a0000000-0000-0000-0000-000000000001',
    'Trichoderma biofertilizer (rice bran carrier)',
    'microbial_biofertilizer',
    'soil_amendment',
    'Carrier-based Trichoderma harzianum biofertilizer using rice bran and corn starch binder. 7-14 day incubation at 28-30 C. Biocontrol fungus that suppresses soil-borne pathogens and promotes root growth.',
    '[
        {"name": "trichoderma_culture", "category": "microbial_inoculant", "ml_per_batch": 500, "notes": "Fresh liquid Trichoderma harzianum culture (10^6 spores/ml minimum)"},
        {"name": "rice_bran", "category": "plant_residue", "kg_per_batch": 10, "notes": "Fresh rice bran, not rancid"},
        {"name": "corn_starch", "category": "other", "kg_per_batch": 0.5, "notes": "Binder to improve carrier structure"},
        {"name": "water", "category": "water", "liters_per_batch": 3, "notes": "Chlorine-free water for mixing"}
    ]'::jsonb,
    '{"carrier_ratio_kg_per_L": 20, "incubation_days": 14, "target_CFU_per_g": "10^6"}'::jsonb,
    '[
        {"step": 1, "day": 0, "action": "Mix rice bran and corn starch in clean container", "temperature_c": null, "notes": "Dry mix first for even distribution"},
        {"step": 2, "day": 0, "action": "Add water gradually to achieve moist (not wet) consistency", "temperature_c": null, "notes": "Squeeze test: should hold shape without dripping"},
        {"step": 3, "day": 0, "action": "Add Trichoderma culture, mix thoroughly with clean hands (gloves)", "temperature_c": null, "notes": "Even distribution of spores throughout carrier"},
        {"step": 4, "day": 0, "action": "Pack mixture into sealed plastic bags (2-3 kg per bag)", "temperature_c": null, "notes": "Seal tightly to maintain humidity during incubation"},
        {"step": 5, "day": 0, "action": "Incubate at 28-30 C in dark area for 7-14 days", "temperature_c": 29, "notes": "Trichoderma grows best at 28-30 C; do not exceed 35 C"},
        {"step": 6, "day": 7, "action": "Check bags for white-green sporulation (indicates Trichoderma growth)", "temperature_c": null, "notes": "White-green mold on surface is normal and desired"},
        {"step": 7, "day": 14, "action": "Open bags and spread mixture thinly to dry in shade", "temperature_c": null, "notes": "Direct sunlight kills spores; shade-dry only"},
        {"step": 8, "day": 14, "action": "Store dried carrier in sealed dark container at room temperature", "temperature_c": null, "notes": "Use within 6 months; store in cool dark place"}
    ]'::jsonb,
    14,
    40.00,
    50.00,
    29.00,
    6.50,
    null,
    'Mix 50-100 g carrier per m2 into top 5 cm of soil before planting; or apply 5-10 g per seedling hole at transplanting',
    ARRAY['Do not expose to direct sunlight — UV kills Trichoderma spores', 'Store in cool dark place; heat above 35 C kills spores', 'Do not mix with chemical fungicides (Trichoderma is a living fungus)', 'White-green sporulation during incubation is normal and desired', 'Use within 6 months of production for maximum viability'],
    'Bio-Organic Fertilizer Categories and Composition (Kokonut Biofactory research)',
    'A 14-day carrier-based Trichoderma biofertilizer recipe. Ingredients: 500 ml liquid Trichoderma culture (10^6 spores/ml), 10 kg rice bran, 500 g corn starch, 3 L water. Incubate sealed at 28-30 C for 14 days, shade-dry, store. Apply 50-100 g/m2 to soil or 5-10 g per seedling hole.',
    'Trichoderma biofertilizer (rice bran carrier): 14-day incubation recipe. Ingredients: Trichoderma culture (500 ml), rice bran (10 kg), corn starch (500 g), water (3 L). Incubate 28-30 C for 14 days, shade-dry. Apply 50-100 g/m2 to soil. Biocontrol fungus suppresses Pythium, Fusarium, Rhizoctonia.',
    ARRAY['Not a fertilizer — provides living biocontrol fungus, not nutrients', 'UV-sensitive; store and apply in shaded conditions', 'Do not mix with chemical fungicides', 'Not a commercial guarantee; smallholder pilot evidence'],
    3,
    'published',
    '{"scale":"smallholder_pilot","region":"tropical","duration_days":14,"microbial_type":"trichoderma"}'::jsonb,
    'pilot_seed',
    'adelphi-recipe-trichoderma-biofertilizer-v1',
    '{"record_type":"bio_recipe_library","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    recipe_name = EXCLUDED.recipe_name,
    public_summary = EXCLUDED.public_summary,
    updated_at = NOW();
