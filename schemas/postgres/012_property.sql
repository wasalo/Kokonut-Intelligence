-- ============================================================
-- 012_property.sql — Legal or managed property boundaries
-- ============================================================

CREATE TABLE IF NOT EXISTS property (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    property_type VARCHAR(100), -- titled, leased, communal, government_granted
    area NUMERIC(12,4),
    area_unit VARCHAR(20) DEFAULT 'hectares',
    legal_description TEXT,
    parcel_number VARCHAR(100),
    ownership_type VARCHAR(100),
    deed_or_title_url TEXT,
    zoning VARCHAR(100),
    boundary GEOMETRY(POLYGON, 4326),
    center GEOMETRY(POINT, 4326),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_property_location ON property(location_id);
CREATE INDEX IF NOT EXISTS idx_property_slug ON property(slug);
CREATE INDEX IF NOT EXISTS idx_property_boundary ON property USING GIST(boundary);
CREATE INDEX IF NOT EXISTS idx_property_center ON property USING GIST(center);

-- Add property_id FK to farm table
ALTER TABLE farm ADD COLUMN IF NOT EXISTS property_id UUID REFERENCES property(id);
CREATE INDEX IF NOT EXISTS idx_farm_property ON farm(property_id);
