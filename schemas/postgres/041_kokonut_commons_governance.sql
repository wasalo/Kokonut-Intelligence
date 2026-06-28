-- ============================================================
-- 041_kokonut_commons_governance.sql — Anti-capture governance, flexible redistribution, federation, and participatory signals
-- ============================================================

CREATE TABLE IF NOT EXISTS anti_capture_governance_policy (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    policy_name VARCHAR(255) NOT NULL,
    governance_body VARCHAR(255) NOT NULL,
    policy_scope VARCHAR(100) NOT NULL,
    voting_method VARCHAR(100) NOT NULL,
    voting_cap_pct NUMERIC(7,4),
    quadratic_or_conviction_enabled BOOLEAN DEFAULT FALSE,
    one_person_one_vote_enabled BOOLEAN DEFAULT FALSE,
    sybil_resistance_method TEXT,
    worker_or_operator_veto_enabled BOOLEAN DEFAULT FALSE,
    community_veto_enabled BOOLEAN DEFAULT FALSE,
    delegation_limits TEXT,
    enforcement_mode VARCHAR(100) NOT NULL DEFAULT 'offchain_policy',
    policy_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_anti_capture_location ON anti_capture_governance_policy(location_id);
CREATE INDEX IF NOT EXISTS idx_anti_capture_scope ON anti_capture_governance_policy(policy_scope);
CREATE INDEX IF NOT EXISTS idx_anti_capture_status ON anti_capture_governance_policy(status);

ALTER TABLE anti_capture_governance_policy DROP CONSTRAINT IF EXISTS chk_anti_capture_status;
ALTER TABLE anti_capture_governance_policy ADD CONSTRAINT chk_anti_capture_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE anti_capture_governance_policy DROP CONSTRAINT IF EXISTS chk_anti_capture_scope;
ALTER TABLE anti_capture_governance_policy ADD CONSTRAINT chk_anti_capture_scope CHECK (policy_scope IN ('farm', 'guild', 'dao', 'network', 'publication_review', 'other'));

ALTER TABLE anti_capture_governance_policy DROP CONSTRAINT IF EXISTS chk_anti_capture_voting;
ALTER TABLE anti_capture_governance_policy ADD CONSTRAINT chk_anti_capture_voting CHECK (voting_method IN ('one_person_one_vote', 'quadratic', 'conviction', 'token_vote_capped', 'consent', 'consensus', 'hybrid', 'other'));

ALTER TABLE anti_capture_governance_policy DROP CONSTRAINT IF EXISTS chk_anti_capture_values;
ALTER TABLE anti_capture_governance_policy ADD CONSTRAINT chk_anti_capture_values CHECK (
    (voting_cap_pct IS NULL OR voting_cap_pct BETWEEN 0 AND 100)
    AND enforcement_mode IN ('offchain_policy', 'directus_hook', 'smart_contract', 'multisig_policy', 'manual_review', 'other')
);

CREATE TABLE IF NOT EXISTS commons_redistribution_policy (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    policy_name VARCHAR(255) NOT NULL,
    scenario_name VARCHAR(255),
    policy_scope VARCHAR(100) NOT NULL,
    policy_status VARCHAR(50) DEFAULT 'proposed',
    revenue_basis VARCHAR(100) NOT NULL,
    commons_allocation_pct NUMERIC(7,4),
    local_cooperative_allocation_pct NUMERIC(7,4),
    operator_allocation_pct NUMERIC(7,4),
    digital_commons_allocation_pct NUMERIC(7,4),
    reserve_allocation_pct NUMERIC(7,4),
    trigger_conditions TEXT[] DEFAULT '{}',
    enforcement_mode VARCHAR(100) NOT NULL DEFAULT 'offchain_policy',
    audit_cadence VARCHAR(100),
    policy_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_commons_redistribution_location ON commons_redistribution_policy(location_id);
CREATE INDEX IF NOT EXISTS idx_commons_redistribution_scope ON commons_redistribution_policy(policy_scope);
CREATE INDEX IF NOT EXISTS idx_commons_redistribution_status ON commons_redistribution_policy(status, policy_status);

ALTER TABLE commons_redistribution_policy DROP CONSTRAINT IF EXISTS chk_commons_redistribution_status;
ALTER TABLE commons_redistribution_policy ADD CONSTRAINT chk_commons_redistribution_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE commons_redistribution_policy DROP CONSTRAINT IF EXISTS chk_commons_redistribution_policy_status;
ALTER TABLE commons_redistribution_policy ADD CONSTRAINT chk_commons_redistribution_policy_status CHECK (policy_status IN ('proposed', 'active', 'paused', 'superseded', 'rejected'));

ALTER TABLE commons_redistribution_policy DROP CONSTRAINT IF EXISTS chk_commons_redistribution_scope;
ALTER TABLE commons_redistribution_policy ADD CONSTRAINT chk_commons_redistribution_scope CHECK (policy_scope IN ('farm', 'guild', 'dao', 'network', 'scenario', 'other'));

ALTER TABLE commons_redistribution_policy DROP CONSTRAINT IF EXISTS chk_commons_redistribution_values;
ALTER TABLE commons_redistribution_policy ADD CONSTRAINT chk_commons_redistribution_values CHECK (
    revenue_basis IN ('net_profit', 'gross_revenue', 'surplus', 'grant_pool', 'treasury_inflow', 'scenario', 'other')
    AND (commons_allocation_pct IS NULL OR commons_allocation_pct BETWEEN 0 AND 100)
    AND (local_cooperative_allocation_pct IS NULL OR local_cooperative_allocation_pct BETWEEN 0 AND 100)
    AND (operator_allocation_pct IS NULL OR operator_allocation_pct BETWEEN 0 AND 100)
    AND (digital_commons_allocation_pct IS NULL OR digital_commons_allocation_pct BETWEEN 0 AND 100)
    AND (reserve_allocation_pct IS NULL OR reserve_allocation_pct BETWEEN 0 AND 100)
    AND enforcement_mode IN ('offchain_policy', 'smart_contract', 'multisig_policy', 'reporting_policy', 'manual_review', 'other')
);

CREATE TABLE IF NOT EXISTS federation_protocol (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_name VARCHAR(255) NOT NULL,
    target_region VARCHAR(255),
    federation_scope VARCHAR(100) NOT NULL,
    permissionless_forking_enabled BOOLEAN DEFAULT FALSE,
    local_adaptation_rights TEXT,
    mutual_aid_commitments TEXT[] DEFAULT '{}',
    shared_infrastructure TEXT[] DEFAULT '{}',
    onboarding_requirements TEXT[] DEFAULT '{}',
    anti_extractive_safeguards TEXT[] DEFAULT '{}',
    conflict_resolution_path TEXT,
    protocol_status VARCHAR(50) DEFAULT 'draft',
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_federation_scope ON federation_protocol(federation_scope);
CREATE INDEX IF NOT EXISTS idx_federation_status ON federation_protocol(status, protocol_status);

ALTER TABLE federation_protocol DROP CONSTRAINT IF EXISTS chk_federation_status;
ALTER TABLE federation_protocol ADD CONSTRAINT chk_federation_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE federation_protocol DROP CONSTRAINT IF EXISTS chk_federation_scope;
ALTER TABLE federation_protocol ADD CONSTRAINT chk_federation_scope CHECK (federation_scope IN ('farm_network', 'guild_network', 'regional_cluster', 'open_source_framework', 'other'));

ALTER TABLE federation_protocol DROP CONSTRAINT IF EXISTS chk_federation_protocol_status;
ALTER TABLE federation_protocol ADD CONSTRAINT chk_federation_protocol_status CHECK (protocol_status IN ('draft', 'pilot', 'active', 'paused', 'deprecated'));

CREATE TABLE IF NOT EXISTS algorithmic_redistribution_mechanism (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    mechanism_name VARCHAR(255) NOT NULL,
    mechanism_type VARCHAR(100) NOT NULL,
    beneficiary_scope VARCHAR(100) NOT NULL,
    allocation_formula TEXT NOT NULL,
    funding_source VARCHAR(100),
    eligibility_criteria TEXT[] DEFAULT '{}',
    privacy_safeguards TEXT[] DEFAULT '{}',
    implementation_status VARCHAR(50) DEFAULT 'proposed',
    enforcement_mode VARCHAR(100) NOT NULL DEFAULT 'manual_review',
    mechanism_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_algo_redistribution_location ON algorithmic_redistribution_mechanism(location_id);
CREATE INDEX IF NOT EXISTS idx_algo_redistribution_type ON algorithmic_redistribution_mechanism(mechanism_type);
CREATE INDEX IF NOT EXISTS idx_algo_redistribution_status ON algorithmic_redistribution_mechanism(status, implementation_status);

ALTER TABLE algorithmic_redistribution_mechanism DROP CONSTRAINT IF EXISTS chk_algo_redistribution_status;
ALTER TABLE algorithmic_redistribution_mechanism ADD CONSTRAINT chk_algo_redistribution_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE algorithmic_redistribution_mechanism DROP CONSTRAINT IF EXISTS chk_algo_redistribution_type;
ALTER TABLE algorithmic_redistribution_mechanism ADD CONSTRAINT chk_algo_redistribution_type CHECK (mechanism_type IN ('targeted_grant', 'fee_rebate', 'progressive_fee', 'airdrop', 'public_goods_matching', 'operator_support', 'other'));

ALTER TABLE algorithmic_redistribution_mechanism DROP CONSTRAINT IF EXISTS chk_algo_redistribution_scope;
ALTER TABLE algorithmic_redistribution_mechanism ADD CONSTRAINT chk_algo_redistribution_scope CHECK (beneficiary_scope IN ('farm_operator', 'local_cooperative', 'guild_contributor', 'community_steward', 'public_goods_pool', 'other'));

ALTER TABLE algorithmic_redistribution_mechanism DROP CONSTRAINT IF EXISTS chk_algo_redistribution_impl;
ALTER TABLE algorithmic_redistribution_mechanism ADD CONSTRAINT chk_algo_redistribution_impl CHECK (
    implementation_status IN ('proposed', 'pilot', 'active', 'paused', 'completed', 'rejected')
    AND enforcement_mode IN ('manual_review', 'directus_hook', 'smart_contract', 'multisig_policy', 'offchain_policy', 'other')
);

CREATE TABLE IF NOT EXISTS participatory_signal_experiment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_name VARCHAR(255) NOT NULL,
    signal_type VARCHAR(100) NOT NULL,
    governance_scope VARCHAR(100) NOT NULL,
    decision_binding VARCHAR(50) DEFAULT 'advisory',
    experiment_status VARCHAR(50) DEFAULT 'proposed',
    participation_rules TEXT NOT NULL,
    moderation_policy TEXT,
    safety_boundaries TEXT[] DEFAULT '{}',
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_participatory_signal_type ON participatory_signal_experiment(signal_type);
CREATE INDEX IF NOT EXISTS idx_participatory_signal_status ON participatory_signal_experiment(status, experiment_status);

ALTER TABLE participatory_signal_experiment DROP CONSTRAINT IF EXISTS chk_participatory_signal_status;
ALTER TABLE participatory_signal_experiment ADD CONSTRAINT chk_participatory_signal_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE participatory_signal_experiment DROP CONSTRAINT IF EXISTS chk_participatory_signal_type;
ALTER TABLE participatory_signal_experiment ADD CONSTRAINT chk_participatory_signal_type CHECK (signal_type IN ('meme_poll', 'vibes_check', 'sentiment_signal', 'ranked_preference', 'community_story', 'other'));

ALTER TABLE participatory_signal_experiment DROP CONSTRAINT IF EXISTS chk_participatory_signal_values;
ALTER TABLE participatory_signal_experiment ADD CONSTRAINT chk_participatory_signal_values CHECK (
    governance_scope IN ('farm', 'guild', 'dao', 'network', 'publication_review', 'other')
    AND decision_binding IN ('advisory', 'ratification_required', 'nonbinding_research', 'binding_after_review')
    AND experiment_status IN ('proposed', 'pilot', 'active', 'completed', 'paused', 'rejected')
);

CREATE OR REPLACE VIEW v_public_anti_capture_governance_policy AS
SELECT acgp.*, em.label AS evidence_maturity_label
FROM anti_capture_governance_policy acgp
LEFT JOIN evidence_maturity_level em ON em.level = acgp.evidence_maturity
WHERE acgp.status = 'published'
  AND acgp.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(acgp.public_summary, '')), '') IS NOT NULL
  AND (acgp.location_id IS NULL OR EXISTS (SELECT 1 FROM farm_registry_record fr WHERE fr.location_id = acgp.location_id AND fr.status IN ('verified', 'published')));

CREATE OR REPLACE VIEW v_public_commons_redistribution_policy AS
SELECT crp.*, em.label AS evidence_maturity_label
FROM commons_redistribution_policy crp
LEFT JOIN evidence_maturity_level em ON em.level = crp.evidence_maturity
WHERE crp.status = 'published'
  AND crp.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(crp.public_summary, '')), '') IS NOT NULL
  AND (crp.location_id IS NULL OR EXISTS (SELECT 1 FROM farm_registry_record fr WHERE fr.location_id = crp.location_id AND fr.status IN ('verified', 'published')));

CREATE OR REPLACE VIEW v_public_federation_protocol AS
SELECT fp.*, em.label AS evidence_maturity_label
FROM federation_protocol fp
LEFT JOIN evidence_maturity_level em ON em.level = fp.evidence_maturity
WHERE fp.status = 'published'
  AND fp.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(fp.public_summary, '')), '') IS NOT NULL;

CREATE OR REPLACE VIEW v_public_algorithmic_redistribution_mechanism AS
SELECT arm.*, em.label AS evidence_maturity_label
FROM algorithmic_redistribution_mechanism arm
LEFT JOIN evidence_maturity_level em ON em.level = arm.evidence_maturity
WHERE arm.status = 'published'
  AND arm.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(arm.public_summary, '')), '') IS NOT NULL
  AND (arm.location_id IS NULL OR EXISTS (SELECT 1 FROM farm_registry_record fr WHERE fr.location_id = arm.location_id AND fr.status IN ('verified', 'published')));

CREATE OR REPLACE VIEW v_public_participatory_signal_experiment AS
SELECT pse.*, em.label AS evidence_maturity_label
FROM participatory_signal_experiment pse
LEFT JOIN evidence_maturity_level em ON em.level = pse.evidence_maturity
WHERE pse.status = 'published'
  AND pse.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(pse.public_summary, '')), '') IS NOT NULL;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('kokonut-commons-governance-v1', 'Anti-capture governance, flexible redistribution policies, federation protocols, algorithmic redistribution, and participatory signals', 'schema 041')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
