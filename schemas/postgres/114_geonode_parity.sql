-- GeoNode Parity: ISO 19115 metadata fields, thesaurus support, file CRS

-- ============================================================
-- ISO 19115 metadata fields on app_project_metadata
-- ============================================================
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS date_created DATE;
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS date_modified DATE;
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS topic_category VARCHAR(100);
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS spatial_resolution VARCHAR(100);
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS vertical_reference_system VARCHAR(100);
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS lineage TEXT;
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS distribution_format TEXT[];
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS reference_system VARCHAR(100) DEFAULT 'EPSG:4326';
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS purpose TEXT;
ALTER TABLE app_project_metadata ADD COLUMN IF NOT EXISTS credit TEXT;

-- ============================================================
-- Data stream file: CRS and enhanced metadata
-- ============================================================
ALTER TABLE data_stream_file ADD COLUMN IF NOT EXISTS crs VARCHAR(50) DEFAULT 'EPSG:4326';
ALTER TABLE data_stream_file ADD COLUMN IF NOT EXISTS file_hash VARCHAR(128);

-- ============================================================
-- Thesaurus: controlled vocabularies with hierarchical relationships
-- ============================================================
CREATE TABLE IF NOT EXISTS thesaurus (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identifier VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    date_updated DATE,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_th_identifier ON thesaurus(identifier);

CREATE TABLE IF NOT EXISTS thesaurus_keyword (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesaurus_id UUID NOT NULL REFERENCES thesaurus(id) ON DELETE CASCADE,
    keyword_about VARCHAR(255) NOT NULL,
    alt_label VARCHAR(255),
    parent_keyword_id UUID REFERENCES thesaurus_keyword(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tk_thesaurus ON thesaurus_keyword(thesaurus_id);
CREATE INDEX idx_tk_parent ON thesaurus_keyword(parent_keyword_id);
CREATE INDEX idx_tk_about ON thesaurus_keyword(keyword_about);

CREATE TABLE IF NOT EXISTS thesaurus_keyword_label (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    keyword_id UUID NOT NULL REFERENCES thesaurus_keyword(id) ON DELETE CASCADE,
    label VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(keyword_id, language)
);

CREATE INDEX idx_tkl_keyword ON thesaurus_keyword_label(keyword_id);
CREATE INDEX idx_tkl_language ON thesaurus_keyword_label(language);

-- Seed default thesauri
INSERT INTO thesaurus (identifier, title, description, language) VALUES
('activity_type', 'Activity Type', 'Controlled vocabulary for agricultural and land management activities', 'en'),
('environment_type', 'Environment Type', 'Controlled vocabulary for ecosystem and environment types', 'en'),
('impact_type', 'Impact Type', 'Controlled vocabulary for ecological and social impact types', 'en'),
('data_stream_post_type', 'Data Stream Post Type', 'Controlled vocabulary for data stream post types', 'en')
ON CONFLICT (identifier) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description;
