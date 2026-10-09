-- ============================================================
-- 283_strategy_foresight_frame.sql
-- Unified strategic foresight framing and input integration.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_foresight_frame (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL UNIQUE REFERENCES strategy_plan(id) ON DELETE CASCADE,
    focal_question TEXT NOT NULL,
    decision_question TEXT NOT NULL,
    system_boundary TEXT NOT NULL,
    geographic_boundary TEXT,
    stakeholder_boundary TEXT,
    time_horizon_start DATE NOT NULL,
    time_horizon_end DATE NOT NULL,
    method VARCHAR(60) NOT NULL DEFAULT 'integrated_scan_scenario_review',
    baseline_summary TEXT,
    known_blind_spots TEXT,
    visibility VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'limited', 'public')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'retired')),
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (time_horizon_end >= time_horizon_start)
);

CREATE TABLE IF NOT EXISTS strategy_foresight_driver (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    frame_id UUID NOT NULL REFERENCES strategy_foresight_frame(id) ON DELETE CASCADE,
    driver_type VARCHAR(30) NOT NULL CHECK (driver_type IN ('trend', 'driver', 'predetermined_element', 'critical_uncertainty', 'wildcard', 'opportunity')),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    time_to_impact VARCHAR(30),
    impact_level VARCHAR(20) CHECK (impact_level IS NULL OR impact_level IN ('low', 'medium', 'high', 'critical')),
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate'
        CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    reversibility VARCHAR(30),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'validated', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_foresight_input (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    frame_id UUID NOT NULL REFERENCES strategy_foresight_frame(id) ON DELETE CASCADE,
    source_type VARCHAR(40) NOT NULL CHECK (source_type IN (
        'threat_signal', 'competitive_signal', 'pestel_factor', 'swot_factor',
        'forecast_scenario', 'delphi_study', 'backcast_plan', 'stakeholder_feedback',
        'environmental_scan', 'scenario_narrative', 'external_document'
    )),
    source_id UUID,
    source_ref TEXT,
    input_role VARCHAR(30) NOT NULL CHECK (input_role IN ('scan', 'driver', 'uncertainty', 'evidence', 'stakeholder_view')),
    interpretation TEXT,
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate'
        CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (source_id IS NOT NULL OR NULLIF(BTRIM(source_ref), '') IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_foresight_input_identity
    ON strategy_foresight_input(frame_id, source_type, COALESCE(source_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(source_ref, ''), input_role);
CREATE INDEX IF NOT EXISTS idx_strategy_foresight_driver_frame
    ON strategy_foresight_driver(frame_id, driver_type, status);
CREATE INDEX IF NOT EXISTS idx_strategy_foresight_input_frame
    ON strategy_foresight_input(frame_id, input_role, source_type);

DROP TRIGGER IF EXISTS trg_strategy_foresight_frame_updated_at ON strategy_foresight_frame;
CREATE TRIGGER trg_strategy_foresight_frame_updated_at
    BEFORE UPDATE ON strategy_foresight_frame
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_foresight_frame IS 'Decision-focused strategic foresight frame connecting alternative futures inputs to a strategy plan';
COMMENT ON TABLE strategy_foresight_driver IS 'Structured trends, drivers, predetermined elements, critical uncertainties, wildcards, and opportunities';
COMMENT ON TABLE strategy_foresight_input IS 'Typed integration links to existing scanning, scenario, consultation, and backcasting records';
