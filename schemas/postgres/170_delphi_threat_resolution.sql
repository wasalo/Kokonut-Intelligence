BEGIN;

ALTER TABLE delphi_panel_member
    ADD COLUMN IF NOT EXISTS stakeholder_group VARCHAR(100),
    ADD COLUMN IF NOT EXISTS geography_code VARCHAR(100),
    ADD COLUMN IF NOT EXISTS affected_community BOOLEAN,
    ADD COLUMN IF NOT EXISTS lived_experience BOOLEAN,
    ADD COLUMN IF NOT EXISTS expertise_domains TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS conflict_disclosure TEXT,
    ADD COLUMN IF NOT EXISTS consent_status VARCHAR(20) NOT NULL DEFAULT 'pending';

ALTER TABLE delphi_panel_member DROP CONSTRAINT IF EXISTS chk_delphi_panel_consent_status;
ALTER TABLE delphi_panel_member ADD CONSTRAINT chk_delphi_panel_consent_status
    CHECK (consent_status IN ('pending','granted','withdrawn'));

CREATE TABLE IF NOT EXISTS delphi_diversity_target (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    dimension_key VARCHAR(100) NOT NULL,
    category_code VARCHAR(100) NOT NULL,
    minimum_count INTEGER CHECK (minimum_count >= 0),
    minimum_share NUMERIC(5,4) CHECK (minimum_share BETWEEN 0 AND 1),
    rationale TEXT NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (study_id, dimension_key, category_code),
    CHECK (minimum_count IS NOT NULL OR minimum_share IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS delphi_diversity_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    panel_size INTEGER NOT NULL,
    participating_size INTEGER NOT NULL,
    target_results JSONB NOT NULL,
    unmet_targets JSONB NOT NULL,
    diversity_status VARCHAR(30) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (diversity_status IN ('not_configured','insufficient_data','targets_met','targets_partially_met','targets_not_met'))
);

CREATE TABLE IF NOT EXISTS delphi_stopping_evaluation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    item_id UUID REFERENCES delphi_item(id) ON DELETE CASCADE,
    scope VARCHAR(10) NOT NULL,
    outcome VARCHAR(40) NOT NULL,
    consensus_met BOOLEAN NOT NULL,
    participation_met BOOLEAN NOT NULL,
    stability_met BOOLEAN NOT NULL,
    duration_exceeded BOOLEAN NOT NULL,
    completion_met BOOLEAN NOT NULL,
    normalized_iqr NUMERIC(10,6),
    median_shift NUMERIC(10,6),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (scope IN ('item','study')),
    CHECK (outcome IN ('continue','consensus_reached','stable_without_consensus','time_limit_with_consensus','time_limit_without_consensus','insufficient_participation','insufficient_stability_history','incomplete_items','administratively_terminated')),
    CHECK ((scope = 'item' AND item_id IS NOT NULL) OR (scope = 'study' AND item_id IS NULL))
);

CREATE TABLE IF NOT EXISTS delphi_minority_report (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES delphi_study(id) ON DELETE CASCADE,
    item_id UUID REFERENCES delphi_item(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    position_summary TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    implications TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by_panel_member_id UUID REFERENCES delphi_panel_member(id) ON DELETE SET NULL,
    submitted_at TIMESTAMPTZ,
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    verification_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('draft','submitted','verified','published','rejected')),
    CHECK (status NOT IN ('verified','published') OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS threat_forecast_question (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id),
    threat_id UUID REFERENCES threat(id) ON DELETE SET NULL,
    narrative_id UUID REFERENCES threat_narrative(id) ON DELETE SET NULL,
    domain_key VARCHAR(100) NOT NULL,
    question_text TEXT NOT NULL,
    event_definition TEXT NOT NULL,
    resolution_criteria TEXT NOT NULL,
    resolution_source TEXT NOT NULL,
    opens_at TIMESTAMPTZ NOT NULL,
    closes_at TIMESTAMPTZ NOT NULL,
    resolves_by TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (opens_at < closes_at AND closes_at <= resolves_by),
    CHECK (threat_id IS NOT NULL OR narrative_id IS NOT NULL),
    CHECK (status IN ('draft','open','closed','resolved','cancelled','invalid'))
);

ALTER TABLE delphi_item ADD COLUMN IF NOT EXISTS forecast_question_id UUID REFERENCES threat_forecast_question(id);

CREATE TABLE IF NOT EXISTS threat_probability_forecast (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_question_id UUID NOT NULL REFERENCES threat_forecast_question(id) ON DELETE CASCADE,
    source_type VARCHAR(40) NOT NULL,
    source_id UUID,
    probability NUMERIC(8,7) NOT NULL CHECK (probability BETWEEN 0 AND 1),
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    supersedes_id UUID REFERENCES threat_probability_forecast(id),
    methodology_version VARCHAR(50) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (source_type IN ('delphi_member','delphi_unweighted_consensus','delphi_weighted_consensus','analyst','model'))
);

CREATE TABLE IF NOT EXISTS threat_forecast_resolution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_question_id UUID NOT NULL UNIQUE REFERENCES threat_forecast_question(id) ON DELETE RESTRICT,
    outcome NUMERIC(2,1),
    resolution_status VARCHAR(20) NOT NULL,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolution_notes TEXT NOT NULL,
    resolved_by UUID NOT NULL,
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (resolution_status IN ('resolved','cancelled','invalid')),
    CHECK ((resolution_status = 'resolved' AND outcome IN (0,1)) OR (resolution_status IN ('cancelled','invalid') AND outcome IS NULL))
);

CREATE TABLE IF NOT EXISTS threat_forecast_score (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID NOT NULL UNIQUE REFERENCES threat_probability_forecast(id) ON DELETE CASCADE,
    resolution_id UUID NOT NULL REFERENCES threat_forecast_resolution(id) ON DELETE CASCADE,
    brier_score NUMERIC(12,10) NOT NULL CHECK (brier_score BETWEEN 0 AND 1),
    scoring_version VARCHAR(50) NOT NULL,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS delphi_expert_calibration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_member_id UUID NOT NULL REFERENCES delphi_panel_member(id) ON DELETE CASCADE,
    domain_key VARCHAR(100) NOT NULL,
    resolved_forecast_count INTEGER NOT NULL,
    mean_brier_score NUMERIC(12,10),
    baseline_brier_score NUMERIC(12,10),
    brier_skill_score NUMERIC(12,10),
    calibrated_weight NUMERIC(6,4) NOT NULL CHECK (calibrated_weight BETWEEN 0.5 AND 1.5),
    calibration_version VARCHAR(50) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (panel_member_id, domain_key, calibration_version)
);

CREATE INDEX IF NOT EXISTS idx_threat_forecast_question_status ON threat_forecast_question(status, resolves_by);
CREATE INDEX IF NOT EXISTS idx_threat_probability_question ON threat_probability_forecast(forecast_question_id, issued_at);
CREATE INDEX IF NOT EXISTS idx_delphi_stopping_study ON delphi_stopping_evaluation(study_id, evaluated_at);

COMMIT;
