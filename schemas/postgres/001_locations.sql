-- ============================================================
-- 001_locations.sql — Master and spatial data
-- ============================================================

-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_version (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(20) NOT NULL UNIQUE,
    description TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by VARCHAR(100),
    checksum VARCHAR(64)
);

-- Locations
CREATE TABLE IF NOT EXISTS location (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    boundary GEOMETRY(POLYGON, 4326),
    center GEOMETRY(POINT, 4326),
    country VARCHAR(100),
    region VARCHAR(255),
    sub_region VARCHAR(255),
    timezone VARCHAR(50),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    -- Baseline fields (PRD requirement)
    baseline_revenue NUMERIC(15,2),
    baseline_asset_value NUMERIC(15,2),
    baseline_cash_flow NUMERIC(15,2),
    baseline_assumptions JSONB DEFAULT '{}',
    baseline_source VARCHAR(255),
    baseline_date DATE,
    -- Metadata
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_location_slug ON location(slug);
CREATE INDEX IF NOT EXISTS idx_location_status ON location(status);
CREATE INDEX IF NOT EXISTS idx_location_boundary ON location USING GIST(boundary);
CREATE INDEX IF NOT EXISTS idx_location_center ON location USING GIST(center);

-- Farms
CREATE TABLE IF NOT EXISTS farm (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    farm_type VARCHAR(100), -- conventional, organic, syntropic, agroforestry, hybrid
    total_area NUMERIC(12,4),
    area_unit VARCHAR(20) DEFAULT 'hectares',
    boundary GEOMETRY(POLYGON, 4326),
    center GEOMETRY(POINT, 4326),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_farm_location ON farm(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_slug ON farm(slug);
CREATE INDEX IF NOT EXISTS idx_farm_boundary ON farm USING GIST(boundary);

-- Plots
CREATE TABLE IF NOT EXISTS plot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farm(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255),
    description TEXT,
    area NUMERIC(12,4),
    area_unit VARCHAR(20) DEFAULT 'hectares',
    boundary GEOMETRY(POLYGON, 4326),
    center GEOMETRY(POINT, 4326),
    soil_type VARCHAR(100),
    water_source VARCHAR(255),
    elevation_m NUMERIC(8,2),
    slope_pct NUMERIC(5,2),
    aspect VARCHAR(20),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_plot_farm ON plot(farm_id);
CREATE INDEX IF NOT EXISTS idx_plot_boundary ON plot USING GIST(boundary);

-- Partners
CREATE TABLE IF NOT EXISTS partner (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    partner_type VARCHAR(100), -- buyer, funder, vendor, verifier, technical, community
    description TEXT,
    website VARCHAR(500),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Infrastructure assets
CREATE TABLE IF NOT EXISTS infrastructure_asset (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(100) NOT NULL, -- tank, pump, reservoir, electrical, biofactory, greenhouse, nursery, solar, well
    description TEXT,
    install_date DATE,
    capacity NUMERIC(12,4),
    capacity_unit VARCHAR(50),
    condition_status VARCHAR(50), -- excellent, good, fair, poor, critical
    last_inspection_date DATE,
    replacement_cost NUMERIC(15,2),
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_infra_location ON infrastructure_asset(location_id);
CREATE INDEX IF NOT EXISTS idx_infra_type ON infrastructure_asset(asset_type);

-- Staff
CREATE TABLE IF NOT EXISTS staff (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100), -- manager, field_worker, finance, analyst, admin
    email VARCHAR(255),
    phone VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
