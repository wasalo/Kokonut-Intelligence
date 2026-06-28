-- ============================================================
-- 035_financial_resilience_and_scaling.sql — Sustainability, risk, scaling, and publication governance
-- ============================================================

CREATE TABLE IF NOT EXISTS financial_sustainability_plan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    plan_name VARCHAR(255) NOT NULL,
    farm_model VARCHAR(100) NOT NULL,
    plan_period_start DATE NOT NULL,
    plan_period_end DATE,
    revenue_streams TEXT[] DEFAULT '{}',
    grant_dependency_pct NUMERIC(7,4),
    reinvestment_pct NUMERIC(7,4),
    public_goods_allocation_pct NUMERIC(7,4),
    break_even_month INTEGER,
    runway_months NUMERIC(8,2),
    projected_annual_revenue_usd NUMERIC(18,2),
    projected_annual_operating_cost_usd NUMERIC(18,2),
    projected_annual_noi_usd NUMERIC(18,2),
    sustainability_status VARCHAR(50) DEFAULT 'draft',
    strategy_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_fin_sustainability_location ON financial_sustainability_plan(location_id);
CREATE INDEX IF NOT EXISTS idx_fin_sustainability_farm ON financial_sustainability_plan(farm_id);
CREATE INDEX IF NOT EXISTS idx_fin_sustainability_model ON financial_sustainability_plan(farm_model);
CREATE INDEX IF NOT EXISTS idx_fin_sustainability_status ON financial_sustainability_plan(status);

ALTER TABLE financial_sustainability_plan DROP CONSTRAINT IF EXISTS chk_fin_sustainability_status;
ALTER TABLE financial_sustainability_plan ADD CONSTRAINT chk_fin_sustainability_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE financial_sustainability_plan DROP CONSTRAINT IF EXISTS chk_fin_sustainability_model;
ALTER TABLE financial_sustainability_plan ADD CONSTRAINT chk_fin_sustainability_model CHECK (farm_model IN (
    'public_good_optimized', 'blended', 'for_profit', 'cooperative', 'research_pilot', 'other'
));

ALTER TABLE financial_sustainability_plan DROP CONSTRAINT IF EXISTS chk_fin_sustainability_plan_state;
ALTER TABLE financial_sustainability_plan ADD CONSTRAINT chk_fin_sustainability_plan_state CHECK (sustainability_status IN (
    'draft', 'grant_dependent', 'transitioning', 'self_sustaining', 'surplus_generating', 'needs_rework'
));

ALTER TABLE financial_sustainability_plan DROP CONSTRAINT IF EXISTS chk_fin_sustainability_percentages;
ALTER TABLE financial_sustainability_plan ADD CONSTRAINT chk_fin_sustainability_percentages CHECK (
    (grant_dependency_pct IS NULL OR grant_dependency_pct BETWEEN 0 AND 100)
    AND (reinvestment_pct IS NULL OR reinvestment_pct BETWEEN 0 AND 100)
    AND (public_goods_allocation_pct IS NULL OR public_goods_allocation_pct BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS risk_mitigation_register (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    risk_category VARCHAR(100) NOT NULL,
    risk_description TEXT NOT NULL,
    likelihood VARCHAR(50),
    impact_level VARCHAR(50),
    mitigation_strategy TEXT NOT NULL,
    insurance_scope TEXT,
    oversight_mechanism TEXT,
    technical_support_provider TEXT,
    owner_role VARCHAR(100),
    review_cadence VARCHAR(100),
    residual_risk_level VARCHAR(50),
    review_date DATE,
    next_review_date DATE,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_risk_register_location ON risk_mitigation_register(location_id);
CREATE INDEX IF NOT EXISTS idx_risk_register_farm ON risk_mitigation_register(farm_id);
CREATE INDEX IF NOT EXISTS idx_risk_register_category ON risk_mitigation_register(risk_category);
CREATE INDEX IF NOT EXISTS idx_risk_register_status ON risk_mitigation_register(status);
CREATE INDEX IF NOT EXISTS idx_risk_register_next_review ON risk_mitigation_register(next_review_date);

ALTER TABLE risk_mitigation_register DROP CONSTRAINT IF EXISTS chk_risk_register_status;
ALTER TABLE risk_mitigation_register ADD CONSTRAINT chk_risk_register_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE risk_mitigation_register DROP CONSTRAINT IF EXISTS chk_risk_register_category;
ALTER TABLE risk_mitigation_register ADD CONSTRAINT chk_risk_register_category CHECK (risk_category IN (
    'climate', 'market', 'operational', 'financial', 'governance', 'policy',
    'evidence_quality', 'community', 'technical', 'other'
));

ALTER TABLE risk_mitigation_register DROP CONSTRAINT IF EXISTS chk_risk_register_levels;
ALTER TABLE risk_mitigation_register ADD CONSTRAINT chk_risk_register_levels CHECK (
    (likelihood IS NULL OR likelihood IN ('low', 'medium', 'high', 'unknown'))
    AND (impact_level IS NULL OR impact_level IN ('low', 'medium', 'high', 'critical', 'unknown'))
    AND (residual_risk_level IS NULL OR residual_risk_level IN ('low', 'medium', 'high', 'critical', 'unknown'))
);

CREATE TABLE IF NOT EXISTS scaling_roadmap_milestone (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    roadmap_name VARCHAR(255) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    target_region VARCHAR(255),
    farm_model VARCHAR(100) NOT NULL,
    planned_farm_count INTEGER,
    capital_required_usd NUMERIC(18,2),
    partner_requirements TEXT[] DEFAULT '{}',
    operational_dependencies TEXT[] DEFAULT '{}',
    risk_gates TEXT[] DEFAULT '{}',
    target_date DATE NOT NULL,
    milestone_status VARCHAR(50) DEFAULT 'planned',
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_scaling_roadmap_location ON scaling_roadmap_milestone(location_id);
CREATE INDEX IF NOT EXISTS idx_scaling_roadmap_region ON scaling_roadmap_milestone(target_region);
CREATE INDEX IF NOT EXISTS idx_scaling_roadmap_model ON scaling_roadmap_milestone(farm_model);
CREATE INDEX IF NOT EXISTS idx_scaling_roadmap_status ON scaling_roadmap_milestone(status, milestone_status);
CREATE INDEX IF NOT EXISTS idx_scaling_roadmap_target_date ON scaling_roadmap_milestone(target_date);

ALTER TABLE scaling_roadmap_milestone DROP CONSTRAINT IF EXISTS chk_scaling_roadmap_status;
ALTER TABLE scaling_roadmap_milestone ADD CONSTRAINT chk_scaling_roadmap_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE scaling_roadmap_milestone DROP CONSTRAINT IF EXISTS chk_scaling_roadmap_milestone_status;
ALTER TABLE scaling_roadmap_milestone ADD CONSTRAINT chk_scaling_roadmap_milestone_status CHECK (milestone_status IN (
    'planned', 'in_progress', 'completed', 'blocked', 'deferred', 'cancelled'
));

ALTER TABLE scaling_roadmap_milestone DROP CONSTRAINT IF EXISTS chk_scaling_roadmap_model;
ALTER TABLE scaling_roadmap_milestone ADD CONSTRAINT chk_scaling_roadmap_model CHECK (farm_model IN (
    'public_good_optimized', 'blended', 'for_profit', 'cooperative', 'research_pilot', 'other'
));

CREATE TABLE IF NOT EXISTS green_paper_publication_review (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(50) NOT NULL,
    document_path TEXT NOT NULL,
    review_status VARCHAR(50) DEFAULT 'draft',
    review_owner VARCHAR(255),
    review_started_at TIMESTAMPTZ,
    target_publication_date DATE,
    open_questions JSONB DEFAULT '[]',
    approval_records JSONB DEFAULT '[]',
    publication_cid TEXT,
    publication_hash TEXT,
    published_at TIMESTAMPTZ,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    UNIQUE(version, document_path)
);

CREATE INDEX IF NOT EXISTS idx_green_paper_review_status ON green_paper_publication_review(review_status, status);
CREATE INDEX IF NOT EXISTS idx_green_paper_review_target ON green_paper_publication_review(target_publication_date);

ALTER TABLE green_paper_publication_review DROP CONSTRAINT IF EXISTS chk_green_paper_review_status;
ALTER TABLE green_paper_publication_review ADD CONSTRAINT chk_green_paper_review_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE green_paper_publication_review DROP CONSTRAINT IF EXISTS chk_green_paper_review_state;
ALTER TABLE green_paper_publication_review ADD CONSTRAINT chk_green_paper_review_state CHECK (review_status IN (
    'draft', 'request_for_comments', 'stakeholder_review', 'approved_for_publication',
    'published', 'needs_rework', 'superseded'
));

CREATE OR REPLACE VIEW v_public_financial_sustainability_summary AS
SELECT
    fsp.id,
    fsp.location_id,
    fsp.farm_id,
    fsp.plan_name,
    fsp.farm_model,
    fsp.plan_period_start,
    fsp.plan_period_end,
    fsp.revenue_streams,
    fsp.grant_dependency_pct,
    fsp.reinvestment_pct,
    fsp.public_goods_allocation_pct,
    fsp.break_even_month,
    fsp.runway_months,
    fsp.projected_annual_revenue_usd,
    fsp.projected_annual_operating_cost_usd,
    fsp.projected_annual_noi_usd,
    fsp.sustainability_status,
    fsp.public_summary,
    fsp.evidence_maturity,
    em.label AS evidence_maturity_label,
    fsp.metadata
FROM financial_sustainability_plan fsp
LEFT JOIN evidence_maturity_level em ON em.level = fsp.evidence_maturity
WHERE fsp.status = 'published'
  AND fsp.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(fsp.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = fsp.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_risk_mitigation_summary AS
SELECT
    rmr.id,
    rmr.location_id,
    rmr.farm_id,
    rmr.risk_category,
    rmr.risk_description,
    rmr.likelihood,
    rmr.impact_level,
    rmr.mitigation_strategy,
    rmr.insurance_scope,
    rmr.oversight_mechanism,
    rmr.technical_support_provider,
    rmr.owner_role,
    rmr.review_cadence,
    rmr.residual_risk_level,
    rmr.review_date,
    rmr.next_review_date,
    rmr.public_summary,
    rmr.evidence_maturity,
    em.label AS evidence_maturity_label,
    rmr.metadata
FROM risk_mitigation_register rmr
LEFT JOIN evidence_maturity_level em ON em.level = rmr.evidence_maturity
WHERE rmr.status = 'published'
  AND rmr.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(rmr.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = rmr.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_scaling_roadmap_summary AS
SELECT
    srm.id,
    srm.roadmap_name,
    srm.location_id,
    srm.target_region,
    srm.farm_model,
    srm.planned_farm_count,
    srm.capital_required_usd,
    srm.partner_requirements,
    srm.operational_dependencies,
    srm.risk_gates,
    srm.target_date,
    srm.milestone_status,
    srm.public_summary,
    srm.evidence_maturity,
    em.label AS evidence_maturity_label,
    srm.metadata
FROM scaling_roadmap_milestone srm
LEFT JOIN evidence_maturity_level em ON em.level = srm.evidence_maturity
WHERE srm.status = 'published'
  AND srm.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(srm.public_summary, '')), '') IS NOT NULL;

CREATE OR REPLACE VIEW v_public_green_paper_publication_status AS
SELECT
    gpr.id,
    gpr.version,
    gpr.document_path,
    gpr.review_status,
    gpr.review_owner,
    gpr.target_publication_date,
    jsonb_array_length(COALESCE(gpr.open_questions, '[]'::jsonb)) AS open_question_count,
    jsonb_array_length(COALESCE(gpr.approval_records, '[]'::jsonb)) AS approval_record_count,
    gpr.publication_cid,
    gpr.publication_hash,
    gpr.published_at,
    gpr.public_summary,
    gpr.evidence_maturity,
    em.label AS evidence_maturity_label
FROM green_paper_publication_review gpr
LEFT JOIN evidence_maturity_level em ON em.level = gpr.evidence_maturity
WHERE gpr.status IN ('verified', 'published')
  AND NULLIF(TRIM(COALESCE(gpr.public_summary, '')), '') IS NOT NULL;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('financial-resilience-scaling-v1', 'Financial sustainability plans, risk register, scaling roadmap, and Green Paper publication review', 'schema 035')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
