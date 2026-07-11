-- ============================================================
-- 098_multi_farm.sql — Multi-Farm Onboarding
-- ============================================================

-- 1. Farm onboarding workflow
CREATE TABLE IF NOT EXISTS farm_onboarding_workflow (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farm(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_name VARCHAR(255) NOT NULL,
    step_type VARCHAR(100) NOT NULL,
    step_description TEXT,
    depends_on UUID,
    assigned_to UUID REFERENCES staff(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(farm_id, step_order)
);

CREATE INDEX IF NOT EXISTS fow_farm ON farm_onboarding_workflow(farm_id);
CREATE INDEX IF NOT EXISTS fow_status ON farm_onboarding_workflow(status);
CREATE INDEX IF NOT EXISTS fow_order ON farm_onboarding_workflow(farm_id, step_order);

ALTER TABLE farm_onboarding_workflow DROP CONSTRAINT IF EXISTS fow_status;
ALTER TABLE farm_onboarding_workflow ADD CONSTRAINT fow_status CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped', 'blocked'));

ALTER TABLE farm_onboarding_workflow DROP CONSTRAINT IF EXISTS fow_type;
ALTER TABLE farm_onboarding_workflow ADD CONSTRAINT fow_type CHECK (step_type IN (
    'land_assessment', 'community_engagement', 'template_selection',
    'farm_specification', 'zone_setup', 'governance_setup', 'token_binding',
    'soil_baseline', 'planting', 'monitoring_setup', 'mrve_setup',
    'certification', 'go_live'
));

-- 2. Cross-farm portfolio
CREATE TABLE IF NOT EXISTS cross_farm_portfolio (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_name VARCHAR(255) NOT NULL,
    total_farm_count INTEGER DEFAULT 0,
    total_area_m2 NUMERIC(15,2) DEFAULT 0,
    total_trees INTEGER DEFAULT 0,
    total_revenue_usd NUMERIC(18,2) DEFAULT 0,
    total_carbon_sequestered NUMERIC(12,4) DEFAULT 0,
    avg_regen_score NUMERIC(5,2),
    avg_ebf_score NUMERIC(5,2),
    regions_covered TEXT[],
    last_computed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Farm template instance tracking
CREATE TABLE IF NOT EXISTS farm_template_instance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farm(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES farm_template(id) ON DELETE RESTRICT,
    template_version VARCHAR(50) NOT NULL,
    customizations JSONB DEFAULT '{}',
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by UUID REFERENCES staff(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'applied',
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS fti_farm ON farm_template_instance(farm_id);
CREATE INDEX IF NOT EXISTS fti_template ON farm_template_instance(template_id);

ALTER TABLE farm_template_instance DROP CONSTRAINT IF EXISTS fti_status;
ALTER TABLE farm_template_instance ADD CONSTRAINT fti_status CHECK (status IN ('applied', 'overridden', 'superseded'));

-- 4. Public views
CREATE OR REPLACE VIEW v_public_cross_farm_portfolio AS
SELECT
    cfp.*,
    (SELECT COUNT(*) FROM farm f WHERE f.status = 'active') AS active_farms,
    (SELECT COALESCE(SUM(re.amount), 0) FROM revenue_event re) AS total_network_revenue
FROM cross_farm_portfolio cfp
ORDER BY cfp.last_computed_at DESC
LIMIT 1;

CREATE OR REPLACE VIEW v_farm_onboarding_progress AS
SELECT
    fow.farm_id,
    f.name AS farm_name,
    l.name AS location_name,
    COUNT(*) AS total_steps,
    COUNT(*) FILTER (WHERE fow.status = 'completed') AS completed_steps,
    ROUND(COUNT(*) FILTER (WHERE fow.status = 'completed')::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) AS completion_pct,
    MAX(fow.completed_at) AS last_completed_at
FROM farm_onboarding_workflow fow
JOIN farm f ON f.id = fow.farm_id
JOIN location l ON l.id = fow.location_id
GROUP BY fow.farm_id, f.name, l.name;
