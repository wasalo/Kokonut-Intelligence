-- ============================================================
-- 057_tree_tracking.sql — Seeds: metric, Adelphi pilot data
-- ============================================================

-- New metric definition
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('tree_density_per_ha', 'Tree Density per Hectare', 'Count of live individual trees per hectare of cultivated area.', 'count(tree_record where status = alive) / plot.area_ha', ARRAY['tree_record', 'plot'], 'Use tree_record with status = alive, linked to active plots.', 'Exclude dead, removal, or surviving trees. Exclude plots without area_ha.', 'trees_per_hectare', 'numeric', 'Ecology Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['tree_tracking', 'silvi_integration', 'biodiversity'], 'Supersede through metric_version before changing public interpretation.')
ON CONFLICT (metric_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    inclusion_rules = EXCLUDED.inclusion_rules,
    exclusion_rules = EXCLUDED.exclusion_rules,
    unit = EXCLUDED.unit,
    data_type = EXCLUDED.data_type,
    owner = EXCLUDED.owner,
    update_frequency = EXCLUDED.update_frequency,
    active = EXCLUDED.active,
    validation_tests = EXCLUDED.validation_tests,
    report_usage = EXCLUDED.report_usage,
    deprecation_policy = EXCLUDED.deprecation_policy;

-- ============================================================================
-- Adelphi pilot: 20 individual tree records with GPS coordinates
-- ============================================================================

-- Coconut palms in the Agroforestry Corridor (plot a0000000-0000-0000-0000-000000000021)
-- GPS coordinates approximated around Adelphi farm in Dominican Republic
INSERT INTO tree_record (
    id, location_id, plot_id, zone_id, tree_inventory_id,
    species_name, species_common_name, tree_tag,
    latitude, longitude,
    planting_date, height_m, dbh_cm, canopy_diameter_m,
    health_score, maturity_stage, status, last_survey_date,
    source_system, source_id, source_raw
) VALUES
-- Coconut palms (15 trees)
('a0000000-0000-0000-0000-000000005701', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-001', 18.5210000, -69.9870000, '2020-03-15', 12.5, 35.2, 8.0, 92.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac001', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005702', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-002', 18.5210200, -69.9870100, '2020-03-15', 11.8, 33.5, 7.5, 88.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac002', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005703', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-003', 18.5210400, -69.9870200, '2020-03-15', 13.1, 36.8, 8.5, 95.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac003', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005704', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-004', 18.5210600, -69.9870300, '2020-03-15', 10.9, 31.2, 7.0, 85.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac004', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005705', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-005', 18.5210800, -69.9870400, '2020-03-15', 12.2, 34.0, 7.8, 90.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac005', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005706', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-006', 18.5211000, -69.9870500, '2020-03-15', 12.8, 35.5, 8.2, 91.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac006', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005707', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-007', 18.5211200, -69.9870600, '2020-03-15', 11.5, 32.8, 7.2, 87.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac007', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005708', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-008', 18.5211400, -69.9870700, '2021-06-10', 8.5, 24.0, 5.5, 78.0, 'juvenile', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac008', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005709', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-009', 18.5211600, -69.9870800, '2021-06-10', 7.2, 20.5, 4.8, 72.0, 'juvenile', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac009', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005710', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-010', 18.5211800, -69.9870900, '2021-06-10', 8.0, 22.0, 5.2, 80.0, 'juvenile', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac010', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005711', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-011', 18.5212000, -69.9871000, '2022-01-15', 5.5, 16.0, 3.8, 65.0, 'juvenile', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac011', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005712', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-012', 18.5212200, -69.9871100, '2022-01-15', 4.8, 14.0, 3.2, 58.0, 'seedling', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac012', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005713', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-013', 18.5212400, -69.9871200, '2022-01-15', 5.2, 15.5, 3.5, 62.0, 'seedling', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac013', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005714', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-014', 18.5212600, -69.9871300, '2023-03-20', 3.2, 10.0, 2.0, 45.0, 'seedling', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac014', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005715', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000080',
 'Cocos nucifera', 'Coconut Palm', 'AC-015', 18.5212800, -69.9871400, '2023-03-20', 2.8, 8.5, 1.5, 40.0, 'seedling', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac015', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),

-- Passion fruit vines in Syntropic Beds (plot a0000000-0000-0000-0000-000000000020)
('a0000000-0000-0000-0000-000000005716', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000700', NULL,
 'Passiflora edulis', 'Passion Fruit', 'SB-001', 18.5209000, -69.9869000, '2024-02-10', 3.0, 5.0, 2.5, 85.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-sb001', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005717', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000700', NULL,
 'Passiflora edulis', 'Passion Fruit', 'SB-002', 18.5209200, -69.9869100, '2024-02-10', 2.8, 4.5, 2.2, 78.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-sb002', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005718', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000700', NULL,
 'Passiflora edulis', 'Passion Fruit', 'SB-003', 18.5209400, -69.9869200, '2024-02-10', 3.2, 5.2, 2.8, 88.0, 'mature', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-sb003', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),

-- Inga edulis (nitrogen fixer) in Agroforestry Corridor
('a0000000-0000-0000-0000-000000005719', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', NULL,
 'Inga edulis', 'Ice Cream Bean', 'AC-016', 18.5213000, -69.9871500, '2021-06-10', 6.5, 18.0, 4.5, 82.0, 'juvenile', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac016', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005720', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000701', NULL,
 'Inga edulis', 'Ice Cream Bean', 'AC-017', 18.5213200, -69.9871600, '2021-06-10', 7.0, 20.0, 5.0, 85.0, 'juvenile', 'alive', '2026-06-01', 'pilot_seed', 'adelphi-tree-ac017', '{"record_type":"tree_record","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    health_score = EXCLUDED.health_score,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- Tree measurements (3 quarterly surveys per coconut palm)
-- ============================================================================

INSERT INTO tree_measurement (
    id, tree_record_id, measurement_date,
    height_m, dbh_cm, canopy_diameter_m, health_score,
    source_system, source_id, source_raw
) VALUES
-- AC-001: 3 surveys showing growth
('a0000000-0000-0000-0000-000000005751', 'a0000000-0000-0000-0000-000000005701', '2026-01-15', 12.0, 34.5, 7.8, 90.0, 'pilot_seed', 'adelphi-meas-ac001-q1', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005752', 'a0000000-0000-0000-0000-000000005701', '2026-04-01', 12.3, 34.8, 7.9, 91.0, 'pilot_seed', 'adelphi-meas-ac001-q2', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005753', 'a0000000-0000-0000-0000-000000005701', '2026-06-01', 12.5, 35.2, 8.0, 92.0, 'pilot_seed', 'adelphi-meas-ac001-q3', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
-- AC-002: 3 surveys
('a0000000-0000-0000-0000-000000005754', 'a0000000-0000-0000-0000-000000005702', '2026-01-15', 11.3, 32.8, 7.2, 86.0, 'pilot_seed', 'adelphi-meas-ac002-q1', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005755', 'a0000000-0000-0000-0000-000000005702', '2026-04-01', 11.5, 33.2, 7.3, 87.0, 'pilot_seed', 'adelphi-meas-ac002-q2', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005756', 'a0000000-0000-0000-0000-000000005702', '2026-06-01', 11.8, 33.5, 7.5, 88.0, 'pilot_seed', 'adelphi-meas-ac002-q3', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
-- AC-003: 3 surveys
('a0000000-0000-0000-0000-000000005757', 'a0000000-0000-0000-0000-000000005703', '2026-01-15', 12.6, 36.0, 8.2, 93.0, 'pilot_seed', 'adelphi-meas-ac003-q1', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005758', 'a0000000-0000-0000-0000-000000005703', '2026-04-01', 12.9, 36.5, 8.4, 94.0, 'pilot_seed', 'adelphi-meas-ac003-q2', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005759', 'a0000000-0000-0000-0000-000000005703', '2026-06-01', 13.1, 36.8, 8.5, 95.0, 'pilot_seed', 'adelphi-meas-ac003-q3', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
-- AC-008: 3 surveys (juvenile, faster growth)
('a0000000-0000-0000-0000-000000005760', 'a0000000-0000-0000-0000-000000005708', '2026-01-15', 7.8, 23.0, 5.0, 75.0, 'pilot_seed', 'adelphi-meas-ac008-q1', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005761', 'a0000000-0000-0000-0000-000000005708', '2026-04-01', 8.2, 23.5, 5.3, 77.0, 'pilot_seed', 'adelphi-meas-ac008-q2', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005762', 'a0000000-0000-0000-0000-000000005708', '2026-06-01', 8.5, 24.0, 5.5, 78.0, 'pilot_seed', 'adelphi-meas-ac008-q3', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
-- AC-014: 3 surveys (seedling, fastest growth rate)
('a0000000-0000-0000-0000-000000005763', 'a0000000-0000-0000-0000-000000005714', '2026-01-15', 2.5, 8.5, 1.5, 40.0, 'pilot_seed', 'adelphi-meas-ac014-q1', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005764', 'a0000000-0000-0000-0000-000000005714', '2026-04-01', 2.8, 9.2, 1.8, 43.0, 'pilot_seed', 'adelphi-meas-ac014-q2', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005765', 'a0000000-0000-0000-0000-000000005714', '2026-06-01', 3.2, 10.0, 2.0, 45.0, 'pilot_seed', 'adelphi-meas-ac014-q3', '{"record_type":"tree_measurement","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    health_score = EXCLUDED.health_score,
    height_m = EXCLUDED.height_m;
