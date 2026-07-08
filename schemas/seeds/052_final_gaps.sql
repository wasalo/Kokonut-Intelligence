-- ============================================================
-- 052_final_gaps.sql — Seeds: Q6 weather data, Q12 endangered species data
-- ============================================================

-- Q6: Adelphi pilot weather observations (monthly averages for correlation)
INSERT INTO weather_observation (
    id, location_id, observation_date, observation_time, source,
    temperature_c, humidity_pct, rainfall_mm, precipitation_mm
) VALUES
('a0000000-0000-0000-0000-000000005210',
 'a0000000-0000-0000-0000-000000000001',
 '2025-10-15', '12:00:00', 'manual',
 27.5, 72.0, 45.0, 45.0),
('a0000000-0000-0000-0000-000000005211',
 'a0000000-0000-0000-0000-000000000001',
 '2025-11-15', '12:00:00', 'manual',
 26.8, 68.0, 30.0, 30.0),
('a0000000-0000-0000-0000-000000005212',
 'a0000000-0000-0000-0000-000000000001',
 '2025-12-15', '12:00:00', 'manual',
 27.0, 65.0, 20.0, 20.0),
('a0000000-0000-0000-0000-000000005213',
 'a0000000-0000-0000-0000-000000000001',
 '2026-01-15', '12:00:00', 'manual',
 26.5, 70.0, 35.0, 35.0),
('a0000000-0000-0000-0000-000000005214',
 'a0000000-0000-0000-0000-000000000001',
 '2026-02-15', '12:00:00', 'manual',
 27.8, 75.0, 55.0, 55.0),
('a0000000-0000-0000-0000-000000005215',
 'a0000000-0000-0000-0000-000000000001',
 '2026-03-10', '12:00:00', 'manual',
 28.1, 68.0, 40.0, 40.0)
ON CONFLICT (id) DO UPDATE SET
    temperature_c = EXCLUDED.temperature_c,
    humidity_pct = EXCLUDED.humidity_pct,
    rainfall_mm = EXCLUDED.rainfall_mm;

-- Q12: Adelphi pilot endangered species reintroduction
INSERT INTO underplanting_event (
    id, location_id, zone_id, plot_id,
    species_name, species_role, planting_date,
    area_m2, plant_count, expected_benefit,
    survival_count, survival_survey_date,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005220',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'a0000000-0000-0000-0000-000000000015',
 'Inga edulis', 'nitrogen_fixer', '2025-10-01',
 2500.00, 50, 'N-fixation, shade, and biomass for syntropic system',
 42, '2026-03-10',
 'Inga edulis planted as support species for syntropic beds. 84% survival after 5 months.',
 'published', 'pilot_seed', 'adelphi-underplant-001',
 '{"record_type":"underplanting_event","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005221',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'a0000000-0000-0000-0000-000000000015',
 'Canavalia ensiformis', 'nitrogen_fixer', '2025-10-01',
 2500.00, 100, 'N-fixation, living cover, green manure',
 85, '2026-03-10',
 'Jack bean as ground-cover nitrogen fixer. 85% survival. High biomass production.',
 'published', 'pilot_seed', 'adelphi-underplant-002',
 '{"record_type":"underplanting_event","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005222',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000020',
 'a0000000-0000-0000-0000-000000000015',
 'Mucuna pruriens', 'living_cover', '2025-10-05',
 2500.00, 80, 'Living mulch, weed suppression, N-fixation',
 70, '2026-03-10',
 'Mucuna as living mulch between coconut rows. 87.5% survival.',
 'published', 'pilot_seed', 'adelphi-underplant-003',
 '{"record_type":"underplanting_event","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    species_name = EXCLUDED.species_name,
    plant_count = EXCLUDED.plant_count,
    survival_count = EXCLUDED.survival_count,
    updated_at = NOW();
