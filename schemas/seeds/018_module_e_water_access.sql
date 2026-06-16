-- Water access data for pilot farm
-- Depends on: 001_pilot_farm.sql (location)
INSERT INTO water_access (id, location_id, source_type, source_name, capacity_liters, reliability_score, quality_score, distance_km, monthly_cost_usd, status, notes) VALUES
('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'borehole', 'Main Farm Borehole', 50000.00, 85.00, 90.00, 0.50, 120.00, 'active', 'Primary water source, solar-powered pump'),
('e0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'rainwater_harvesting', 'Roof Collection System', 10000.00, 60.00, 75.00, 0.10, 25.00, 'active', 'Collects from main barn roof, seasonal reliability'),
('e0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'river', 'Kisumu River Intake', 200000.00, 70.00, 65.00, 2.30, 45.00, 'active', 'Backup source, requires filtration before use')
ON CONFLICT (id) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    reliability_score = EXCLUDED.reliability_score,
    quality_score = EXCLUDED.quality_score,
    updated_at = NOW();
