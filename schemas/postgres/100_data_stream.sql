-- Data Stream: Chronological project data posts
-- Enables real-time data uploads, blockchain anchoring, and stakeholder collaboration

-- ============================================================
-- data_stream_post
-- ============================================================
CREATE TABLE data_stream_post (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Location anchor
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),

    -- Post identity
    post_type VARCHAR(50) NOT NULL DEFAULT 'field_update',
    title VARCHAR(255) NOT NULL,
    content TEXT,
    content_hash VARCHAR(128),
    content_search TSVECTOR,

    -- Evidence (URLs + Directus file attachments)
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    file_ids UUID[],
    media_type VARCHAR(50),

    -- Blockchain anchoring
    is_anchored BOOLEAN DEFAULT FALSE,
    attestation_uid VARCHAR(66),
    chain VARCHAR(50) DEFAULT 'celo',
    anchored_at TIMESTAMPTZ,

    -- Visibility
    visibility VARCHAR(20) DEFAULT 'internal',

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'draft',

    -- Source lineage
    schema_version VARCHAR(50) DEFAULT 'data-stream-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,

    CONSTRAINT chk_dsp_status CHECK (status IN ('draft','submitted','verified','published','rejected')),
    CONSTRAINT chk_dsp_type CHECK (post_type IN (
        'field_update','monitoring_report','photo','satellite_image',
        'sensor_reading','soil_analysis','water_analysis','biodiversity_survey',
        'harvest_report','weather_report','financial_report','community_update',
        'training_record','intervention_record','compliance_record'
    )),
    CONSTRAINT chk_dsp_visibility CHECK (visibility IN ('public','internal','private'))
);

CREATE INDEX idx_dsp_location ON data_stream_post(location_id);
CREATE INDEX idx_dsp_status ON data_stream_post(status);
CREATE INDEX idx_dsp_type ON data_stream_post(post_type);
CREATE INDEX idx_dsp_created ON data_stream_post(created_at DESC);
CREATE INDEX idx_dsp_visibility ON data_stream_post(visibility);
CREATE INDEX idx_dsp_search ON data_stream_post USING GIN(content_search);
CREATE INDEX idx_dsp_evidence_urls ON data_stream_post USING GIN(evidence_urls);
CREATE INDEX idx_dsp_file_ids ON data_stream_post USING GIN(file_ids);

-- Auto-update full-text search vector
CREATE OR REPLACE FUNCTION trg_dsp_search_update() RETURNS trigger AS $$
BEGIN
    NEW.content_search :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS dsp_search_update ON data_stream_post;
CREATE TRIGGER dsp_search_update
    BEFORE INSERT OR UPDATE OF title, content ON data_stream_post
    FOR EACH ROW EXECUTE FUNCTION trg_dsp_search_update();

-- ============================================================
-- data_stream_post_comment
-- ============================================================
CREATE TABLE data_stream_post_comment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES data_stream_post(id) ON DELETE CASCADE,
    author_id UUID,
    content TEXT NOT NULL,
    is_anchored BOOLEAN DEFAULT FALSE,
    attestation_uid VARCHAR(66),
    status VARCHAR(50) DEFAULT 'published',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_dspc_post ON data_stream_post_comment(post_id);
CREATE INDEX idx_dspc_status ON data_stream_post_comment(status);

-- ============================================================
-- v_project_data_stream (chronological feed for each project)
-- ============================================================
CREATE OR REPLACE VIEW v_project_data_stream AS
SELECT
    dsp.id,
    dsp.location_id,
    dsp.post_type,
    dsp.title,
    dsp.content,
    dsp.media_type,
    dsp.evidence_urls,
    dsp.file_ids,
    dsp.visibility,
    dsp.status,
    dsp.is_anchored,
    dsp.attestation_uid,
    dsp.chain,
    dsp.anchored_at,
    dsp.created_at,
    dsp.created_by,
    dsp.metadata,
    l.name AS location_name,
    fr.farm_name,
    (SELECT COUNT(*) FROM data_stream_post_comment dsc WHERE dsc.post_id = dsp.id) AS comment_count
FROM data_stream_post dsp
JOIN location l ON l.id = dsp.location_id
LEFT JOIN farm_registry_record fr ON fr.location_id = dsp.location_id AND fr.status IN ('verified', 'published')
WHERE l.status = 'active'
  AND dsp.status IN ('published', 'verified')
  AND dsp.visibility = 'public'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr2
      WHERE fr2.location_id = dsp.location_id
        AND fr2.status IN ('verified', 'published')
  )
ORDER BY dsp.created_at DESC;

-- ============================================================
-- v_data_stream_search (full-text search across posts)
-- ============================================================
CREATE OR REPLACE VIEW v_data_stream_search AS
SELECT
    dsp.id,
    dsp.location_id,
    dsp.post_type,
    dsp.title,
    dsp.content,
    dsp.visibility,
    dsp.status,
    dsp.created_at,
    l.name AS location_name,
    ts_rank(dsp.content_search, plainto_tsquery('english', COALESCE(dsp.title, '') || ' ' || COALESCE(dsp.content, ''))) AS search_rank
FROM data_stream_post dsp
JOIN location l ON l.id = dsp.location_id
WHERE dsp.status IN ('published', 'verified')
  AND dsp.content_search IS NOT NULL
  AND l.status = 'active';
