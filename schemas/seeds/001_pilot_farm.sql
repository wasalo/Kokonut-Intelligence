-- ============================================================
-- Pilot Farm Seed Data: Master Data
-- Kokonut Adelphi — Sabana Grande de Boya, Dominican Republic
-- ============================================================

-- Location
INSERT INTO location (id, name, slug, description, country, region, sub_region, timezone, latitude, longitude, baseline_revenue, baseline_asset_value, baseline_cash_flow, baseline_cost, status) VALUES
('a0000000-0000-0000-0000-000000000001', 'Kokonut Adelphi', 'kokonut-adelphi', 'First live Kokonut syntropic farm proof in Sabana Grande de Boya, Monte Plata, Dominican Republic', 'Dominican Republic', 'Monte Plata', 'Sabana Grande de Boya', 'America/Santo_Domingo', NULL, NULL, 15000.00, 25000.00, 8000.00, 12000.00, 'active')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    description = EXCLUDED.description,
    country = EXCLUDED.country,
    region = EXCLUDED.region,
    sub_region = EXCLUDED.sub_region,
    timezone = EXCLUDED.timezone,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    baseline_revenue = EXCLUDED.baseline_revenue,
    baseline_asset_value = EXCLUDED.baseline_asset_value,
    baseline_cash_flow = EXCLUDED.baseline_cash_flow,
    baseline_cost = EXCLUDED.baseline_cost,
    status = EXCLUDED.status,
    metadata = jsonb_build_object(
        'source', 'kokonut knowledge base',
        'hub_url', 'https://hub.kokonut.network/projects/41',
        'proof_stage', 'first_live_syntropic_farm',
        'women_led', true,
        'public_goods_allocation_pct', 10
    ),
    updated_at = NOW();

UPDATE location
SET baseline_revenue = 15000.00,
    baseline_asset_value = 25000.00,
    baseline_cash_flow = 8000.00,
    baseline_cost = 12000.00,
    schema_version = COALESCE(schema_version, 'common-data-schema-v1'),
    baseline_source = COALESCE(baseline_source, 'pilot_seed'),
    baseline_date = COALESCE(baseline_date, '2025-09-01')
WHERE id = 'a0000000-0000-0000-0000-000000000001';

-- Property
INSERT INTO property (id, location_id, name, slug, property_type, area, area_unit, description, status) VALUES
('a0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'Kokonut Adelphi Property', 'kokonut-adelphi-property', 'communal', 1.5725, 'hectares', 'Main property boundary for Kokonut Adelphi: 15,725 m2 total area with 13,838 m2 agricultural land', 'active')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    property_type = EXCLUDED.property_type,
    area = EXCLUDED.area,
    area_unit = EXCLUDED.area_unit,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Farm
INSERT INTO farm (id, location_id, property_id, name, slug, farm_type, total_area, area_unit, status) VALUES
('a0000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000005', 'Kokonut Adelphi', 'kokonut-adelphi-farm', 'syntropic', 1.5725, 'hectares', 'active')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    farm_type = EXCLUDED.farm_type,
    total_area = EXCLUDED.total_area,
    area_unit = EXCLUDED.area_unit,
    status = EXCLUDED.status,
    metadata = jsonb_build_object('agricultural_land_m2', 13838, 'total_area_m2', 15725),
    updated_at = NOW();

-- Plots (NO location_id — schema: plot has farm_id but no location_id)
INSERT INTO plot (id, farm_id, name, slug, area, area_unit, soil_type, water_source, status) VALUES
('a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000010', 'Syntropic Beds', 'syntropic-beds', 0.7838, 'hectares', 'tropical clay loam', 'rainfed and drip irrigation', 'active'),
('a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000010', 'Agroforestry Corridor', 'agroforestry-corridor', 0.4500, 'hectares', 'tropical clay loam', 'rainfed', 'active'),
('a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000010', 'Nursery Biofactory Poultry Loop', 'nursery-biofactory-poultry-loop', 0.1500, 'hectares', 'amended nursery substrate', 'stored rainwater', 'active')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    area = EXCLUDED.area,
    area_unit = EXCLUDED.area_unit,
    soil_type = EXCLUDED.soil_type,
    water_source = EXCLUDED.water_source,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Crops (NO slug, NO status — schema: name, scientific_name, variety, crop_category, growing_season_days, expected_yield_per_ha, expected_yield_unit, water_needs, climate_zone)
INSERT INTO crop (id, name, crop_category, growing_season_days, expected_yield_per_ha, expected_yield_unit, water_needs, climate_zone) VALUES
('a0000000-0000-0000-0000-000000000030', 'Lettuce', 'vegetable', 45, 15000.00, 'kg/hectare', 'moderate', 'tropical'),
('a0000000-0000-0000-0000-000000000031', 'Passion Fruit', 'fruit', 365, 12000.00, 'kg/hectare', 'moderate', 'tropical'),
('a0000000-0000-0000-0000-000000000032', 'Coconut', 'tree', 1825, 80.00, 'nuts/palm/year', 'moderate', 'tropical'),
('a0000000-0000-0000-0000-000000000033', 'Indian Yam', 'root', 270, 10000.00, 'kg/hectare', 'moderate', 'tropical'),
('a0000000-0000-0000-0000-000000000034', 'Eggs', 'other', 1, 0.00, 'eggs/day', 'low', 'tropical')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    crop_category = EXCLUDED.crop_category,
    growing_season_days = EXCLUDED.growing_season_days,
    expected_yield_per_ha = EXCLUDED.expected_yield_per_ha,
    expected_yield_unit = EXCLUDED.expected_yield_unit,
    water_needs = EXCLUDED.water_needs,
    climate_zone = EXCLUDED.climate_zone;

-- Crop Cycles (NO cycle_number — schema: cycle_name, season, location_id required)
INSERT INTO crop_cycle (id, plot_id, crop_id, location_id, cycle_name, season, planting_date, expected_harvest_date, actual_harvest_date, expected_yield, expected_yield_unit, actual_yield, actual_yield_unit, area_planted, area_unit, status) VALUES
('a0000000-0000-0000-0000-000000000040', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000030', 'a0000000-0000-0000-0000-000000000001', 'Lettuce Cycle 1', 'dry_2025', '2025-10-01', '2025-11-15', '2025-11-12', 5.00, 'tonnes', 4.80, 'tonnes', 0.20, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000041', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000030', 'a0000000-0000-0000-0000-000000000001', 'Lettuce Cycle 2', 'dry_2026', '2026-01-05', '2026-02-20', '2026-02-18', 5.20, 'tonnes', 5.00, 'tonnes', 0.20, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000042', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000031', 'a0000000-0000-0000-0000-000000000001', 'Passion Fruit Establishment', 'perennial_2025_2026', '2025-10-05', '2026-03-15', '2026-03-15', 3.00, 'tonnes', 2.40, 'tonnes', 0.30, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000043', 'a0000000-0000-0000-0000-000000000021', 'a0000000-0000-0000-0000-000000000032', 'a0000000-0000-0000-0000-000000000001', 'Coconut Establishment', 'perennial_2025_2026', '2025-10-10', '2026-03-15', '2026-03-15', 0.50, 'tonnes', 0.42, 'tonnes', 0.15, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000044', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000033', 'a0000000-0000-0000-0000-000000000001', 'Indian Yam Cycle 1', 'wet_2025_2026', '2025-11-01', '2026-02-28', '2026-02-15', 4.00, 'tonnes', 3.70, 'tonnes', 0.25, 'hectares', 'completed'),
('a0000000-0000-0000-0000-000000000045', 'a0000000-0000-0000-0000-000000000022', 'a0000000-0000-0000-0000-000000000034', 'a0000000-0000-0000-0000-000000000001', 'Egg Production Cycle 1', 'dry_2026', '2026-01-10', '2026-03-08', '2026-02-28', 1800.00, 'eggs', 1680.00, 'eggs', 0.05, 'hectares', 'completed')
ON CONFLICT (id) DO UPDATE SET
    plot_id = EXCLUDED.plot_id,
    crop_id = EXCLUDED.crop_id,
    cycle_name = EXCLUDED.cycle_name,
    season = EXCLUDED.season,
    planting_date = EXCLUDED.planting_date,
    expected_harvest_date = EXCLUDED.expected_harvest_date,
    actual_harvest_date = EXCLUDED.actual_harvest_date,
    expected_yield = EXCLUDED.expected_yield,
    expected_yield_unit = EXCLUDED.expected_yield_unit,
    actual_yield = EXCLUDED.actual_yield,
    actual_yield_unit = EXCLUDED.actual_yield_unit,
    area_planted = EXCLUDED.area_planted,
    area_unit = EXCLUDED.area_unit,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Partners (NO contact_name — schema: name, slug, partner_type, description, website, contact_email, contact_phone)
INSERT INTO partner (id, name, slug, partner_type, description, contact_email, status) VALUES
('a0000000-0000-0000-0000-000000000050', 'Dominican Produce Buyers Cooperative', 'dominican-produce-buyers', 'buyer', 'Regional produce buyer and distributor for Adelphi harvests', 'buyers@example.kokonut.network', 'active'),
('a0000000-0000-0000-0000-000000000051', 'Adelphi Bioinputs Network', 'adelphi-bioinputs-network', 'vendor', 'Local agricultural inputs, bioinputs, and equipment supplier', 'bioinputs@example.kokonut.network', 'active'),
('a0000000-0000-0000-0000-000000000052', 'Public Nouns', 'public-nouns', 'funder', 'Public goods funder connected to Nouns #69 funding context', 'public-goods@example.kokonut.network', 'active')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    partner_type = EXCLUDED.partner_type,
    description = EXCLUDED.description,
    contact_email = EXCLUDED.contact_email,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Staff (NO status — schema uses is_active BOOLEAN)
INSERT INTO staff (id, location_id, name, role, is_active) VALUES
('a0000000-0000-0000-0000-000000000060', 'a0000000-0000-0000-0000-000000000001', 'Adelphi Farm Lead', 'manager', TRUE),
('a0000000-0000-0000-0000-000000000061', 'a0000000-0000-0000-0000-000000000001', 'Community Operations Lead', 'supervisor', TRUE),
('a0000000-0000-0000-0000-000000000062', 'a0000000-0000-0000-0000-000000000001', 'Nursery Steward', 'field_worker', TRUE),
('a0000000-0000-0000-0000-000000000063', 'a0000000-0000-0000-0000-000000000001', 'MRV Field Coordinator', 'field_worker', TRUE)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- Infrastructure (NO installation_date — schema uses install_date, capacity is NUMERIC not VARCHAR)
INSERT INTO infrastructure_asset (id, location_id, asset_type, name, capacity, capacity_unit, install_date, status) VALUES
('a0000000-0000-0000-0000-000000000070', 'a0000000-0000-0000-0000-000000000001', 'biofactory', 'Adelphi Biofactory', 5000.00, 'liters/year', '2025-06-01', 'active'),
('a0000000-0000-0000-0000-000000000071', 'a0000000-0000-0000-0000-000000000001', 'nursery', 'Seedling Nursery', 10000.00, 'seedlings/year', '2025-03-01', 'active')
ON CONFLICT (id) DO UPDATE SET
    asset_type = EXCLUDED.asset_type,
    name = EXCLUDED.name,
    capacity = EXCLUDED.capacity,
    capacity_unit = EXCLUDED.capacity_unit,
    install_date = EXCLUDED.install_date,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Wallet Profiles (NO status — schema uses is_active BOOLEAN, add chain_id)
INSERT INTO wallet_profile (id, address, chain, chain_id, role, label, is_active) VALUES
('a0000000-0000-0000-0000-000000000080', '0xeb55b75328a8dffd45bbf34b7e7efc431a179085', 'gnosis', 100, 'treasury', 'Kokonut Treasury SAFE', TRUE),
('a0000000-0000-0000-0000-000000000081', '0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5', 'celo', 42220, 'attester_admin', 'Kokonut Multisig', TRUE)
ON CONFLICT (id) DO UPDATE SET
    address = EXCLUDED.address,
    chain = EXCLUDED.chain,
    chain_id = EXCLUDED.chain_id,
    role = EXCLUDED.role,
    label = EXCLUDED.label,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();
