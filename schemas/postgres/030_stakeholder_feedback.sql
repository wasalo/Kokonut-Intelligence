-- ============================================================
-- 030_stakeholder_feedback.sql — Stakeholder feedback and consent
-- ============================================================

CREATE TABLE IF NOT EXISTS stakeholder_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    feedback_type VARCHAR(50) NOT NULL,
    stakeholder_group VARCHAR(100) NOT NULL,
    stakeholder_name VARCHAR(255),
    feedback_date DATE NOT NULL,
    feedback_text TEXT NOT NULL,
    feedback_audio_cid TEXT,
    language VARCHAR(50),
    sentiment VARCHAR(20),
    themes JSONB DEFAULT '[]',
    suggested_improvements JSONB DEFAULT '[]',
    harms_or_unintended_consequences TEXT,
    consent_given BOOLEAN DEFAULT FALSE,
    consent_scope VARCHAR(100) DEFAULT 'private_review',
    consent_notes TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_feedback_location ON stakeholder_feedback(location_id);
CREATE INDEX IF NOT EXISTS idx_feedback_farm ON stakeholder_feedback(farm_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON stakeholder_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_group ON stakeholder_feedback(stakeholder_group);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON stakeholder_feedback(status);
CREATE INDEX IF NOT EXISTS idx_feedback_public ON stakeholder_feedback(is_public, status);
CREATE INDEX IF NOT EXISTS idx_feedback_themes ON stakeholder_feedback USING GIN(themes);

ALTER TABLE stakeholder_feedback DROP CONSTRAINT IF EXISTS chk_feedback_lifecycle;
ALTER TABLE stakeholder_feedback ADD CONSTRAINT chk_feedback_lifecycle CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE stakeholder_feedback DROP CONSTRAINT IF EXISTS chk_feedback_type;
ALTER TABLE stakeholder_feedback ADD CONSTRAINT chk_feedback_type CHECK (feedback_type IN (
    'community_need', 'farmer_feedback', 'worker_feedback', 'local_resident_feedback',
    'buyer_feedback', 'partner_feedback', 'advisor_feedback', 'complaint',
    'consent_note', 'harm_or_unintended_consequence', 'suggested_improvement', 'other'
));

ALTER TABLE stakeholder_feedback DROP CONSTRAINT IF EXISTS chk_feedback_sentiment;
ALTER TABLE stakeholder_feedback ADD CONSTRAINT chk_feedback_sentiment CHECK (
    sentiment IS NULL OR sentiment IN ('positive', 'neutral', 'negative', 'mixed', 'unknown')
);

-- Private by default with explicit opt-in before public exposure.
ALTER TABLE stakeholder_feedback DROP CONSTRAINT IF EXISTS chk_feedback_public_opt_in;
ALTER TABLE stakeholder_feedback ADD CONSTRAINT chk_feedback_public_opt_in CHECK (
    is_public = FALSE
    OR (
        consent_given = TRUE
        AND consent_scope IN ('public_summary', 'public_quote', 'public_full')
        AND status = 'published'
        AND NULLIF(TRIM(COALESCE(public_summary, '')), '') IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS stakeholder_feedback_review (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feedback_id UUID NOT NULL REFERENCES stakeholder_feedback(id) ON DELETE CASCADE,
    reviewer_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    review_date TIMESTAMPTZ DEFAULT NOW(),
    action VARCHAR(50) NOT NULL,
    response_text TEXT,
    escalation_level VARCHAR(50),
    due_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_review_feedback ON stakeholder_feedback_review(feedback_id);
CREATE INDEX IF NOT EXISTS idx_feedback_review_action ON stakeholder_feedback_review(action);
CREATE INDEX IF NOT EXISTS idx_feedback_review_due ON stakeholder_feedback_review(due_at);

ALTER TABLE stakeholder_feedback_review DROP CONSTRAINT IF EXISTS chk_feedback_review_action;
ALTER TABLE stakeholder_feedback_review ADD CONSTRAINT chk_feedback_review_action CHECK (action IN (
    'acknowledged', 'needs_info', 'escalated', 'resolved', 'dismissed', 'published_summary'
));

CREATE OR REPLACE VIEW v_public_stakeholder_feedback_summary AS
SELECT
    sf.id,
    sf.location_id,
    sf.farm_id,
    sf.feedback_type,
    sf.stakeholder_group,
    sf.feedback_date,
    sf.sentiment,
    sf.themes,
    sf.public_summary,
    sf.evidence_maturity,
    em.label AS evidence_maturity_label
FROM stakeholder_feedback sf
LEFT JOIN evidence_maturity_level em ON em.level = sf.evidence_maturity
WHERE sf.is_public = TRUE
  AND sf.consent_given = TRUE
  AND sf.status = 'published'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = sf.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('stakeholder-feedback-v1', 'Private-by-default stakeholder feedback, review, and public-safe summary view', 'schema 030')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
