-- ============================================================
-- Pilot Farm Seed Data: Master Data
-- Kokonut Demo Farm — Kisumu, Kenya
-- ============================================================

-- Location
INSERT INTO location (id, name, slug, description, country, region, sub_region, timezone, latitude, longitude, baseline_revenue, baseline_asset_value, baseline_cash_flow, baseline_cost, status) VALUES
('a0000000-0000-0000-0000-000000000001', 'Kokonut Demo Farm — Kisumu', 'kokonut-demo-kisumu', 'Pilot farm in western Kenya for regenerative agriculture demonstration', 'Kenya', 'Nyanza', 'Kisumu County', 'Africa/Nairobi', -0.1000000, 34.7500000, 15000.00, 25000.00, 8000.00, 12000.00, 'active')
ON CONFLICT (id) DO NOTHING;

-- Property
INSERT INTO property (id, location_id, name, slug, property_type, area, area_unit, description, status) VALUES
('a0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'Kokonut Demo Property', 'kokonut-demo-property', 'titled', 15.00, 'hectares', 'Main property boundary for the Kisumu demo farm', 'active')
ON CONFLICT (id) DO NOTHING;

-- Farm
INSERT INTO farm (id, location_id, property_id, name, slug, farm_type, total_area, area_unit, status) VALUES
('a0000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000005', 'Main Farm', 'main-farm', 'organically_managed', 12.00, 'hectares', 'active')
ON CONFLICT (id) DO NOTHING;

-- Plots (NO location_id — schema: plot has farm_id but no location_id)
INSERT INTO plot (id, farm_id, name, area, area_unit, soil_type, water_source, status) VALUES
('a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000010', 'Plot A', 4.00, 'hectares', 'loam', 'river', 'active'),
('a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000010', 'Plot B', 3.00, 'hectares', 'clay', 'borehole', 'active'),
('a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000010', 'Plot C', 5.00, 'hectares', 'loam', 'rainfed', 'active')
ON CONFLICT (id) DO NOTHING;

-- Crops (NO slug, NO status — schema: name, scientific_name, variety, crop_category, growing_season_days, expected_yield_per_ha, expected_yield_unit, water_needs, climate_zone)
INSERT INTO crop (id, name, crop_category, growing_season_days, expected_yield_per_ha, expected_yield_unit, water_needs, climate_zone) VALUES
('a0000000-0000-0000-0000-000000000030', 'Maize', 'cereal', 90, 2.50, 'tonnes/hectare', 'moderate', 'tropical'),
('a0000000-0000-0000-0000-000000000031', 'Cassava', 'root', 180, 8.00, 'tonnes/hectare', 'low', 'tropical'),
('a0000000-0000-0000-0000-000000000032', 'Beans', 'legume', 60, 1.20, 'tonnes/hectare', 'moderate', 'tropical'),
('a0000000-0000-0000-0000-000000000033', 'Sweet Potato', 'root', 120, 5.00, 'tonnes/hectare', 'moderate', 'tropical')
ON CONFLICT (id) DO NOTHING;

-- Crop Cycles (NO cycle_number — schema: cycle_name, season, location_id required)
INSERT INTO crop_cycle (id, plot_id, crop_id, location_id, cycle_name, season, planting_date, expected_harvest_date, actual_harvest_date, expected_yield, expected_yield_unit, actual_yield, actual_yield_unit, area_planted, area_unit, status) VALUES
('a0000000-0000-0000-0000-000000000040', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000030', 'a0000000-0000-0000-0000-000000000001', 'Maize Cycle 1', 'Oct-Dec 2025', '2025-10-01', '2025-12-28', '2025-12-20', 10.00, 'tonnes', 34.96, 'tonnes', 4.00, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000041', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000030', 'a0000000-0000-0000-0000-000000000001', 'Maize Cycle 2', 'Jan-Mar 2026', '2026-01-05', '2026-03-30', '2026-03-20', 10.00, 'tonnes', 31.68, 'tonnes', 4.00, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000042', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000031', 'a0000000-0000-0000-0000-000000000001', 'Cassava Cycle 1', 'Oct 2025-Mar 2026', '2025-10-05', '2026-03-15', '2026-03-15', 24.00, 'tonnes', 21.38, 'tonnes', 3.00, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000043', 'a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000032', 'a0000000-0000-0000-0000-000000000001', 'Beans Cycle 1', 'Oct-Dec 2025', '2025-10-10', '2025-12-08', '2025-11-20', 2.40, 'tonnes', 2.21, 'tonnes', 2.00, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000044', 'a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000033', 'a0000000-0000-0000-0000-000000000001', 'Sweet Potato Cycle 1', 'Nov 2025-Feb 2026', '2025-11-01', '2026-02-28', '2026-02-15', 10.00, 'tonnes', 9.40, 'tonnes', 2.00, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000045', 'a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000032', 'a0000000-0000-0000-0000-000000000001', 'Beans Cycle 2', 'Jan-Mar 2026', '2026-01-10', '2026-03-08', '2026-02-28', 2.40, 'tonnes', 1.98, 'tonnes', 2.00, 'hectares', 'completed')
ON CONFLICT (id) DO NOTHING;

-- Partners (NO contact_name — schema: name, slug, partner_type, description, website, contact_email, contact_phone)
INSERT INTO partner (id, name, slug, partner_type, description, contact_email, status) VALUES
('a0000000-0000-0000-0000-000000000050', 'Nairobi Markets Ltd', 'nairobi-markets', 'buyer', 'Regional produce buyer and distributor', 'james@nairobimarkets.co.ke', 'active'),
('a0000000-0000-0000-0000-000000000051', 'AgroSupplies Kenya', 'agrosupplies-kenya', 'vendor', 'Agricultural inputs and equipment supplier', 'mary@agrosupplies.co.ke', 'active'),
('a0000000-0000-0000-0000-000000000052', 'Green Bonds DAO', 'green-bonds-dao', 'funder', 'Regenerative agriculture funding DAO', 'governance@greenbonds.xyz', 'active')
ON CONFLICT (id) DO NOTHING;

-- Staff (NO status — schema uses is_active BOOLEAN)
INSERT INTO staff (id, location_id, name, role, is_active) VALUES
('a0000000-0000-0000-0000-000000000060', 'a0000000-0000-0000-0000-000000000001', 'James Ochieng', 'manager', TRUE),
('a0000000-0000-0000-0000-000000000061', 'a0000000-0000-0000-0000-000000000001', 'Grace Wanjiku', 'supervisor', TRUE),
('a0000000-0000-0000-0000-000000000062', 'a0000000-0000-0000-0000-000000000001', 'Peter Akoth', 'field_worker', TRUE),
('a0000000-0000-0000-0000-000000000063', 'a0000000-0000-0000-0000-000000000001', 'Mary Anyango', 'field_worker', TRUE)
ON CONFLICT (id) DO NOTHING;

-- Infrastructure (NO installation_date — schema uses install_date, capacity is NUMERIC not VARCHAR)
INSERT INTO infrastructure_asset (id, location_id, asset_type, name, capacity, capacity_unit, install_date, status) VALUES
('a0000000-0000-0000-0000-000000000070', 'a0000000-0000-0000-0000-000000000001', 'pump', 'Solar Irrigation Pump', 5000.00, 'liters/hour', '2025-06-01', 'active'),
('a0000000-0000-0000-0000-000000000071', 'a0000000-0000-0000-0000-000000000001', 'storage', 'Storage Shed', 50.00, 'tonnes', '2025-03-01', 'active')
ON CONFLICT (id) DO NOTHING;

-- Wallet Profiles (NO status — schema uses is_active BOOLEAN, add chain_id)
INSERT INTO wallet_profile (id, address, chain, chain_id, role, label, is_active) VALUES
('a0000000-0000-0000-0000-000000000080', '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18', 'ethereum', 1, 'treasury', 'Kokonut Treasury', TRUE),
('a0000000-0000-0000-0000-000000000081', '0x1234567890abcdef1234567890abcdef12345678', 'optimism', 10, 'operations', 'Farm Operations', TRUE)
ON CONFLICT (address, chain) DO NOTHING;
