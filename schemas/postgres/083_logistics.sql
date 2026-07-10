-- ============================================================
-- 083_logistics.sql — Logistics & Cold Chain
-- ============================================================

-- 1. Storage facility
CREATE TABLE IF NOT EXISTS storage_facility (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    facility_name VARCHAR(255) NOT NULL,
    facility_type VARCHAR(100) NOT NULL,
    capacity_kg NUMERIC(12,2),
    capacity_unit VARCHAR(50) DEFAULT 'kg',
    temperature_min_c NUMERIC(5,2),
    temperature_max_c NUMERIC(5,2),
    humidity_min_pct NUMERIC(5,2),
    humidity_max_pct NUMERIC(5,2),
    temperature_controlled BOOLEAN DEFAULT FALSE,
    gps_latitude NUMERIC(10,7),
    gps_longitude NUMERIC(10,7),
    condition_status VARCHAR(50) DEFAULT 'good',
    last_inspection_date DATE,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_storage_location ON storage_facility(location_id);
CREATE INDEX IF NOT EXISTS idx_storage_type ON storage_facility(facility_type);

ALTER TABLE storage_facility DROP CONSTRAINT IF EXISTS chk_storage_type;
ALTER TABLE storage_facility ADD CONSTRAINT chk_storage_type CHECK (facility_type IN (
    'cold_room', 'dry_store', 'warehouse', 'pack_house', 'cold_chain_truck',
    'solar_dryer', 'fermentation_room', 'freezer', 'other'
));

ALTER TABLE storage_facility DROP CONSTRAINT IF EXISTS chk_storage_status;
ALTER TABLE storage_facility ADD CONSTRAINT chk_storage_status CHECK (status IN ('active', 'maintenance', 'inactive'));

-- 2. Shipment
CREATE TABLE IF NOT EXISTS shipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    origin_name VARCHAR(255) NOT NULL,
    origin_latitude NUMERIC(10,7),
    origin_longitude NUMERIC(10,7),
    destination_name VARCHAR(255) NOT NULL,
    destination_latitude NUMERIC(10,7),
    destination_longitude NUMERIC(10,7),
    carrier_name VARCHAR(255),
    vehicle_type VARCHAR(100),
    vehicle_id VARCHAR(100),
    departure_time TIMESTAMPTZ,
    estimated_arrival TIMESTAMPTZ,
    actual_arrival TIMESTAMPTZ,
    distance_km NUMERIC(10,2),
    estimated_duration_hours NUMERIC(8,2),
    actual_duration_hours NUMERIC(8,2),
    temperature_controlled BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'prepared',
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_shipment_location ON shipment(location_id);
CREATE INDEX IF NOT EXISTS idx_shipment_status ON shipment(status);
CREATE INDEX IF NOT EXISTS idx_shipment_dates ON shipment(departure_time, actual_arrival);

ALTER TABLE shipment DROP CONSTRAINT IF EXISTS chk_shipment_status;
ALTER TABLE shipment ADD CONSTRAINT chk_shipment_status CHECK (status IN (
    'prepared', 'in_transit', 'delivered', 'verified', 'cancelled'
));

-- 3. Shipment item
CREATE TABLE IF NOT EXISTS shipment_item (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shipment_id UUID NOT NULL REFERENCES shipment(id) ON DELETE CASCADE,
    harvest_event_id UUID REFERENCES harvest_event(id) ON DELETE SET NULL,
    purchase_order_item_id UUID REFERENCES purchase_order_item(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    quality_grade VARCHAR(50),
    quality_at_departure VARCHAR(50),
    quality_at_arrival VARCHAR(50),
    temperature_at_departure_c NUMERIC(5,2),
    temperature_at_arrival_c NUMERIC(5,2),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shipment_item_shipment ON shipment_item(shipment_id);
CREATE INDEX IF NOT EXISTS idx_shipment_item_harvest ON shipment_item(harvest_event_id);

-- 4. Cold chain record (temperature time-series)
CREATE TABLE IF NOT EXISTS cold_chain_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shipment_id UUID REFERENCES shipment(id) ON DELETE CASCADE,
    storage_facility_id UUID REFERENCES storage_facility(id) ON DELETE SET NULL,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    sensor_id UUID REFERENCES sensor_device(id) ON DELETE SET NULL,
    record_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    temperature_c NUMERIC(5,2) NOT NULL,
    humidity_pct NUMERIC(5,2),
    within_range BOOLEAN NOT NULL,
    min_range_c NUMERIC(5,2),
    max_range_c NUMERIC(5,2),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ccr_shipment ON cold_chain_record(shipment_id);
CREATE INDEX IF NOT EXISTS idx_ccr_storage ON cold_chain_record(storage_facility_id);
CREATE INDEX IF NOT EXISTS idx_ccr_location ON cold_chain_record(location_id);
CREATE INDEX IF NOT EXISTS idx_ccr_time ON cold_chain_record(record_time);
CREATE INDEX IF NOT EXISTS idx_ccr_sensor ON cold_chain_record(sensor_id);

-- 5. Transport log
CREATE TABLE IF NOT EXISTS transport_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shipment_id UUID NOT NULL REFERENCES shipment(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    origin_name VARCHAR(255) NOT NULL,
    destination_name VARCHAR(255) NOT NULL,
    distance_km NUMERIC(10,2),
    duration_hours NUMERIC(8,2),
    fuel_liters NUMERIC(8,2),
    fuel_cost NUMERIC(10,2),
    currency VARCHAR(10) DEFAULT 'USD',
    emissions_kg_co2e NUMERIC(10,4),
    route_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transport_shipment ON transport_log(shipment_id);
CREATE INDEX IF NOT EXISTS idx_transport_location ON transport_log(location_id);

-- 6. Public views
CREATE OR REPLACE VIEW v_public_shipment_summary AS
SELECT
    s.id AS shipment_id,
    s.origin_name,
    s.destination_name,
    s.carrier_name,
    s.departure_time,
    s.actual_arrival,
    s.distance_km,
    s.temperature_controlled,
    s.status,
    l.name AS location_name,
    (SELECT COUNT(*) FROM shipment_item si WHERE si.shipment_id = s.id) AS item_count,
    (SELECT SUM(si.quantity) FROM shipment_item si WHERE si.shipment_id = s.id) AS total_quantity
FROM shipment s
JOIN location l ON l.id = s.location_id
WHERE EXISTS (
    SELECT 1 FROM farm_registry_record fr
    WHERE fr.location_id = s.location_id
    AND fr.status IN ('verified', 'published')
);

CREATE OR REPLACE VIEW v_cold_chain_compliance AS
SELECT
    ccr.shipment_id,
    ccr.storage_facility_id,
    COUNT(*) AS total_readings,
    COUNT(*) FILTER (WHERE ccr.within_range = TRUE) AS compliant_readings,
    COUNT(*) FILTER (WHERE ccr.within_range = FALSE) AS out_of_range_readings,
    ROUND(COUNT(*) FILTER (WHERE ccr.within_range = TRUE)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) AS compliance_pct,
    AVG(ccr.temperature_c) AS avg_temperature,
    MIN(ccr.temperature_c) AS min_temperature,
    MAX(ccr.temperature_c) AS max_temperature
FROM cold_chain_record ccr
GROUP BY ccr.shipment_id, ccr.storage_facility_id;
