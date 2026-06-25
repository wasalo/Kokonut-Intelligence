-- Water access data for pilot farm
-- Depends on: 001_pilot_farm.sql (location)
INSERT INTO water_access (id, location_id, source_type, source_name, capacity_liters, reliability_score, quality_score, distance_km, monthly_cost_usd, status, notes) VALUES
('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'borehole', 'Adelphi Farm Borehole', 50000.00, 85.00, 90.00, 0.50, 120.00, 'active', 'Primary water source for Adelphi operations'),
('e0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'rainwater_harvesting', 'Adelphi Roof Collection System', 10000.00, 60.00, 75.00, 0.10, 25.00, 'active', 'Collects from farm structures, seasonal reliability'),
('e0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'stored_water', 'Adelphi Backup Water Storage', 200000.00, 70.00, 65.00, 2.30, 45.00, 'active', 'Backup source, requires filtration before use')
ON CONFLICT (id) DO UPDATE SET
    source_type = EXCLUDED.source_type,
    source_name = EXCLUDED.source_name,
    capacity_liters = EXCLUDED.capacity_liters,
    reliability_score = EXCLUDED.reliability_score,
    quality_score = EXCLUDED.quality_score,
    distance_km = EXCLUDED.distance_km,
    monthly_cost_usd = EXCLUDED.monthly_cost_usd,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes,
    updated_at = NOW();
