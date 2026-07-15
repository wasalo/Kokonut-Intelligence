-- Migration 197: Business Model Canvas + Value Proposition Canvas
-- Phase 7A of BMC Sprint
--
-- Tables:
--   business_model_canvas  – Core BMC with 9 JSONB block columns
--   canvas_version         – Version snapshots
--   customer_job           – Jobs customers are trying to get done
--   pain_point             – Pain points by customer segment
--   gain_creator           – Gain creators linked to customer jobs

BEGIN;

-- ============================================================
-- 1. business_model_canvas
-- ============================================================
CREATE TABLE IF NOT EXISTS business_model_canvas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organization(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('location', 'organization')),
    entity_id UUID NOT NULL,

    -- The 9 BMC building blocks stored as JSONB
    key_partners JSONB DEFAULT '[]',
    key_activities JSONB DEFAULT '[]',
    key_resources JSONB DEFAULT '[]',
    value_propositions JSONB DEFAULT '[]',
    customer_relationships JSONB DEFAULT '[]',
    channels JSONB DEFAULT '[]',
    customer_segments JSONB DEFAULT '[]',
    revenue_streams JSONB DEFAULT '[]',
    cost_structure JSONB DEFAULT '{}',

    -- Canvas metadata
    canvas_name VARCHAR(255) DEFAULT 'Primary Canvas',
    description TEXT,
    fiscal_year INTEGER,
    tags TEXT[] DEFAULT '{}',

    -- Health score (composite across all 9 blocks)
    health_score NUMERIC(5,2) DEFAULT 0
        CHECK (health_score >= 0 AND health_score <= 100),
    health_score_breakdown JSONB DEFAULT '{}',
    health_score_computed_at TIMESTAMPTZ,

    -- Version tracking
    version INTEGER DEFAULT 1,

    -- Governed lifecycle
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'business-model-canvas-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bmc_location ON business_model_canvas(location_id);
CREATE INDEX IF NOT EXISTS idx_bmc_org ON business_model_canvas(organization_id);
CREATE INDEX IF NOT EXISTS idx_bmc_entity ON business_model_canvas(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_bmc_status ON business_model_canvas(status);
CREATE INDEX IF NOT EXISTS idx_bmc_segments ON business_model_canvas USING GIN(customer_segments);
CREATE INDEX IF NOT EXISTS idx_bmc_tags ON business_model_canvas USING GIN(tags);

-- ============================================================
-- 2. canvas_version
-- ============================================================
CREATE TABLE IF NOT EXISTS canvas_version (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canvas_id UUID NOT NULL REFERENCES business_model_canvas(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    changes TEXT,
    change_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    UNIQUE(canvas_id, version)
);

CREATE INDEX IF NOT EXISTS idx_cv_canvas ON canvas_version(canvas_id);

-- ============================================================
-- 3. customer_job
-- ============================================================
CREATE TABLE IF NOT EXISTS customer_job (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canvas_id UUID NOT NULL REFERENCES business_model_canvas(id) ON DELETE CASCADE,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN ('functional', 'social', 'emotional')),
    job_description TEXT NOT NULL,
    customer_segment VARCHAR(255),
    importance_rank INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cj_canvas ON customer_job(canvas_id);
CREATE INDEX IF NOT EXISTS idx_cj_type ON customer_job(job_type);

-- ============================================================
-- 4. pain_point
-- ============================================================
CREATE TABLE IF NOT EXISTS pain_point (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canvas_id UUID NOT NULL REFERENCES business_model_canvas(id) ON DELETE CASCADE,
    job_id UUID REFERENCES customer_job(id) ON DELETE SET NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'moderate'
        CHECK (severity IN ('low', 'moderate', 'high', 'critical')),
    customer_segment VARCHAR(255),
    existing_alternatives TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pp_canvas ON pain_point(canvas_id);
CREATE INDEX IF NOT EXISTS idx_pp_job ON pain_point(job_id);
CREATE INDEX IF NOT EXISTS idx_pp_severity ON pain_point(severity);

-- ============================================================
-- 5. gain_creator
-- ============================================================
CREATE TABLE IF NOT EXISTS gain_creator (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canvas_id UUID NOT NULL REFERENCES business_model_canvas(id) ON DELETE CASCADE,
    job_id UUID REFERENCES customer_job(id) ON DELETE SET NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    gain_type VARCHAR(50) DEFAULT 'required'
        CHECK (gain_type IN ('required', 'expected', 'desired', 'unexpected')),
    customer_segment VARCHAR(255),
    value_proposition_link TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gc_canvas ON gain_creator(canvas_id);
CREATE INDEX IF NOT EXISTS idx_gc_job ON gain_creator(job_id);
CREATE INDEX IF NOT EXISTS idx_gc_type ON gain_creator(gain_type);

-- ============================================================
-- Views
-- ============================================================

-- Public-safe canvas view
CREATE OR REPLACE VIEW v_public_business_model_canvas AS
SELECT
    bmc.id,
    bmc.entity_type,
    bmc.entity_id,
    l.name AS location_name,
    bmc.canvas_name,
    bmc.description,
    bmc.fiscal_year,
    bmc.key_partners,
    bmc.key_activities,
    bmc.key_resources,
    bmc.value_propositions,
    bmc.customer_relationships,
    bmc.channels,
    bmc.customer_segments,
    bmc.revenue_streams,
    bmc.cost_structure,
    bmc.health_score,
    bmc.tags,
    bmc.version,
    bmc.created_at,
    bmc.updated_at
FROM business_model_canvas bmc
LEFT JOIN location l ON l.id = bmc.location_id
WHERE bmc.status IN ('verified', 'published')
  AND (
      bmc.entity_type != 'location'
      OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = bmc.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

-- Canvas summary view (aggregated health across all canvases per location)
CREATE OR REPLACE VIEW v_canvas_health_summary AS
SELECT
    bmc.location_id,
    l.name AS location_name,
    COUNT(*) AS canvas_count,
    AVG(bmc.health_score) AS avg_health_score,
    MIN(bmc.health_score) AS min_health_score,
    MAX(bmc.health_score) AS max_health_score,
    MAX(bmc.created_at) AS latest_canvas_at
FROM business_model_canvas bmc
JOIN location l ON l.id = bmc.location_id
WHERE bmc.status IN ('draft', 'submitted', 'verified', 'published')
GROUP BY bmc.location_id, l.name;

-- Value Proposition Canvas summary
CREATE OR REPLACE VIEW v_value_proposition_summary AS
SELECT
    bmc.id AS canvas_id,
    bmc.location_id,
    bmc.entity_id,
    COUNT(DISTINCT cj.id) AS job_count,
    COUNT(DISTINCT pp.id) AS pain_count,
    COUNT(DISTINCT gc.id) AS gain_count,
    COUNT(DISTINCT CASE WHEN pp.severity IN ('high', 'critical') THEN pp.id END) AS high_severity_pains,
    COUNT(DISTINCT CASE WHEN gc.gain_type = 'required' THEN gc.id END) AS required_gains
FROM business_model_canvas bmc
LEFT JOIN customer_job cj ON cj.canvas_id = bmc.id
LEFT JOIN pain_point pp ON pp.canvas_id = bmc.id
LEFT JOIN gain_creator gc ON gc.canvas_id = bmc.id
GROUP BY bmc.id, bmc.location_id, bmc.entity_id;

COMMIT;
