-- ============================================================
-- 048_economic_social_enhancement.sql — Training sessions and revenue streams
-- ============================================================

-- Training session: individual training participation tracking
CREATE TABLE IF NOT EXISTS training_session (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    participant_name VARCHAR(255) NOT NULL,
    participant_role VARCHAR(100),
    session_date DATE NOT NULL,
    session_topic VARCHAR(255) NOT NULL,
    session_type VARCHAR(100),
    duration_hours NUMERIC(6,2),
    pre_score NUMERIC(5,2),
    post_score NUMERIC(5,2),
    improvement_pct NUMERIC(5,2),
    trainer VARCHAR(255),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'economic-social-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_training_location ON training_session(location_id);
CREATE INDEX IF NOT EXISTS idx_training_date ON training_session(session_date);
CREATE INDEX IF NOT EXISTS idx_training_topic ON training_session(session_topic);
CREATE INDEX IF NOT EXISTS idx_training_participant ON training_session(participant_name);
CREATE INDEX IF NOT EXISTS idx_training_status ON training_session(status);

ALTER TABLE training_session DROP CONSTRAINT IF EXISTS chk_training_session_type;
ALTER TABLE training_session ADD CONSTRAINT chk_training_session_type CHECK (
    session_type IS NULL OR session_type IN (
        'soil_management', 'pest_management', 'harvesting', 'post_harvest',
        'financial_management', 'organic_inputs', 'water_management',
        'record_keeping', 'agroforestry', 'other'
    )
);

ALTER TABLE training_session DROP CONSTRAINT IF EXISTS chk_training_status;
ALTER TABLE training_session ADD CONSTRAINT chk_training_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Revenue stream contribution: tracks which revenue streams contribute to profitability
CREATE TABLE IF NOT EXISTS revenue_stream_contribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    stream_name VARCHAR(255) NOT NULL,
    stream_category VARCHAR(100),
    gross_revenue NUMERIC(15,2) NOT NULL,
    direct_costs NUMERIC(15,2),
    allocated_costs NUMERIC(15,2),
    net_contribution NUMERIC(15,2),
    contribution_pct NUMERIC(5,2),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'economic-social-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_revstream_location ON revenue_stream_contribution(location_id);
CREATE INDEX IF NOT EXISTS idx_revstream_crop_cycle ON revenue_stream_contribution(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_revstream_period ON revenue_stream_contribution(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_revstream_name ON revenue_stream_contribution(stream_name);
CREATE INDEX IF NOT EXISTS idx_revstream_status ON revenue_stream_contribution(status);

ALTER TABLE revenue_stream_contribution DROP CONSTRAINT IF EXISTS chk_revstream_category;
ALTER TABLE revenue_stream_contribution ADD CONSTRAINT chk_revstream_category CHECK (
    stream_category IS NULL OR stream_category IN (
        'fresh_produce', 'processed_goods', 'bio_input_sales', 'nursery_sales',
        'carbon_credits', 'biodiversity_credits', 'training_services',
        'agritourism', 'grants', 'other'
    )
);

ALTER TABLE revenue_stream_contribution DROP CONSTRAINT IF EXISTS chk_revstream_status;
ALTER TABLE revenue_stream_contribution ADD CONSTRAINT chk_revstream_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Public-safe views
CREATE OR REPLACE VIEW v_public_training_impact AS
SELECT
    ts.id,
    ts.location_id,
    l.name AS location_name,
    ts.participant_name,
    ts.participant_role,
    ts.session_date,
    ts.session_topic,
    ts.session_type,
    ts.duration_hours,
    ts.pre_score,
    ts.post_score,
    ts.improvement_pct,
    ts.trainer,
    ts.notes,
    ts.status
FROM training_session ts
JOIN location l ON l.id = ts.location_id
WHERE l.status = 'active'
  AND ts.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_revenue_streams AS
SELECT
    rsc.id,
    rsc.location_id,
    l.name AS location_name,
    rsc.crop_cycle_id,
    cc.cycle_name,
    rsc.period_start,
    rsc.period_end,
    rsc.stream_name,
    rsc.stream_category,
    rsc.gross_revenue,
    rsc.direct_costs,
    rsc.allocated_costs,
    rsc.net_contribution,
    rsc.contribution_pct,
    rsc.notes,
    rsc.status
FROM revenue_stream_contribution rsc
JOIN location l ON l.id = rsc.location_id
LEFT JOIN crop_cycle cc ON cc.id = rsc.crop_cycle_id
WHERE l.status = 'active'
  AND rsc.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('economic-social-v1', 'Training sessions, revenue stream contributions, and public views', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
