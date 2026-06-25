-- ============================================================
-- Seed: Adelphi carbon framework pilot data
-- ============================================================
-- Tree inventory, underplanting events, GHG emissions,
-- framework phases, regenerative practice checklist, and
-- climate-impact summaries for Kokonut Adelphi.

-- Tree inventory (coconut and companion species)
INSERT INTO tree_inventory (id, location_id, plot_id, zone_id, species_name, tree_count, avg_height_m, avg_dbh_cm, avg_canopy_diameter_m, maturity_stage, planting_date, survey_date, biomass_estimate_kg, carbon_estimate_tonnes, co2e_estimate_tonnes, allometric_source, notes, status, source_system, source_id) VALUES
-- Mature coconut in agroforestry corridor
('a0000000-0000-0000-0000-000000000800', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'Cocos nucifera', 85, 12.0, 35.0, 8.0, 'mature', '2018-06-01', '2026-03-01', 25500.00, 11985.00, 43985.00, 'Nair et al. 2009 - coconut allometric', 'Mature coconut palms along agroforestry corridor', 'published', 'pilot_seed', 'adelphi-tree-coconut-2026-03'),
-- Young coconut in syntropic beds
('a0000000-0000-0000-0000-000000000801', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000700', 'Cocos nucifera', 12, 4.0, 15.0, 3.0, 'juvenile', '2025-03-01', '2026-03-01', 360.00, 169.20, 621.00, 'Rajagopalan et al. 2018', 'Young coconut interspersed in syntropic beds', 'published', 'pilot_seed', 'adelphi-tree-coconut-young-2026-03'),
-- Passion fruit vines
('a0000000-0000-0000-0000-000000000802', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'Passiflora edulis', 120, 3.0, NULL, NULL, 'mature', '2025-06-01', '2026-03-01', 480.00, 225.60, 828.00, 'Local estimate - vine biomass', 'Passion fruit vines on coconut support structures', 'published', 'pilot_seed', 'adelphi-tree-passion-2026-03')
ON CONFLICT (id) DO UPDATE SET
    species_name = EXCLUDED.species_name,
    tree_count = EXCLUDED.tree_count,
    avg_height_m = EXCLUDED.avg_height_m,
    survey_date = EXCLUDED.survey_date,
    biomass_estimate_kg = EXCLUDED.biomass_estimate_kg,
    carbon_estimate_tonnes = EXCLUDED.carbon_estimate_tonnes,
    co2e_estimate_tonnes = EXCLUDED.co2e_estimate_tonnes,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Underplanting events (companion species in multi-strata corridor)
INSERT INTO underplanting_event (id, location_id, zone_id, plot_id, species_name, species_role, planting_date, area_m2, plant_count, expected_benefit, survival_count, survival_survey_date, notes, status, source_system, source_id) VALUES
('a0000000-0000-0000-0000-000000000810', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000021', 'Canavalia ensiformis', 'nitrogen_fixer', '2025-10-15', 2000.00, 400, 'Nitrogen fixation and living ground cover', 360, '2026-01-15', 'Cover crop between coconut rows', 'published', 'pilot_seed', 'adelphi-underplant-canavalia-2025-10'),
('a0000000-0000-0000-0000-000000000811', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000021', 'Inga edulis', 'nitrogen_fixer', '2025-11-01', 500.00, 50, 'Fast-growing nitrogen-fixing shade tree', 45, '2026-02-01', 'Support species for multi-strata corridor', 'published', 'pilot_seed', 'adelphi-underplant-inga-2025-11'),
('a0000000-0000-0000-0000-000000000812', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000700', 'a0000000-0000-0000-0000-000000000020', 'Mucuna pruriens', 'living_cover', '2025-10-20', 3000.00, 600, 'Living cover crop, erosion control, biomass', 540, '2026-01-20', 'Cover crop in syntropic bed pathways', 'published', 'pilot_seed', 'adelphi-underplant-mucuna-2025-10'),
('a0000000-0000-0000-0000-000000000813', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000021', 'Helianthus annuus', 'pollinator', '2025-12-01', 300.00, 200, 'Attract pollinators for passion fruit', 180, '2026-02-01', 'Sunflower border for pollinator habitat', 'published', 'pilot_seed', 'adelphi-underplant-sunflower-2025-12')
ON CONFLICT (id) DO UPDATE SET
    species_name = EXCLUDED.species_name,
    survival_count = EXCLUDED.survival_count,
    survival_survey_date = EXCLUDED.survival_survey_date,
    status = EXCLUDED.status,
    updated_at = NOW();

-- GHG emissions inventory (Adelphi transport, machinery, inputs)
INSERT INTO ghg_emissions_inventory (id, location_id, reporting_date, reporting_period, category, activity_description, quantity, quantity_unit, emission_factor_id, co2e_kg, co2e_tonnes, notes, status, source_system, source_id) VALUES
-- Transport: farm-to-market diesel truck
('a0000000-0000-0000-0000-000000000820', 'a0000000-0000-0000-0000-000000000001', '2026-01-15', 'monthly', 'transport', 'Monthly produce delivery to Sabana Grande market', 120.00, 'km', (SELECT id FROM ghg_emission_factor WHERE factor_key = 'truck_transport_diesel'), 321.60, 0.3216, '120km round trip x 2 trips/month', 'published', 'pilot_seed', 'adelphi-transport-2026-01'),
('a0000000-0000-0000-0000-000000000821', 'a0000000-0000-0000-0000-000000000001', '2026-02-15', 'monthly', 'transport', 'Monthly produce delivery to Sabana Grande market', 120.00, 'km', (SELECT id FROM ghg_emission_factor WHERE factor_key = 'truck_transport_diesel'), 321.60, 0.3216, '120km round trip x 2 trips/month', 'published', 'pilot_seed', 'adelphi-transport-2026-02'),
-- Machinery: tractor for land prep
('a0000000-0000-0000-0000-000000000822', 'a0000000-0000-0000-0000-000000000001', '2025-11-15', 'quarterly', 'machinery', 'Tractor land prep for syntropic bed expansion', 8.00, 'hour', (SELECT id FROM ghg_emission_factor WHERE factor_key = 'tractor_diesel'), 21.44, 0.0214, '8 hours tractor time', 'published', 'pilot_seed', 'adelphi-machinery-2025-11'),
-- Inputs: compost application (low emission)
('a0000000-0000-0000-0000-000000000823', 'a0000000-0000-0000-0000-000000000001', '2025-10-20', 'quarterly', 'input', 'Compost application to syntropic beds', 500.00, 'kg', (SELECT id FROM ghg_emission_factor WHERE factor_key = 'compost_organic'), 25.00, 0.025, 'On-farm compost, minimal emissions', 'published', 'pilot_seed', 'adelphi-input-2025-10'),
-- Inputs: biofertilizer (on-farm, negligible)
('a0000000-0000-0000-0000-000000000824', 'a0000000-0000-0000-0000-000000000001', '2025-12-01', 'quarterly', 'input', 'Biofertilizer production and application', 200.00, 'kg', (SELECT id FROM ghg_emission_factor WHERE factor_key = 'biofertilizer'), 4.00, 0.004, 'On-farm biofactory compost tea', 'published', 'pilot_seed', 'adelphi-input-bio-2025-12')
ON CONFLICT (id) DO UPDATE SET
    category = EXCLUDED.category,
    quantity = EXCLUDED.quantity,
    co2e_kg = EXCLUDED.co2e_kg,
    co2e_tonnes = EXCLUDED.co2e_tonnes,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Framework phase (Adelphi current implementation phase)
INSERT INTO framework_phase (id, location_id, framework_key, phase, phase_start_date, phase_end_date, phase_status, owner_wallet, review_cadence, notes, metadata) VALUES
('a0000000-0000-0000-0000-000000000830', 'a0000000-0000-0000-0000-000000000001', 'kokonut_framework', 'baseline_establishment', '2025-10-01', '2026-03-31', 'completed', '0x0000000000000000000000000000000000000001', 'monthly', 'Baseline soil carbon, biodiversity, and tree inventory completed', '{"source":"pilot seed"}'::jsonb),
('a0000000-0000-0000-0000-000000000831', 'a0000000-0000-0000-0000-000000000001', 'kokonut_framework', 'monitoring', '2026-04-01', NULL, 'active', '0x0000000000000000000000000000000000000001', 'monthly', 'Ongoing monitoring of carbon, biodiversity, and regenerative practices', '{"source":"pilot seed"}'::jsonb),
('a0000000-0000-0000-0000-000000000832', 'a0000000-0000-0000-0000-000000000001', 'ebf', 'baseline_establishment', '2025-10-01', '2026-03-31', 'completed', '0x0000000000000000000000000000000000000001', 'quarterly', 'EBF environmental dimension baseline established', '{"source":"pilot seed"}'::jsonb),
('a0000000-0000-0000-0000-000000000833', 'a0000000-0000-0000-0000-000000000001', 'ebf', 'monitoring', '2026-04-01', NULL, 'active', '0x0000000000000000000000000000000000000001', 'quarterly', 'EBF environmental monitoring in progress', '{"source":"pilot seed"}'::jsonb),
('a0000000-0000-0000-0000-000000000834', 'a0000000-0000-0000-0000-000000000001', 'sdg', 'baseline_establishment', '2025-10-01', '2026-03-31', 'completed', '0x0000000000000000000000000000000000000001', 'quarterly', 'SDG evidence baseline for SDGs 1,2,5,8,13,15', '{"source":"pilot seed"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    phase = EXCLUDED.phase,
    phase_status = EXCLUDED.phase_status,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- Regenerative practice checklist (Adelphi initial assessment)
INSERT INTO regenerative_practice_checklist (id, location_id, assessment_date, principle_key, score, evidence_path, notes, assessed_by, status) VALUES
('a0000000-0000-0000-0000-000000000840', 'a0000000-0000-0000-0000-000000000001', '2026-03-01', 'soil_protection', 4, 'farm_practice_event:adelphi-practice-soil-protection-2025-10', 'Mulch, compost, and biochar applied; soil carbon increased 3.4 t/ha. Room for deeper cover crop integration.', NULL, 'published'),
('a0000000-0000-0000-0000-000000000841', 'a0000000-0000-0000-0000-000000000001', '2026-03-01', 'living_cover', 4, 'farm_practice_event:adelphi-practice-living-cover-2025-10', 'Living cover established on syntropic beds; Mucuna and Canavalia providing ground cover. Some bare patches remain.', NULL, 'published'),
('a0000000-0000-0000-0000-000000000842', 'a0000000-0000-0000-0000-000000000001', '2026-03-01', 'biodiversity', 5, 'farm_practice_event:adelphi-practice-biodiversity-2025-11', 'Multi-strata corridor with 85 coconut, 120 passion fruit, Inga, Canavalia. Shannon index 1.12.', NULL, 'published'),
('a0000000-0000-0000-0000-000000000843', 'a0000000-0000-0000-0000-000000000001', '2026-03-01', 'animal_integration', 3, 'farm_practice_event:adelphi-practice-poultry-2026-01', 'Poultry loop established with 30 birds. Egg production contributing to food and fertility loop. Scale still small.', NULL, 'published'),
('a0000000-0000-0000-0000-000000000844', 'a0000000-0000-0000-0000-000000000001', '2026-03-01', 'organic_inputs', 5, 'farm_practice_event:adelphi-practice-bioinputs-2025-10', 'Biofactory producing compost tea and biofertilizer. Zero synthetic inputs. Full organic input cycle.', NULL, 'published')
ON CONFLICT (id) DO UPDATE SET
    score = EXCLUDED.score,
    notes = EXCLUDED.notes,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Climate-impact summary (2025 baseline year)
INSERT INTO climate_impact_summary (id, location_id, reporting_year, above_ground_carbon_tonnes, below_ground_carbon_tonnes, total_sequestration_tonnes_co2e, transport_emissions_tonnes_co2e, machinery_emissions_tonnes_co2e, input_emissions_tonnes_co2e, total_emissions_tonnes_co2e, net_climate_impact_tonnes_co2e, species_count, shannon_index, regenerative_score_total, methodology_version, data_quality_score, status, notes, source_system, source_id) VALUES
('a0000000-0000-0000-0000-000000000850', 'a0000000-0000-0000-0000-000000000001', 2025, 12.38, 3.40, 57.53, 0.64, 0.02, 0.03, 0.69, 56.84, 37, 1.12, 21, 'v1.0', 78.0, 'published', '2025 baseline year: establishment of syntropic beds, tree planting, and first soil carbon measurements', 'pilot_seed', 'adelphi-climate-summary-2025')
ON CONFLICT (id) DO UPDATE SET
    above_ground_carbon_tonnes = EXCLUDED.above_ground_carbon_tonnes,
    below_ground_carbon_tonnes = EXCLUDED.below_ground_carbon_tonnes,
    total_sequestration_tonnes_co2e = EXCLUDED.total_sequestration_tonnes_co2e,
    net_climate_impact_tonnes_co2e = EXCLUDED.net_climate_impact_tonnes_co2e,
    status = EXCLUDED.status,
    updated_at = NOW();
