-- ============================================================
-- 036_capital_efficiency_and_utility.sql — Capital efficiency, regenerative ROI scenarios, and governance throughput
-- ============================================================

CREATE TABLE IF NOT EXISTS capital_efficiency_scenario (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    scenario_name VARCHAR(255) NOT NULL,
    scenario_type VARCHAR(100) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE,
    capital_deployed_usd NUMERIC(18,2) NOT NULL,
    gross_output_value_usd NUMERIC(18,2),
    net_output_value_usd NUMERIC(18,2),
    public_goods_value_usd NUMERIC(18,2),
    capital_leverage_ratio NUMERIC(12,4),
    efficiency_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_capital_efficiency_location ON capital_efficiency_scenario(location_id);
CREATE INDEX IF NOT EXISTS idx_capital_efficiency_type ON capital_efficiency_scenario(scenario_type);
CREATE INDEX IF NOT EXISTS idx_capital_efficiency_status ON capital_efficiency_scenario(status);

ALTER TABLE capital_efficiency_scenario DROP CONSTRAINT IF EXISTS chk_capital_efficiency_status;
ALTER TABLE capital_efficiency_scenario ADD CONSTRAINT chk_capital_efficiency_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE capital_efficiency_scenario DROP CONSTRAINT IF EXISTS chk_capital_efficiency_type;
ALTER TABLE capital_efficiency_scenario ADD CONSTRAINT chk_capital_efficiency_type CHECK (scenario_type IN (
    'farm_establishment', 'practice_upgrade', 'public_goods_loop', 'replication',
    'sponsor_supported', 'partner_infrastructure', 'other'
));

ALTER TABLE capital_efficiency_scenario DROP CONSTRAINT IF EXISTS chk_capital_efficiency_amounts;
ALTER TABLE capital_efficiency_scenario ADD CONSTRAINT chk_capital_efficiency_amounts CHECK (
    capital_deployed_usd >= 0
    AND (gross_output_value_usd IS NULL OR gross_output_value_usd >= 0)
    AND (public_goods_value_usd IS NULL OR public_goods_value_usd >= 0)
    AND (capital_leverage_ratio IS NULL OR capital_leverage_ratio >= 0)
);

CREATE TABLE IF NOT EXISTS regenerative_efficiency_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    practice_event_id UUID REFERENCES farm_practice_event(id) ON DELETE SET NULL,
    observation_date DATE NOT NULL,
    practice_type VARCHAR(100) NOT NULL,
    baseline_cost_usd NUMERIC(18,2),
    observed_cost_usd NUMERIC(18,2),
    cost_savings_pct NUMERIC(8,4),
    incremental_output_value_usd NUMERIC(18,2),
    implementation_cost_usd NUMERIC(18,2),
    payback_months NUMERIC(10,2),
    efficiency_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_regen_efficiency_location ON regenerative_efficiency_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_regen_efficiency_practice ON regenerative_efficiency_observation(practice_type);
CREATE INDEX IF NOT EXISTS idx_regen_efficiency_status ON regenerative_efficiency_observation(status);

ALTER TABLE regenerative_efficiency_observation DROP CONSTRAINT IF EXISTS chk_regen_efficiency_status;
ALTER TABLE regenerative_efficiency_observation ADD CONSTRAINT chk_regen_efficiency_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE regenerative_efficiency_observation DROP CONSTRAINT IF EXISTS chk_regen_efficiency_values;
ALTER TABLE regenerative_efficiency_observation ADD CONSTRAINT chk_regen_efficiency_values CHECK (
    (baseline_cost_usd IS NULL OR baseline_cost_usd >= 0)
    AND (observed_cost_usd IS NULL OR observed_cost_usd >= 0)
    AND (cost_savings_pct IS NULL OR cost_savings_pct BETWEEN -100 AND 100)
    AND (implementation_cost_usd IS NULL OR implementation_cost_usd >= 0)
    AND (payback_months IS NULL OR payback_months >= 0)
);

CREATE TABLE IF NOT EXISTS governance_throughput_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    dao_proposal_id UUID REFERENCES dao_proposal(id) ON DELETE SET NULL,
    proposal_code VARCHAR(100) NOT NULL,
    venue VARCHAR(100),
    proposal_type VARCHAR(100),
    proposal_created_at TIMESTAMPTZ NOT NULL,
    decision_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    decision_latency_days NUMERIC(10,2),
    execution_latency_days NUMERIC(10,2),
    decision_result VARCHAR(50),
    governance_summary TEXT NOT NULL,
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
    updated_by UUID,
    UNIQUE(proposal_code, source_system, source_id)
);

CREATE INDEX IF NOT EXISTS idx_governance_throughput_location ON governance_throughput_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_governance_throughput_proposal ON governance_throughput_observation(proposal_code);
CREATE INDEX IF NOT EXISTS idx_governance_throughput_status ON governance_throughput_observation(status);

ALTER TABLE governance_throughput_observation DROP CONSTRAINT IF EXISTS chk_governance_throughput_status;
ALTER TABLE governance_throughput_observation ADD CONSTRAINT chk_governance_throughput_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE governance_throughput_observation DROP CONSTRAINT IF EXISTS chk_governance_decision_result;
ALTER TABLE governance_throughput_observation ADD CONSTRAINT chk_governance_decision_result CHECK (
    decision_result IS NULL OR decision_result IN ('approved', 'rejected', 'cancelled', 'deferred', 'executed', 'unknown')
);

CREATE TABLE IF NOT EXISTS capital_provider_utility_scenario (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    capital_source_id UUID REFERENCES capital_source(id) ON DELETE SET NULL,
    scenario_name VARCHAR(255) NOT NULL,
    provider_type VARCHAR(100) NOT NULL,
    capital_amount_usd NUMERIC(18,2) NOT NULL,
    expected_financial_return_usd NUMERIC(18,2),
    expected_public_goods_value_usd NUMERIC(18,2),
    expected_verification_outputs INTEGER,
    expected_payback_months NUMERIC(10,2),
    utility_score NUMERIC(5,2),
    utility_summary TEXT NOT NULL,
    public_summary TEXT,
    limitations TEXT[] DEFAULT '{}',
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

CREATE INDEX IF NOT EXISTS idx_capital_provider_location ON capital_provider_utility_scenario(location_id);
CREATE INDEX IF NOT EXISTS idx_capital_provider_type ON capital_provider_utility_scenario(provider_type);
CREATE INDEX IF NOT EXISTS idx_capital_provider_status ON capital_provider_utility_scenario(status);

ALTER TABLE capital_provider_utility_scenario DROP CONSTRAINT IF EXISTS chk_capital_provider_status;
ALTER TABLE capital_provider_utility_scenario ADD CONSTRAINT chk_capital_provider_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE capital_provider_utility_scenario DROP CONSTRAINT IF EXISTS chk_capital_provider_type;
ALTER TABLE capital_provider_utility_scenario ADD CONSTRAINT chk_capital_provider_type CHECK (provider_type IN (
    'grantmaker', 'sponsor', 'dao_treasury', 'impact_investor', 'buyer_partner', 'public_goods_funder', 'other'
));

ALTER TABLE capital_provider_utility_scenario DROP CONSTRAINT IF EXISTS chk_capital_provider_values;
ALTER TABLE capital_provider_utility_scenario ADD CONSTRAINT chk_capital_provider_values CHECK (
    capital_amount_usd >= 0
    AND (expected_financial_return_usd IS NULL OR expected_financial_return_usd >= 0)
    AND (expected_public_goods_value_usd IS NULL OR expected_public_goods_value_usd >= 0)
    AND (expected_verification_outputs IS NULL OR expected_verification_outputs >= 0)
    AND (expected_payback_months IS NULL OR expected_payback_months >= 0)
    AND (utility_score IS NULL OR utility_score BETWEEN 0 AND 10)
);

CREATE OR REPLACE VIEW v_public_capital_efficiency_summary AS
SELECT
    ces.id,
    ces.location_id,
    ces.farm_id,
    ces.scenario_name,
    ces.scenario_type,
    ces.period_start,
    ces.period_end,
    ces.capital_deployed_usd,
    ces.gross_output_value_usd,
    ces.net_output_value_usd,
    ces.public_goods_value_usd,
    ces.capital_leverage_ratio,
    ces.public_summary,
    ces.evidence_maturity,
    em.label AS evidence_maturity_label,
    ces.metadata
FROM capital_efficiency_scenario ces
LEFT JOIN evidence_maturity_level em ON em.level = ces.evidence_maturity
WHERE ces.status = 'published'
  AND ces.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(ces.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = ces.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_regenerative_efficiency_summary AS
SELECT
    reo.id,
    reo.location_id,
    reo.farm_id,
    reo.practice_event_id,
    reo.observation_date,
    reo.practice_type,
    reo.baseline_cost_usd,
    reo.observed_cost_usd,
    reo.cost_savings_pct,
    reo.incremental_output_value_usd,
    reo.implementation_cost_usd,
    reo.payback_months,
    reo.public_summary,
    reo.evidence_maturity,
    em.label AS evidence_maturity_label,
    reo.metadata
FROM regenerative_efficiency_observation reo
LEFT JOIN evidence_maturity_level em ON em.level = reo.evidence_maturity
WHERE reo.status = 'published'
  AND reo.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(reo.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = reo.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_governance_throughput_summary AS
SELECT
    gto.id,
    gto.location_id,
    gto.dao_proposal_id,
    gto.proposal_code,
    gto.venue,
    gto.proposal_type,
    gto.proposal_created_at,
    gto.decision_at,
    gto.executed_at,
    gto.decision_latency_days,
    gto.execution_latency_days,
    gto.decision_result,
    gto.public_summary,
    gto.evidence_maturity,
    em.label AS evidence_maturity_label,
    gto.metadata
FROM governance_throughput_observation gto
LEFT JOIN evidence_maturity_level em ON em.level = gto.evidence_maturity
WHERE gto.status = 'published'
  AND gto.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(gto.public_summary, '')), '') IS NOT NULL
  AND (
      gto.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = gto.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_capital_provider_utility_summary AS
SELECT
    cpus.id,
    cpus.location_id,
    cpus.farm_id,
    cpus.scenario_name,
    cpus.provider_type,
    cpus.capital_amount_usd,
    cpus.expected_financial_return_usd,
    cpus.expected_public_goods_value_usd,
    cpus.expected_verification_outputs,
    cpus.expected_payback_months,
    cpus.utility_score,
    cpus.public_summary,
    cpus.limitations,
    cpus.evidence_maturity,
    em.label AS evidence_maturity_label,
    cpus.metadata
FROM capital_provider_utility_scenario cpus
LEFT JOIN evidence_maturity_level em ON em.level = cpus.evidence_maturity
WHERE cpus.status = 'published'
  AND cpus.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(cpus.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = cpus.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('capital-efficiency-utility-v1', 'Capital efficiency scenarios, regenerative efficiency observations, governance throughput, and capital-provider utility scenarios', 'schema 036')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
