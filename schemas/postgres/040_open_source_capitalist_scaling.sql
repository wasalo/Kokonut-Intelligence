-- ============================================================
-- 040_open_source_capitalist_scaling.sql — Scaling economics, adoption barriers, stress tests, and open-source reuse evidence
-- ============================================================

CREATE TABLE IF NOT EXISTS farm_launch_unit_economics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    source_scaling_milestone_id UUID REFERENCES scaling_roadmap_milestone(id) ON DELETE SET NULL,
    economics_name VARCHAR(255) NOT NULL,
    farm_model VARCHAR(100) NOT NULL,
    target_region VARCHAR(255),
    planned_farm_count INTEGER,
    planned_hectares NUMERIC(12,4),
    expected_beneficiary_count INTEGER,
    setup_cost_usd NUMERIC(18,2),
    first_year_operating_cost_usd NUMERIC(18,2),
    verification_overhead_usd NUMERIC(18,2),
    total_launch_cost_usd NUMERIC(18,2),
    cost_per_farm_usd NUMERIC(18,2),
    cost_per_hectare_usd NUMERIC(18,2),
    cost_per_beneficiary_usd NUMERIC(18,2),
    projected_annual_revenue_usd NUMERIC(18,2),
    projected_annual_noi_usd NUMERIC(18,2),
    projected_roi_pct NUMERIC(10,4),
    payback_months NUMERIC(10,2),
    launch_timeline_months NUMERIC(10,2),
    assumptions TEXT[] DEFAULT '{}',
    evidence_confidence VARCHAR(50),
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

CREATE INDEX IF NOT EXISTS idx_farm_launch_economics_location ON farm_launch_unit_economics(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_launch_economics_model ON farm_launch_unit_economics(farm_model);
CREATE INDEX IF NOT EXISTS idx_farm_launch_economics_status ON farm_launch_unit_economics(status);

ALTER TABLE farm_launch_unit_economics DROP CONSTRAINT IF EXISTS chk_farm_launch_economics_status;
ALTER TABLE farm_launch_unit_economics ADD CONSTRAINT chk_farm_launch_economics_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE farm_launch_unit_economics DROP CONSTRAINT IF EXISTS chk_farm_launch_economics_model;
ALTER TABLE farm_launch_unit_economics ADD CONSTRAINT chk_farm_launch_economics_model CHECK (farm_model IN (
    'public_good_optimized', 'blended', 'for_profit', 'cooperative', 'research_pilot', 'other'
));

ALTER TABLE farm_launch_unit_economics DROP CONSTRAINT IF EXISTS chk_farm_launch_economics_confidence;
ALTER TABLE farm_launch_unit_economics ADD CONSTRAINT chk_farm_launch_economics_confidence CHECK (
    evidence_confidence IS NULL OR evidence_confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')
);

ALTER TABLE farm_launch_unit_economics DROP CONSTRAINT IF EXISTS chk_farm_launch_economics_values;
ALTER TABLE farm_launch_unit_economics ADD CONSTRAINT chk_farm_launch_economics_values CHECK (
    (planned_farm_count IS NULL OR planned_farm_count >= 0)
    AND (planned_hectares IS NULL OR planned_hectares >= 0)
    AND (expected_beneficiary_count IS NULL OR expected_beneficiary_count >= 0)
    AND (setup_cost_usd IS NULL OR setup_cost_usd >= 0)
    AND (first_year_operating_cost_usd IS NULL OR first_year_operating_cost_usd >= 0)
    AND (verification_overhead_usd IS NULL OR verification_overhead_usd >= 0)
    AND (total_launch_cost_usd IS NULL OR total_launch_cost_usd >= 0)
    AND (cost_per_farm_usd IS NULL OR cost_per_farm_usd >= 0)
    AND (cost_per_hectare_usd IS NULL OR cost_per_hectare_usd >= 0)
    AND (cost_per_beneficiary_usd IS NULL OR cost_per_beneficiary_usd >= 0)
    AND (projected_annual_revenue_usd IS NULL OR projected_annual_revenue_usd >= 0)
    AND (payback_months IS NULL OR payback_months >= 0)
    AND (launch_timeline_months IS NULL OR launch_timeline_months >= 0)
);

CREATE TABLE IF NOT EXISTS network_scaling_target (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_name VARCHAR(255) NOT NULL,
    target_region VARCHAR(255),
    farm_model VARCHAR(100) NOT NULL,
    target_date DATE NOT NULL,
    target_farm_count INTEGER NOT NULL,
    target_hectares NUMERIC(12,4),
    target_beneficiary_count INTEGER,
    capital_required_usd NUMERIC(18,2),
    expected_public_goods_value_usd NUMERIC(18,2),
    expected_verification_outputs INTEGER,
    readiness_score NUMERIC(5,2),
    dependency_summary TEXT NOT NULL,
    risk_gate_summary TEXT NOT NULL,
    target_status VARCHAR(50) DEFAULT 'planned',
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_network_scaling_region ON network_scaling_target(target_region);
CREATE INDEX IF NOT EXISTS idx_network_scaling_model ON network_scaling_target(farm_model);
CREATE INDEX IF NOT EXISTS idx_network_scaling_status ON network_scaling_target(status, target_status);
CREATE INDEX IF NOT EXISTS idx_network_scaling_target_date ON network_scaling_target(target_date);

ALTER TABLE network_scaling_target DROP CONSTRAINT IF EXISTS chk_network_scaling_status;
ALTER TABLE network_scaling_target ADD CONSTRAINT chk_network_scaling_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE network_scaling_target DROP CONSTRAINT IF EXISTS chk_network_scaling_target_status;
ALTER TABLE network_scaling_target ADD CONSTRAINT chk_network_scaling_target_status CHECK (target_status IN (
    'planned', 'conditional', 'in_progress', 'achieved', 'blocked', 'deferred', 'cancelled'
));

ALTER TABLE network_scaling_target DROP CONSTRAINT IF EXISTS chk_network_scaling_model;
ALTER TABLE network_scaling_target ADD CONSTRAINT chk_network_scaling_model CHECK (farm_model IN (
    'public_good_optimized', 'blended', 'for_profit', 'cooperative', 'research_pilot', 'other'
));

ALTER TABLE network_scaling_target DROP CONSTRAINT IF EXISTS chk_network_scaling_values;
ALTER TABLE network_scaling_target ADD CONSTRAINT chk_network_scaling_values CHECK (
    target_farm_count >= 0
    AND (target_hectares IS NULL OR target_hectares >= 0)
    AND (target_beneficiary_count IS NULL OR target_beneficiary_count >= 0)
    AND (capital_required_usd IS NULL OR capital_required_usd >= 0)
    AND (expected_public_goods_value_usd IS NULL OR expected_public_goods_value_usd >= 0)
    AND (expected_verification_outputs IS NULL OR expected_verification_outputs >= 0)
    AND (readiness_score IS NULL OR readiness_score BETWEEN 0 AND 10)
);

CREATE TABLE IF NOT EXISTS adoption_barrier_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    assessment_date DATE NOT NULL,
    barrier_category VARCHAR(100) NOT NULL,
    barrier_name VARCHAR(255) NOT NULL,
    affected_scope VARCHAR(100) NOT NULL,
    severity VARCHAR(50),
    likelihood VARCHAR(50),
    resolution_status VARCHAR(50) DEFAULT 'open',
    owner_role VARCHAR(100),
    mitigation_plan TEXT NOT NULL,
    estimated_mitigation_cost_usd NUMERIC(18,2),
    target_resolution_date DATE,
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

CREATE INDEX IF NOT EXISTS idx_adoption_barrier_location ON adoption_barrier_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_adoption_barrier_category ON adoption_barrier_assessment(barrier_category);
CREATE INDEX IF NOT EXISTS idx_adoption_barrier_status ON adoption_barrier_assessment(status, resolution_status);

ALTER TABLE adoption_barrier_assessment DROP CONSTRAINT IF EXISTS chk_adoption_barrier_status;
ALTER TABLE adoption_barrier_assessment ADD CONSTRAINT chk_adoption_barrier_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE adoption_barrier_assessment DROP CONSTRAINT IF EXISTS chk_adoption_barrier_category;
ALTER TABLE adoption_barrier_assessment ADD CONSTRAINT chk_adoption_barrier_category CHECK (barrier_category IN (
    'farmer_onboarding', 'dao_governance', 'regulatory', 'cultural', 'market', 'technical', 'capital', 'evidence_quality', 'other'
));

ALTER TABLE adoption_barrier_assessment DROP CONSTRAINT IF EXISTS chk_adoption_barrier_scope;
ALTER TABLE adoption_barrier_assessment ADD CONSTRAINT chk_adoption_barrier_scope CHECK (affected_scope IN (
    'farm', 'community', 'region', 'network', 'partner', 'other'
));

ALTER TABLE adoption_barrier_assessment DROP CONSTRAINT IF EXISTS chk_adoption_barrier_levels;
ALTER TABLE adoption_barrier_assessment ADD CONSTRAINT chk_adoption_barrier_levels CHECK (
    (severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical', 'unknown'))
    AND (likelihood IS NULL OR likelihood IN ('low', 'medium', 'high', 'unknown'))
    AND resolution_status IN ('open', 'mitigating', 'resolved', 'accepted', 'blocked')
    AND (estimated_mitigation_cost_usd IS NULL OR estimated_mitigation_cost_usd >= 0)
);

CREATE TABLE IF NOT EXISTS perpetual_value_stress_test (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    financial_sustainability_plan_id UUID REFERENCES financial_sustainability_plan(id) ON DELETE SET NULL,
    scenario_name VARCHAR(255) NOT NULL,
    scenario_date DATE NOT NULL,
    stress_type VARCHAR(100) NOT NULL,
    revenue_change_pct NUMERIC(8,4),
    cost_change_pct NUMERIC(8,4),
    grant_delay_months NUMERIC(10,2),
    yield_change_pct NUMERIC(8,4),
    baseline_runway_months NUMERIC(10,2),
    downside_runway_months NUMERIC(10,2),
    baseline_noi_usd NUMERIC(18,2),
    downside_noi_usd NUMERIC(18,2),
    solvency_status VARCHAR(50) DEFAULT 'untested',
    mitigation_actions TEXT[] DEFAULT '{}',
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

CREATE INDEX IF NOT EXISTS idx_perpetual_stress_location ON perpetual_value_stress_test(location_id);
CREATE INDEX IF NOT EXISTS idx_perpetual_stress_type ON perpetual_value_stress_test(stress_type);
CREATE INDEX IF NOT EXISTS idx_perpetual_stress_status ON perpetual_value_stress_test(status, solvency_status);

ALTER TABLE perpetual_value_stress_test DROP CONSTRAINT IF EXISTS chk_perpetual_stress_status;
ALTER TABLE perpetual_value_stress_test ADD CONSTRAINT chk_perpetual_stress_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE perpetual_value_stress_test DROP CONSTRAINT IF EXISTS chk_perpetual_stress_type;
ALTER TABLE perpetual_value_stress_test ADD CONSTRAINT chk_perpetual_stress_type CHECK (stress_type IN (
    'market_downturn', 'grant_delay', 'cost_inflation', 'yield_shock', 'climate_event', 'dao_funding_delay', 'combined_downside', 'other'
));

ALTER TABLE perpetual_value_stress_test DROP CONSTRAINT IF EXISTS chk_perpetual_stress_solvency;
ALTER TABLE perpetual_value_stress_test ADD CONSTRAINT chk_perpetual_stress_solvency CHECK (solvency_status IN (
    'untested', 'resilient', 'watchlist', 'needs_mitigation', 'insolvent_without_support'
));

ALTER TABLE perpetual_value_stress_test DROP CONSTRAINT IF EXISTS chk_perpetual_stress_values;
ALTER TABLE perpetual_value_stress_test ADD CONSTRAINT chk_perpetual_stress_values CHECK (
    (baseline_runway_months IS NULL OR baseline_runway_months >= 0)
    AND (downside_runway_months IS NULL OR downside_runway_months >= 0)
);

CREATE TABLE IF NOT EXISTS open_source_impact_artifact (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    artifact_name VARCHAR(255) NOT NULL,
    artifact_type VARCHAR(100) NOT NULL,
    repository_path TEXT,
    external_url TEXT,
    license VARCHAR(100),
    version VARCHAR(100),
    reuse_status VARCHAR(50) DEFAULT 'available',
    reuse_count INTEGER DEFAULT 0,
    supported_use_cases TEXT[] DEFAULT '{}',
    verification_outputs TEXT[] DEFAULT '{}',
    maintenance_owner VARCHAR(100),
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_open_source_artifact_type ON open_source_impact_artifact(artifact_type);
CREATE INDEX IF NOT EXISTS idx_open_source_artifact_status ON open_source_impact_artifact(status, reuse_status);

ALTER TABLE open_source_impact_artifact DROP CONSTRAINT IF EXISTS chk_open_source_artifact_status;
ALTER TABLE open_source_impact_artifact ADD CONSTRAINT chk_open_source_artifact_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE open_source_impact_artifact DROP CONSTRAINT IF EXISTS chk_open_source_artifact_type;
ALTER TABLE open_source_impact_artifact ADD CONSTRAINT chk_open_source_artifact_type CHECK (artifact_type IN (
    'schema', 'dashboard', 'agent', 'report', 'playbook', 'contract', 'export_mapping', 'dataset', 'other'
));

ALTER TABLE open_source_impact_artifact DROP CONSTRAINT IF EXISTS chk_open_source_artifact_reuse;
ALTER TABLE open_source_impact_artifact ADD CONSTRAINT chk_open_source_artifact_reuse CHECK (
    reuse_status IN ('available', 'in_use', 'pilot_reuse', 'deprecated', 'maintenance_needed')
    AND reuse_count >= 0
);

CREATE OR REPLACE VIEW v_public_farm_launch_unit_economics AS
SELECT
    flue.id,
    flue.location_id,
    flue.source_scaling_milestone_id,
    flue.economics_name,
    flue.farm_model,
    flue.target_region,
    flue.planned_farm_count,
    flue.planned_hectares,
    flue.expected_beneficiary_count,
    flue.setup_cost_usd,
    flue.first_year_operating_cost_usd,
    flue.verification_overhead_usd,
    flue.total_launch_cost_usd,
    flue.cost_per_farm_usd,
    flue.cost_per_hectare_usd,
    flue.cost_per_beneficiary_usd,
    flue.projected_annual_revenue_usd,
    flue.projected_annual_noi_usd,
    flue.projected_roi_pct,
    flue.payback_months,
    flue.launch_timeline_months,
    flue.assumptions,
    flue.evidence_confidence,
    flue.public_summary,
    flue.evidence_maturity,
    em.label AS evidence_maturity_label,
    flue.metadata
FROM farm_launch_unit_economics flue
LEFT JOIN evidence_maturity_level em ON em.level = flue.evidence_maturity
WHERE flue.status = 'published'
  AND flue.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(flue.public_summary, '')), '') IS NOT NULL
  AND (
      flue.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = flue.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_network_scaling_target AS
SELECT
    nst.id,
    nst.target_name,
    nst.target_region,
    nst.farm_model,
    nst.target_date,
    nst.target_farm_count,
    nst.target_hectares,
    nst.target_beneficiary_count,
    nst.capital_required_usd,
    CASE WHEN nst.target_farm_count > 0 THEN ROUND(nst.capital_required_usd / nst.target_farm_count, 2) ELSE NULL END AS capital_required_per_farm_usd,
    nst.expected_public_goods_value_usd,
    nst.expected_verification_outputs,
    nst.readiness_score,
    nst.dependency_summary,
    nst.risk_gate_summary,
    nst.target_status,
    nst.public_summary,
    nst.evidence_maturity,
    em.label AS evidence_maturity_label,
    nst.metadata
FROM network_scaling_target nst
LEFT JOIN evidence_maturity_level em ON em.level = nst.evidence_maturity
WHERE nst.status = 'published'
  AND nst.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(nst.public_summary, '')), '') IS NOT NULL;

CREATE OR REPLACE VIEW v_public_adoption_barrier_assessment AS
SELECT
    aba.id,
    aba.location_id,
    aba.assessment_date,
    aba.barrier_category,
    aba.barrier_name,
    aba.affected_scope,
    aba.severity,
    aba.likelihood,
    aba.resolution_status,
    aba.owner_role,
    aba.mitigation_plan,
    aba.estimated_mitigation_cost_usd,
    aba.target_resolution_date,
    aba.public_summary,
    aba.evidence_maturity,
    em.label AS evidence_maturity_label,
    aba.metadata
FROM adoption_barrier_assessment aba
LEFT JOIN evidence_maturity_level em ON em.level = aba.evidence_maturity
WHERE aba.status = 'published'
  AND aba.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(aba.public_summary, '')), '') IS NOT NULL
  AND (
      aba.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = aba.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_perpetual_value_stress_test AS
SELECT
    pvst.id,
    pvst.location_id,
    pvst.financial_sustainability_plan_id,
    pvst.scenario_name,
    pvst.scenario_date,
    pvst.stress_type,
    pvst.revenue_change_pct,
    pvst.cost_change_pct,
    pvst.grant_delay_months,
    pvst.yield_change_pct,
    pvst.baseline_runway_months,
    pvst.downside_runway_months,
    pvst.baseline_noi_usd,
    pvst.downside_noi_usd,
    pvst.solvency_status,
    pvst.mitigation_actions,
    pvst.public_summary,
    pvst.evidence_maturity,
    em.label AS evidence_maturity_label,
    pvst.metadata
FROM perpetual_value_stress_test pvst
LEFT JOIN evidence_maturity_level em ON em.level = pvst.evidence_maturity
WHERE pvst.status = 'published'
  AND pvst.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(pvst.public_summary, '')), '') IS NOT NULL
  AND (
      pvst.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = pvst.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_open_source_impact_artifact AS
SELECT
    osia.id,
    osia.artifact_name,
    osia.artifact_type,
    osia.repository_path,
    osia.external_url,
    osia.license,
    osia.version,
    osia.reuse_status,
    osia.reuse_count,
    osia.supported_use_cases,
    osia.verification_outputs,
    osia.maintenance_owner,
    osia.public_summary,
    osia.evidence_maturity,
    em.label AS evidence_maturity_label,
    osia.metadata
FROM open_source_impact_artifact osia
LEFT JOIN evidence_maturity_level em ON em.level = osia.evidence_maturity
WHERE osia.status = 'published'
  AND osia.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(osia.public_summary, '')), '') IS NOT NULL;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('open-source-capitalist-scaling-v1', 'Scaling economics, adoption barriers, perpetual value stress tests, and open-source reuse evidence', 'schema 040')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
