-- ============================================================
-- 071_sample_plot_design.sql — Seeds: Adelphi pilot sample plots
-- ============================================================

-- Sample plot design for Adelphi Agroforestry Corridor
INSERT INTO sample_plot_design (
    id, location_id, zone_id, design_name,
    sampling_method, target_plot_count, target_plot_area_m2,
    min_distance_between_plots_m,
    zone_area_m2, zone_area_ha,
    confidence_level, generated_plot_count,
    status, source_system, source_id
) VALUES (
    'a0000000-0000-0000-0000-000000007101',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000701',
    'Agroforestry Corridor Stratified Random Design',
    'stratified_random',
    5, 100.0, 15.0,
    4500.0, 0.45,
    95.0, 5,
    'approved', 'pilot_seed', 'adelphi-plot-design-001'
) ON CONFLICT (id) DO UPDATE SET
    generated_plot_count = EXCLUDED.generated_plot_count,
    status = EXCLUDED.status;

-- Sample plots within Agroforestry Corridor
INSERT INTO sample_plot (
    id, design_id, zone_id, location_id,
    plot_number, plot_label,
    center_latitude, center_longitude,
    plot_area_m2, radius_m, stratum,
    source_system, source_id
) VALUES
('a0000000-0000-0000-0000-000000007111',
 'a0000000-0000-0000-0000-000000007101',
 'a0000000-0000-0000-0000-000000000701',
 'a0000000-0000-0000-0000-000000000001',
 1, 'SP-AC-001', 18.52118, -69.98718, 100.0, 5.64, 'mature_coconut',
 'pilot_seed', 'adelphi-sp-001'),
('a0000000-0000-0000-0000-000000007112',
 'a0000000-0000-0000-0000-000000007101',
 'a0000000-0000-0000-0000-000000000701',
 'a0000000-0000-0000-0000-000000000001',
 2, 'SP-AC-002', 18.52125, -69.98710, 100.0, 5.64, 'mature_coconut',
 'pilot_seed', 'adelphi-sp-002'),
('a0000000-0000-0000-0000-000000007113',
 'a0000000-0000-0000-0000-000000007101',
 'a0000000-0000-0000-0000-000000000701',
 'a0000000-0000-0000-0000-000000000001',
 3, 'SP-AC-003', 18.52132, -69.98722, 100.0, 5.64, 'juvenile_coconut',
 'pilot_seed', 'adelphi-sp-003'),
('a0000000-0000-0000-0000-000000007114',
 'a0000000-0000-0000-0000-000000007101',
 'a0000000-0000-0000-0000-000000000701',
 'a0000000-0000-0000-0000-000000000001',
 4, 'SP-AC-004', 18.52115, -69.98728, 100.0, 5.64, 'passion_fruit',
 'pilot_seed', 'adelphi-sp-004'),
('a0000000-0000-0000-0000-000000007115',
 'a0000000-0000-0000-0000-000000007101',
 'a0000000-0000-0000-0000-000000000701',
 'a0000000-0000-0000-0000-000000000001',
 5, 'SP-AC-005', 18.52128, -69.98705, 100.0, 5.64, 'nitrogen_fixer',
 'pilot_seed', 'adelphi-sp-005')
ON CONFLICT (id) DO UPDATE SET
    center_latitude = EXCLUDED.center_latitude,
    center_longitude = EXCLUDED.center_longitude;
