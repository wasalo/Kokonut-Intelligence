-- 161_delphi.sql
-- Real-time Delphi service: structured expert consensus with roundless,
-- continuously-updated evaluations and live aggregated statistics.
--
-- Design notes:
--   * Real-time Delphi replaces discrete rounds with continuous interaction:
--     panel members may update their evaluation at any time; the statistical
--     group response is recomputed live on every submission.
--   * Anonymity: each member is represented by a pseudonymous display_token.
--   * The facilitator (AI agent or human) builds anonymized live summaries and
--     drafts recommendations; final outcomes require human approval.
--   * Stopping criteria are evaluated continuously (stability / IQR / duration).

BEGIN;

-- ---------------------------------------------------------------------------
-- Study
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delphi_study (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    variation VARCHAR(30) NOT NULL DEFAULT 'real_time'
        CHECK (variation IN ('classic','policy','argument','disaggregative','real_time','fast_track')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','open','closed')),
    facilitator_type VARCHAR(20) NOT NULL DEFAULT 'agent'
        CHECK (facilitator_type IN ('agent','human','hybrid')),
    stopping_criteria JSONB NOT NULL DEFAULT
        '{"max_duration_hours": 720, "stability_pct": 5.0, "min_participants": 3, "iqr_threshold": 1.0}',
    created_by UUID,
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_delphi_study_location ON delphi_study(location_id);
CREATE INDEX IF NOT EXISTS idx_delphi_study_status ON delphi_study(status);

-- ---------------------------------------------------------------------------
-- Panel members
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delphi_panel_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    participant_ref_type VARCHAR(30) NOT NULL
        CHECK (participant_ref_type IN ('farmer_identity','stakeholder_group','guild_contributor','agent')),
    participant_ref_id UUID,
    display_token VARCHAR(64) NOT NULL,
    is_anonymous BOOLEAN DEFAULT TRUE,
    expert_weight DECIMAL(6,4) DEFAULT 1.0 CHECK (expert_weight >= 0),
    role VARCHAR(20) NOT NULL DEFAULT 'expert'
        CHECK (role IN ('expert','policymaker','citizen')),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (study_id, display_token)
);

CREATE INDEX IF NOT EXISTS idx_delphi_panel_study ON delphi_panel_member(study_id);
CREATE INDEX IF NOT EXISTS idx_delphi_panel_token ON delphi_panel_member(display_token);

-- ---------------------------------------------------------------------------
-- Items (questionnaire content)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delphi_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    item_type VARCHAR(20) NOT NULL DEFAULT 'option'
        CHECK (item_type IN ('issue','goal','option')),
    label VARCHAR(255) NOT NULL,
    description TEXT,
    scale VARCHAR(30) NOT NULL DEFAULT 'desirability'
        CHECK (scale IN ('desirability','feasibility_technical','feasibility_political','probability')),
    min_value DECIMAL(8,4) DEFAULT -1.0,
    max_value DECIMAL(8,4) DEFAULT 1.0,
    target_entity_type VARCHAR(50),
    target_entity_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (min_value < max_value)
);

CREATE INDEX IF NOT EXISTS idx_delphi_item_study ON delphi_item(study_id);
CREATE INDEX IF NOT EXISTS idx_delphi_item_target ON delphi_item(target_entity_type, target_entity_id);

-- ---------------------------------------------------------------------------
-- Contributions (real-time, upsertable per member per item)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delphi_contribution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES delphi_item(id) ON DELETE CASCADE,
    panel_member_id UUID NOT NULL REFERENCES delphi_panel_member(id) ON DELETE CASCADE,
    score DECIMAL(8,4) NOT NULL,
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (item_id, panel_member_id)
);

CREATE INDEX IF NOT EXISTS idx_delphi_contrib_study ON delphi_contribution(study_id);
CREATE INDEX IF NOT EXISTS idx_delphi_contrib_item ON delphi_contribution(item_id);

-- ---------------------------------------------------------------------------
-- Consensus snapshot (current, upserted per item)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delphi_consensus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES delphi_item(id) ON DELETE CASCADE,
    median DECIMAL(10,4),
    mean DECIMAL(10,4),
    iqr DECIMAL(10,4),
    stddev DECIMAL(10,4),
    cv DECIMAL(10,4),
    participant_count INTEGER DEFAULT 0,
    weighted_median DECIMAL(10,4),
    consensus_reached BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (item_id)
);

CREATE INDEX IF NOT EXISTS idx_delphi_consensus_study ON delphi_consensus(study_id);
CREATE INDEX IF NOT EXISTS idx_delphi_consensus_item ON delphi_consensus(item_id);

-- ---------------------------------------------------------------------------
-- Consensus history (append-only, for inter-submission stability)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delphi_consensus_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES delphi_item(id) ON DELETE CASCADE,
    median DECIMAL(10,4),
    iqr DECIMAL(10,4),
    participant_count INTEGER DEFAULT 0,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_delphi_history_item ON delphi_consensus_history(item_id, computed_at);

-- ---------------------------------------------------------------------------
-- Recommendation (agent-drafted, human-approved)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delphi_recommendation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    summary TEXT,
    recommendation_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','approved','rejected')),
    created_by UUID,
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_delphi_rec_study ON delphi_recommendation(study_id);
CREATE INDEX IF NOT EXISTS idx_delphi_rec_status ON delphi_recommendation(status);

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_delphi_study_summary AS
SELECT
    ds.id AS study_id,
    ds.location_id,
    ds.title,
    ds.variation,
    ds.status,
    ds.facilitator_type,
    ds.stopping_criteria,
    ds.opened_at,
    ds.closed_at,
    (SELECT COUNT(*) FROM delphi_panel_member dpm WHERE dpm.study_id = ds.id) AS panel_size,
    (SELECT COUNT(*) FROM delphi_item di WHERE di.study_id = ds.id) AS item_count,
    (SELECT COUNT(*) FROM delphi_recommendation dr WHERE dr.study_id = ds.id AND dr.status = 'draft') AS open_recommendations
FROM delphi_study ds;

CREATE OR REPLACE VIEW v_delphi_item_live AS
SELECT
    di.id AS item_id,
    di.study_id,
    di.item_type,
    di.label,
    di.scale,
    di.min_value,
    di.max_value,
    di.target_entity_type,
    di.target_entity_id,
    dc.median,
    dc.iqr,
    dc.stddev,
    dc.cv,
    dc.participant_count,
    dc.weighted_median,
    dc.consensus_reached,
    dc.computed_at
FROM delphi_item di
LEFT JOIN delphi_consensus dc ON dc.item_id = di.id;

CREATE OR REPLACE VIEW v_delphi_consensus_public AS
SELECT
    dc.study_id,
    di.label,
    di.scale,
    dc.median,
    dc.iqr,
    dc.participant_count,
    dc.consensus_reached,
    dc.computed_at
FROM delphi_consensus dc
JOIN delphi_item di ON di.id = dc.item_id
JOIN delphi_study ds ON ds.id = dc.study_id
WHERE ds.status = 'closed'
  AND EXISTS (
      SELECT 1
      FROM delphi_recommendation dr
      WHERE dr.study_id = ds.id AND dr.status = 'approved'
  )
  AND EXISTS (
      SELECT 1
      FROM farm_registry_record fr
      WHERE fr.location_id = ds.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('delphi-v1', 'Real-time Delphi structured expert consensus service', 'schema 161')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;

COMMIT;
