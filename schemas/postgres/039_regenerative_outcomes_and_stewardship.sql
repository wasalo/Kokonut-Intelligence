-- ============================================================
-- 039_regenerative_outcomes_and_stewardship.sql — Grant-facing regenerative outcomes, governance, replication, and stewardship evidence
-- ============================================================

CREATE TABLE IF NOT EXISTS regenerative_outcome_summary (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    summary_name VARCHAR(255) NOT NULL,
    hectares_restored NUMERIC(12,4),
    baseline_species_count INTEGER,
    latest_species_count INTEGER,
    species_diversity_delta NUMERIC(10,4),
    baseline_soil_carbon_t_ha NUMERIC(12,4),
    latest_soil_carbon_t_ha NUMERIC(12,4),
    soil_carbon_delta_t_ha NUMERIC(12,4),
    trees_planted_count INTEGER,
    trees_surviving_count INTEGER,
    tree_survival_rate_pct NUMERIC(8,4),
    regenerative_score NUMERIC(5,2),
    jobs_or_roles_supported_count INTEGER,
    training_hours NUMERIC(12,4),
    beneficiary_count INTEGER,
    evidence_confidence VARCHAR(50),
    methodology_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_regen_outcome_location ON regenerative_outcome_summary(location_id);
CREATE INDEX IF NOT EXISTS idx_regen_outcome_period ON regenerative_outcome_summary(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_regen_outcome_status ON regenerative_outcome_summary(status);

ALTER TABLE regenerative_outcome_summary DROP CONSTRAINT IF EXISTS chk_regen_outcome_status;
ALTER TABLE regenerative_outcome_summary ADD CONSTRAINT chk_regen_outcome_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE regenerative_outcome_summary DROP CONSTRAINT IF EXISTS chk_regen_outcome_confidence;
ALTER TABLE regenerative_outcome_summary ADD CONSTRAINT chk_regen_outcome_confidence CHECK (
    evidence_confidence IS NULL OR evidence_confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')
);

ALTER TABLE regenerative_outcome_summary DROP CONSTRAINT IF EXISTS chk_regen_outcome_values;
ALTER TABLE regenerative_outcome_summary ADD CONSTRAINT chk_regen_outcome_values CHECK (
    period_start <= period_end
    AND (hectares_restored IS NULL OR hectares_restored >= 0)
    AND (baseline_species_count IS NULL OR baseline_species_count >= 0)
    AND (latest_species_count IS NULL OR latest_species_count >= 0)
    AND (trees_planted_count IS NULL OR trees_planted_count >= 0)
    AND (trees_surviving_count IS NULL OR trees_surviving_count >= 0)
    AND (tree_survival_rate_pct IS NULL OR tree_survival_rate_pct BETWEEN 0 AND 100)
    AND (regenerative_score IS NULL OR regenerative_score BETWEEN 0 AND 100)
    AND (jobs_or_roles_supported_count IS NULL OR jobs_or_roles_supported_count >= 0)
    AND (training_hours IS NULL OR training_hours >= 0)
    AND (beneficiary_count IS NULL OR beneficiary_count >= 0)
);

CREATE TABLE IF NOT EXISTS community_governance_mechanism (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    mechanism_name VARCHAR(255) NOT NULL,
    governance_level VARCHAR(100) NOT NULL,
    decision_body VARCHAR(255) NOT NULL,
    decision_method VARCHAR(100) NOT NULL,
    quorum_rule TEXT,
    voting_or_consensus_rights TEXT,
    community_veto_rights TEXT,
    escalation_path TEXT,
    power_distribution_summary TEXT NOT NULL,
    participation_cadence VARCHAR(100),
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

CREATE INDEX IF NOT EXISTS idx_community_governance_location ON community_governance_mechanism(location_id);
CREATE INDEX IF NOT EXISTS idx_community_governance_level ON community_governance_mechanism(governance_level);
CREATE INDEX IF NOT EXISTS idx_community_governance_status ON community_governance_mechanism(status);

ALTER TABLE community_governance_mechanism DROP CONSTRAINT IF EXISTS chk_community_governance_status;
ALTER TABLE community_governance_mechanism ADD CONSTRAINT chk_community_governance_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE community_governance_mechanism DROP CONSTRAINT IF EXISTS chk_community_governance_level;
ALTER TABLE community_governance_mechanism ADD CONSTRAINT chk_community_governance_level CHECK (governance_level IN (
    'farm', 'guild', 'dao', 'network', 'publication_review', 'other'
));

ALTER TABLE community_governance_mechanism DROP CONSTRAINT IF EXISTS chk_community_governance_method;
ALTER TABLE community_governance_mechanism ADD CONSTRAINT chk_community_governance_method CHECK (decision_method IN (
    'consensus', 'consent', 'token_vote', 'multisig', 'steward_review', 'hybrid', 'other'
));

CREATE TABLE IF NOT EXISTS replication_readiness_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    assessment_date DATE NOT NULL,
    target_region VARCHAR(255),
    farm_model VARCHAR(100) NOT NULL,
    readiness_score NUMERIC(5,2),
    ecological_prerequisites TEXT[] DEFAULT '{}',
    cultural_governance_prerequisites TEXT[] DEFAULT '{}',
    infrastructure_prerequisites TEXT[] DEFAULT '{}',
    barriers TEXT[] DEFAULT '{}',
    enablers TEXT[] DEFAULT '{}',
    support_structures TEXT[] DEFAULT '{}',
    minimum_evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    replication_status VARCHAR(50) DEFAULT 'assessment',
    assessment_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_replication_readiness_location ON replication_readiness_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_replication_readiness_region ON replication_readiness_assessment(target_region);
CREATE INDEX IF NOT EXISTS idx_replication_readiness_status ON replication_readiness_assessment(status, replication_status);

ALTER TABLE replication_readiness_assessment DROP CONSTRAINT IF EXISTS chk_replication_readiness_status;
ALTER TABLE replication_readiness_assessment ADD CONSTRAINT chk_replication_readiness_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE replication_readiness_assessment DROP CONSTRAINT IF EXISTS chk_replication_readiness_state;
ALTER TABLE replication_readiness_assessment ADD CONSTRAINT chk_replication_readiness_state CHECK (replication_status IN (
    'assessment', 'not_ready', 'conditional', 'ready_for_pilot', 'ready_for_replication', 'blocked'
));

ALTER TABLE replication_readiness_assessment DROP CONSTRAINT IF EXISTS chk_replication_readiness_score;
ALTER TABLE replication_readiness_assessment ADD CONSTRAINT chk_replication_readiness_score CHECK (
    readiness_score IS NULL OR readiness_score BETWEEN 0 AND 10
);

CREATE TABLE IF NOT EXISTS adaptive_stewardship_review (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    review_date DATE NOT NULL,
    review_period_start DATE NOT NULL,
    review_period_end DATE NOT NULL,
    stewardship_scope VARCHAR(100) NOT NULL,
    review_cadence VARCHAR(100),
    trigger_thresholds TEXT[] DEFAULT '{}',
    observed_triggers TEXT[] DEFAULT '{}',
    corrective_actions TEXT[] DEFAULT '{}',
    action_completion_pct NUMERIC(8,4),
    responsible_role VARCHAR(100),
    funding_continuity_plan TEXT,
    next_review_date DATE,
    review_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_adaptive_stewardship_location ON adaptive_stewardship_review(location_id);
CREATE INDEX IF NOT EXISTS idx_adaptive_stewardship_scope ON adaptive_stewardship_review(stewardship_scope);
CREATE INDEX IF NOT EXISTS idx_adaptive_stewardship_status ON adaptive_stewardship_review(status);

ALTER TABLE adaptive_stewardship_review DROP CONSTRAINT IF EXISTS chk_adaptive_stewardship_status;
ALTER TABLE adaptive_stewardship_review ADD CONSTRAINT chk_adaptive_stewardship_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE adaptive_stewardship_review DROP CONSTRAINT IF EXISTS chk_adaptive_stewardship_scope;
ALTER TABLE adaptive_stewardship_review ADD CONSTRAINT chk_adaptive_stewardship_scope CHECK (stewardship_scope IN (
    'ecological', 'community', 'governance', 'financial', 'land', 'evidence_quality', 'other'
));

ALTER TABLE adaptive_stewardship_review DROP CONSTRAINT IF EXISTS chk_adaptive_stewardship_values;
ALTER TABLE adaptive_stewardship_review ADD CONSTRAINT chk_adaptive_stewardship_values CHECK (
    review_period_start <= review_period_end
    AND (action_completion_pct IS NULL OR action_completion_pct BETWEEN 0 AND 100)
);

CREATE OR REPLACE VIEW v_public_regenerative_outcome_summary AS
SELECT
    ros.id,
    ros.location_id,
    ros.farm_id,
    ros.period_start,
    ros.period_end,
    ros.summary_name,
    ros.hectares_restored,
    ros.baseline_species_count,
    ros.latest_species_count,
    ros.species_diversity_delta,
    ros.baseline_soil_carbon_t_ha,
    ros.latest_soil_carbon_t_ha,
    ros.soil_carbon_delta_t_ha,
    ros.trees_planted_count,
    ros.trees_surviving_count,
    ros.tree_survival_rate_pct,
    ros.regenerative_score,
    ros.jobs_or_roles_supported_count,
    ros.training_hours,
    ros.beneficiary_count,
    ros.evidence_confidence,
    ros.public_summary,
    ros.evidence_maturity,
    em.label AS evidence_maturity_label,
    ros.metadata
FROM regenerative_outcome_summary ros
LEFT JOIN evidence_maturity_level em ON em.level = ros.evidence_maturity
WHERE ros.status = 'published'
  AND ros.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(ros.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = ros.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_community_governance_mechanism AS
SELECT
    cgm.id,
    cgm.location_id,
    cgm.farm_id,
    cgm.mechanism_name,
    cgm.governance_level,
    cgm.decision_body,
    cgm.decision_method,
    cgm.quorum_rule,
    cgm.voting_or_consensus_rights,
    cgm.community_veto_rights,
    cgm.escalation_path,
    cgm.power_distribution_summary,
    cgm.participation_cadence,
    cgm.public_summary,
    cgm.evidence_maturity,
    em.label AS evidence_maturity_label,
    cgm.metadata
FROM community_governance_mechanism cgm
LEFT JOIN evidence_maturity_level em ON em.level = cgm.evidence_maturity
WHERE cgm.status = 'published'
  AND cgm.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(cgm.public_summary, '')), '') IS NOT NULL
  AND (
      cgm.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = cgm.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_replication_readiness_summary AS
SELECT
    rra.id,
    rra.location_id,
    rra.assessment_date,
    rra.target_region,
    rra.farm_model,
    rra.readiness_score,
    rra.ecological_prerequisites,
    rra.cultural_governance_prerequisites,
    rra.infrastructure_prerequisites,
    rra.barriers,
    rra.enablers,
    rra.support_structures,
    rra.minimum_evidence_maturity,
    min_em.label AS minimum_evidence_maturity_label,
    rra.replication_status,
    rra.public_summary,
    rra.evidence_maturity,
    em.label AS evidence_maturity_label,
    rra.metadata
FROM replication_readiness_assessment rra
LEFT JOIN evidence_maturity_level em ON em.level = rra.evidence_maturity
LEFT JOIN evidence_maturity_level min_em ON min_em.level = rra.minimum_evidence_maturity
WHERE rra.status = 'published'
  AND rra.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(rra.public_summary, '')), '') IS NOT NULL;

CREATE OR REPLACE VIEW v_public_adaptive_stewardship_summary AS
SELECT
    asr.id,
    asr.location_id,
    asr.farm_id,
    asr.review_date,
    asr.review_period_start,
    asr.review_period_end,
    asr.stewardship_scope,
    asr.review_cadence,
    asr.trigger_thresholds,
    asr.observed_triggers,
    asr.corrective_actions,
    asr.action_completion_pct,
    asr.responsible_role,
    asr.funding_continuity_plan,
    asr.next_review_date,
    asr.public_summary,
    asr.evidence_maturity,
    em.label AS evidence_maturity_label,
    asr.metadata
FROM adaptive_stewardship_review asr
LEFT JOIN evidence_maturity_level em ON em.level = asr.evidence_maturity
WHERE asr.status = 'published'
  AND asr.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(asr.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = asr.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('regenerative-outcomes-stewardship-v1', 'Grant-facing regenerative outcomes, governance mechanisms, replication readiness, and adaptive stewardship evidence', 'schema 039')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
