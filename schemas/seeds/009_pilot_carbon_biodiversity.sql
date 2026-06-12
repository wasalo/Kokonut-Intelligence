-- ============================================================
-- Pilot Farm Seed Data: Soil Carbon & Biodiversity
-- Kokonut Demo Farm — Kisumu, Kenya
-- ============================================================

-- Soil Carbon Measurements (baseline + follow-up per plot)
INSERT INTO soil_carbon_measurement (id, plot_id, location_id, measurement_date, carbon_pct, carbon_tonnes_per_ha, organic_carbon_stock, measurement_method, depth_cm, is_baseline, notes) VALUES
('a0000000-0000-0000-0000-000000000350', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', '2025-10-01', 1.80, 24.50, 24.50, 'lab_analysis', 30.0, TRUE, 'Baseline soil carbon for Plot A (maize)'),
('a0000000-0000-0000-0000-000000000351', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000001', '2026-03-15', 2.05, 27.90, 27.90, 'lab_analysis', 30.0, FALSE, 'Post-season soil carbon for Plot A — +3.4 t/ha gain'),
('a0000000-0000-0000-0000-000000000352', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000001', '2025-10-01', 1.60, 21.80, 21.80, 'lab_analysis', 30.0, TRUE, 'Baseline soil carbon for Plot B (cassava)'),
('a0000000-0000-0000-0000-000000000353', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000001', '2026-03-15', 1.82, 24.80, 24.80, 'lab_analysis', 30.0, FALSE, 'Post-season soil carbon for Plot B — +3.0 t/ha gain'),
('a0000000-0000-0000-0000-000000000354', 'a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000001', '2025-10-01', 2.10, 28.60, 28.60, 'lab_analysis', 30.0, TRUE, 'Baseline soil carbon for Plot C (beans + sweet potato)'),
('a0000000-0000-0000-0000-000000000355', 'a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000001', '2026-03-15', 2.35, 32.00, 32.00, 'lab_analysis', 30.0, FALSE, 'Post-season soil carbon for Plot C — +3.4 t/ha gain')
ON CONFLICT (id) DO NOTHING;

-- Species Observations (baseline + follow-up)
INSERT INTO species_observation (id, location_id, plot_id, observation_date, species_name, species_common_name, species_category, count, abundance, observer, method, habitat_type, notes) VALUES
-- Plot A baseline
('a0000000-0000-0000-0000-000000000360', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', '2025-10-10', 'Passer domesticus', 'House Sparrow', 'bird', 8, 'common', 'J. Mwangi', 'visual', 'crop_field', 'Baseline bird count in maize field'),
('a0000000-0000-0000-0000-000000000361', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', '2025-10-10', 'Apis mellifera', 'Honey Bee', 'insect', 15, 'frequent', 'J. Mwangi', 'visual', 'crop_field', 'Baseline pollinator count'),
('a0000000-0000-0000-0000-000000000362', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', '2025-10-10', 'Gallus gallus domesticus', 'Chicken', 'bird', 3, 'occasional', 'J. Mwangi', 'visual', 'crop_field', 'Free-range chickens in field'),
-- Plot A follow-up
('a0000000-0000-0000-0000-000000000363', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', '2026-03-10', 'Passer domesticus', 'House Sparrow', 'bird', 12, 'common', 'J. Mwangi', 'visual', 'crop_field', 'Post-season bird count — +50% increase'),
('a0000000-0000-0000-0000-000000000364', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', '2026-03-10', 'Apis mellifera', 'Honey Bee', 'insect', 22, 'common', 'J. Mwangi', 'visual', 'crop_field', 'Post-season pollinator count — +47% increase'),
('a0000000-0000-0000-0000-000000000365', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', '2026-03-10', 'Gallus gallus domesticus', 'Chicken', 'bird', 5, 'occasional', 'J. Mwangi', 'visual', 'crop_field', 'Post-season chicken count — +67% increase'),
-- Plot B baseline + follow-up
('a0000000-0000-0000-0000-000000000366', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', '2025-10-10', 'Turdoides striata', 'Jungle Babbler', 'bird', 6, 'frequent', 'J. Mwangi', 'visual', 'crop_field', 'Baseline — cassava field'),
('a0000000-0000-0000-0000-000000000367', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', '2026-03-10', 'Turdoides striata', 'Jungle Babbler', 'bird', 9, 'common', 'J. Mwangi', 'visual', 'crop_field', 'Post-season — +50% increase')
ON CONFLICT (id) DO NOTHING;

-- Environmental Baselines
INSERT INTO environmental_baseline (id, location_id, plot_id, metric_name, baseline_value, unit, measurement_date, measurement_method, source, notes) VALUES
('a0000000-0000-0000-0000-000000000370', 'a0000000-0000-0000-0000-000000000001', NULL, 'soil_carbon_tonnes_per_ha', 24.97, 'tonnes/ha', '2025-10-01', 'lab_analysis', 'soil_carbon_measurement', 'Average baseline soil carbon across all plots'),
('a0000000-0000-0000-0000-000000000371', 'a0000000-0000-0000-0000-000000000001', NULL, 'species_count', 29, 'count', '2025-10-10', 'visual_survey', 'species_observation', 'Total species observed across all plots at baseline'),
('a0000000-0000-0000-0000-000000000372', 'a0000000-0000-0000-0000-000000000001', NULL, 'ndvi_avg', 0.35, 'index', '2025-10-15', 'satellite', 'remote_sensing_observation', 'Average NDVI across all plots at baseline')
ON CONFLICT (id) DO NOTHING;
