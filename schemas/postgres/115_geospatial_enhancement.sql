-- GeoNode Enhancements: Raster metadata, CSW, Geostories, Harvesting

-- ============================================================
-- Raster metadata for GeoTIFF/raster files
-- ============================================================
CREATE TABLE IF NOT EXISTS raster_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_url TEXT NOT NULL,
    file_name VARCHAR(255),
    file_format VARCHAR(50),
    crs VARCHAR(50) DEFAULT 'EPSG:4326',
    pixel_width NUMERIC(12,6),
    pixel_height NUMERIC(12,6),
    bbox_west NUMERIC(10,7),
    bbox_south NUMERIC(10,7),
    bbox_east NUMERIC(10,7),
    bbox_north NUMERIC(10,7),
    num_bands INTEGER,
    band_names TEXT[],
    file_size_bytes BIGINT,
    data_type VARCHAR(50),
    nodata_value NUMERIC(12,4),
    location_id UUID REFERENCES location(id),
    source_system VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rm_location ON raster_metadata(location_id);
CREATE INDEX idx_rm_format ON raster_metadata(file_format);

-- ============================================================
-- LinkML to Directus mapping
-- ============================================================
CREATE TABLE IF NOT EXISTS linkml_directus_mapping (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schema_name VARCHAR(100) NOT NULL,
    directus_collection VARCHAR(100) NOT NULL,
    field_mappings JSONB NOT NULL,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ldm_schema ON linkml_directus_mapping(schema_name);

-- ============================================================
-- Geostories (narrative spatial stories)
-- ============================================================
CREATE TABLE IF NOT EXISTS geostory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    author_id UUID,
    cover_image_url TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_geostory_status CHECK (status IN ('draft', 'published', 'archived'))
);

CREATE INDEX idx_gs_location ON geostory(location_id);
CREATE INDEX idx_gs_status ON geostory(status);

CREATE TABLE IF NOT EXISTS geostory_section (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    geostory_id UUID NOT NULL REFERENCES geostory(id) ON DELETE CASCADE,
    section_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    content TEXT,
    image_url TEXT,
    map_center_lat NUMERIC(10,7),
    map_center_lon NUMERIC(10,7),
    map_zoom INTEGER DEFAULT 10,
    map_layers TEXT[],
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_section_type CHECK (section_type IN (
        'text', 'image', 'map', 'video', 'divider', 'quote'
    ))
);

CREATE INDEX idx_gss_geostory ON geostory_section(geostory_id);
CREATE INDEX idx_gss_type ON geostory_section(section_type);

-- ============================================================
-- Harvest data ingestion log
-- ============================================================
CREATE TABLE IF NOT EXISTS harvest_ingestion_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    source_system VARCHAR(100) NOT NULL,
    source_url TEXT,
    source_format VARCHAR(50),
    records_ingested INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_hil_location ON harvest_ingestion_log(location_id);
CREATE INDEX idx_hil_status ON harvest_ingestion_log(status);
