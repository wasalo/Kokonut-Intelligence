-- ============================================================
-- 034_holistic_wellbeing.sql — Cultural context and holistic well-being
-- ============================================================

CREATE TABLE IF NOT EXISTS cultural_context_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    practice_name VARCHAR(255) NOT NULL,
    practice_type VARCHAR(100) NOT NULL,
    stakeholder_group VARCHAR(100),
    language VARCHAR(50),
    description TEXT NOT NULL,
    public_summary TEXT,
    consent_given BOOLEAN DEFAULT FALSE,
    consent_scope VARCHAR(100) DEFAULT 'private_review',
    is_public BOOLEAN DEFAULT FALSE,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
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

CREATE INDEX IF NOT EXISTS idx_cultural_context_location ON cultural_context_record(location_id);
CREATE INDEX IF NOT EXISTS idx_cultural_context_farm ON cultural_context_record(farm_id);
CREATE INDEX IF NOT EXISTS idx_cultural_context_type ON cultural_context_record(practice_type);
CREATE INDEX IF NOT EXISTS idx_cultural_context_language ON cultural_context_record(language);
CREATE INDEX IF NOT EXISTS idx_cultural_context_status ON cultural_context_record(status);
CREATE INDEX IF NOT EXISTS idx_cultural_context_public ON cultural_context_record(is_public, status);

ALTER TABLE cultural_context_record DROP CONSTRAINT IF EXISTS chk_cultural_context_status;
ALTER TABLE cultural_context_record ADD CONSTRAINT chk_cultural_context_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE cultural_context_record DROP CONSTRAINT IF EXISTS chk_cultural_context_type;
ALTER TABLE cultural_context_record ADD CONSTRAINT chk_cultural_context_type CHECK (practice_type IN (
    'traditional_knowledge', 'local_language', 'heritage_species', 'cultural_practice',
    'community_story', 'land_memory', 'education', 'other'
));

ALTER TABLE cultural_context_record DROP CONSTRAINT IF EXISTS chk_cultural_context_public_opt_in;
ALTER TABLE cultural_context_record ADD CONSTRAINT chk_cultural_context_public_opt_in CHECK (
    is_public = FALSE
    OR (
        consent_given = TRUE
        AND consent_scope IN ('public_summary', 'public_quote', 'public_full')
        AND status = 'published'
        AND NULLIF(TRIM(COALESCE(public_summary, '')), '') IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS wellbeing_metric_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    metric_key VARCHAR(255) NOT NULL,
    observation_date DATE NOT NULL,
    stakeholder_group VARCHAR(100),
    language VARCHAR(50),
    score_value NUMERIC(12,4),
    count_value INTEGER,
    text_value TEXT,
    public_summary TEXT,
    source_tables TEXT[] DEFAULT '{}',
    source_record_ids UUID[] DEFAULT '{}',
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

CREATE INDEX IF NOT EXISTS idx_wellbeing_metric_location ON wellbeing_metric_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_wellbeing_metric_farm ON wellbeing_metric_observation(farm_id);
CREATE INDEX IF NOT EXISTS idx_wellbeing_metric_key ON wellbeing_metric_observation(metric_key);
CREATE INDEX IF NOT EXISTS idx_wellbeing_metric_status ON wellbeing_metric_observation(status);
CREATE INDEX IF NOT EXISTS idx_wellbeing_metric_date ON wellbeing_metric_observation(observation_date);

ALTER TABLE wellbeing_metric_observation DROP CONSTRAINT IF EXISTS chk_wellbeing_metric_status;
ALTER TABLE wellbeing_metric_observation ADD CONSTRAINT chk_wellbeing_metric_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE wellbeing_metric_observation DROP CONSTRAINT IF EXISTS chk_wellbeing_metric_value_present;
ALTER TABLE wellbeing_metric_observation ADD CONSTRAINT chk_wellbeing_metric_value_present CHECK (
    score_value IS NOT NULL OR count_value IS NOT NULL OR NULLIF(TRIM(COALESCE(text_value, '')), '') IS NOT NULL
);

CREATE TABLE IF NOT EXISTS participatory_action_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    stakeholder_feedback_id UUID REFERENCES stakeholder_feedback(id) ON DELETE SET NULL,
    metric_proposal_id UUID REFERENCES metric_proposal(id) ON DELETE SET NULL,
    report_snapshot_id UUID REFERENCES report_snapshot(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    action_date DATE NOT NULL,
    stakeholder_group VARCHAR(100),
    action_summary TEXT NOT NULL,
    public_summary TEXT,
    decision_status VARCHAR(50) DEFAULT 'draft',
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_participatory_action_location ON participatory_action_record(location_id);
CREATE INDEX IF NOT EXISTS idx_participatory_action_feedback ON participatory_action_record(stakeholder_feedback_id);
CREATE INDEX IF NOT EXISTS idx_participatory_action_metric ON participatory_action_record(metric_proposal_id);
CREATE INDEX IF NOT EXISTS idx_participatory_action_status ON participatory_action_record(status);

ALTER TABLE participatory_action_record DROP CONSTRAINT IF EXISTS chk_participatory_action_type;
ALTER TABLE participatory_action_record ADD CONSTRAINT chk_participatory_action_type CHECK (action_type IN (
    'feedback_response', 'metric_proposal', 'report_change', 'governance_review',
    'operator_summary', 'community_meeting', 'training_followup', 'other'
));

ALTER TABLE participatory_action_record DROP CONSTRAINT IF EXISTS chk_participatory_action_status;
ALTER TABLE participatory_action_record ADD CONSTRAINT chk_participatory_action_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE participatory_action_record DROP CONSTRAINT IF EXISTS chk_participatory_decision_status;
ALTER TABLE participatory_action_record ADD CONSTRAINT chk_participatory_decision_status CHECK (decision_status IN (
    'draft', 'planned', 'in_progress', 'completed', 'deferred', 'rejected'
));

CREATE OR REPLACE VIEW v_public_cultural_context_summary AS
SELECT
    ccr.id,
    ccr.location_id,
    ccr.farm_id,
    ccr.practice_name,
    ccr.practice_type,
    ccr.stakeholder_group,
    ccr.language,
    ccr.public_summary,
    ccr.evidence_maturity,
    em.label AS evidence_maturity_label,
    ccr.metadata
FROM cultural_context_record ccr
LEFT JOIN evidence_maturity_level em ON em.level = ccr.evidence_maturity
WHERE ccr.is_public = TRUE
  AND ccr.consent_given = TRUE
  AND ccr.status = 'published'
  AND NULLIF(TRIM(COALESCE(ccr.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = ccr.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_wellbeing_metric_summary AS
SELECT
    wmo.id,
    wmo.location_id,
    wmo.farm_id,
    wmo.metric_key,
    md.display_name AS metric_name,
    wmo.observation_date,
    wmo.stakeholder_group,
    wmo.language,
    wmo.score_value,
    wmo.count_value,
    wmo.public_summary,
    wmo.evidence_maturity,
    em.label AS evidence_maturity_label,
    wmo.metadata
FROM wellbeing_metric_observation wmo
LEFT JOIN metric_definition md ON md.metric_key = wmo.metric_key
LEFT JOIN evidence_maturity_level em ON em.level = wmo.evidence_maturity
WHERE wmo.status = 'published'
  AND wmo.evidence_maturity >= 3
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = wmo.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_participatory_governance_summary AS
SELECT
    par.id,
    par.location_id,
    par.farm_id,
    par.action_type,
    par.action_date,
    par.stakeholder_group,
    par.public_summary,
    par.decision_status,
    par.evidence_maturity,
    em.label AS evidence_maturity_label,
    sf.feedback_type,
    sf.sentiment,
    mp.metric_name,
    mp.status AS metric_proposal_status,
    par.metadata
FROM participatory_action_record par
LEFT JOIN stakeholder_feedback sf ON sf.id = par.stakeholder_feedback_id
LEFT JOIN metric_proposal mp ON mp.id = par.metric_proposal_id
LEFT JOIN evidence_maturity_level em ON em.level = par.evidence_maturity
WHERE par.status = 'published'
  AND NULLIF(TRIM(COALESCE(par.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = par.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('holistic-wellbeing-v1', 'Cultural context, holistic well-being metrics, and participatory action traceability', 'schema 034')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
