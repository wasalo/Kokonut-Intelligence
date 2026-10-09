-- ============================================================
-- 210_value_stream_definitions.sql — Value Stream Definitions
-- ============================================================
-- Formal value stream catalog with stages, observations, and
-- performance metrics. Complements the analytics value_stream
-- module with governed definitions.

CREATE TABLE IF NOT EXISTS value_stream_definition (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    stakeholder_type VARCHAR(30)
        CHECK (stakeholder_type IN ('farmer', 'buyer', 'investor', 'regulator', 'community', 'internal')),
    trigger_event TEXT,
    end_state TEXT,
    owner_role VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated', 'draft')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vsd_name ON value_stream_definition(name);

DROP TRIGGER IF EXISTS trg_vsd_updated_at ON value_stream_definition;
CREATE TRIGGER trg_vsd_updated_at
    BEFORE UPDATE ON value_stream_definition
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Value Stream Stages
-- ============================================================
CREATE TABLE IF NOT EXISTS value_stream_stage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id UUID NOT NULL REFERENCES value_stream_definition(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    sequence_order SMALLINT NOT NULL DEFAULT 1,
    process_key VARCHAR(100) REFERENCES process_map(process_key) ON DELETE SET NULL,
    target_lead_time_hours NUMERIC,
    target_fty_pct NUMERIC CHECK (target_fty_pct >= 0 AND target_fty_pct <= 100),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vss_stream ON value_stream_stage(stream_id);
CREATE INDEX IF NOT EXISTS idx_vss_process ON value_stream_stage(process_key);
CREATE UNIQUE INDEX IF NOT EXISTS idx_vss_stream_seq ON value_stream_stage(stream_id, sequence_order);

DROP TRIGGER IF EXISTS trg_vss_updated_at ON value_stream_stage;
CREATE TRIGGER trg_vss_updated_at
    BEFORE UPDATE ON value_stream_stage
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Stage Observations (actual performance data)
-- ============================================================
CREATE TABLE IF NOT EXISTS value_stream_stage_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id UUID NOT NULL REFERENCES value_stream_stage(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actual_lead_time_hours NUMERIC,
    actual_fty_pct NUMERIC CHECK (actual_fty_pct >= 0 AND actual_fty_pct <= 100),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_vsso_stage ON value_stream_stage_observation(stage_id);
CREATE INDEX IF NOT EXISTS idx_vsso_entity ON value_stream_stage_observation(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_vsso_observed ON value_stream_stage_observation(observed_at);

-- ============================================================
-- View: Value stream performance
-- ============================================================
CREATE OR REPLACE VIEW v_value_stream_performance AS
SELECT
    vsd.id AS stream_id,
    vsd.name AS stream_name,
    vsd.stakeholder_type,
    vsd.trigger_event,
    vsd.end_state,
    vsd.status AS stream_status,
    vss.id AS stage_id,
    vss.name AS stage_name,
    vss.sequence_order,
    vss.process_key,
    vss.target_lead_time_hours,
    vss.target_fty_pct,
    (SELECT COUNT(*) FROM value_stream_stage_observation vsso WHERE vsso.stage_id = vss.id) AS observation_count,
    (SELECT ROUND(AVG(vsso.actual_lead_time_hours), 1)
     FROM value_stream_stage_observation vsso WHERE vsso.stage_id = vss.id) AS avg_lead_time_hours,
    (SELECT ROUND(AVG(vsso.actual_fty_pct), 1)
     FROM value_stream_stage_observation vsso WHERE vsso.stage_id = vss.id) AS avg_fty_pct,
    (SELECT MAX(vsso.observed_at)
     FROM value_stream_stage_observation vsso WHERE vsso.stage_id = vss.id) AS last_observed_at
FROM value_stream_definition vsd
JOIN value_stream_stage vss ON vss.stream_id = vsd.id
ORDER BY vsd.name, vss.sequence_order;

-- ============================================================
-- View: Stream-level summary
-- ============================================================
CREATE OR REPLACE VIEW v_value_stream_summary AS
SELECT
    vsd.id AS stream_id,
    vsd.name AS stream_name,
    vsd.stakeholder_type,
    vsd.status,
    COUNT(vss.id) AS stage_count,
    SUM(vss.target_lead_time_hours) AS total_target_lead_time_hours,
    (SELECT ROUND(AVG(vsso.actual_lead_time_hours), 1)
     FROM value_stream_stage_observation vsso
     JOIN value_stream_stage vss2 ON vsso.stage_id = vss2.id
     WHERE vss2.stream_id = vsd.id) AS avg_actual_lead_time_hours,
    (SELECT ROUND(AVG(vsso.actual_fty_pct), 1)
     FROM value_stream_stage_observation vsso
     JOIN value_stream_stage vss2 ON vsso.stage_id = vss2.id
     WHERE vss2.stream_id = vsd.id) AS avg_fty_pct,
    vsd.created_at,
    vsd.updated_at
FROM value_stream_definition vsd
LEFT JOIN value_stream_stage vss ON vss.stream_id = vsd.id
GROUP BY vsd.id, vsd.name, vsd.stakeholder_type, vsd.status, vsd.created_at, vsd.updated_at;

COMMENT ON TABLE value_stream_definition IS 'Formal value stream definitions with stakeholder type and trigger/end state';
COMMENT ON TABLE value_stream_stage IS 'Stages within a value stream, linked to process_map entries';
COMMENT ON TABLE value_stream_stage_observation IS 'Actual performance observations per stage (lead time, FTY)';
COMMENT ON VIEW v_value_stream_performance IS 'Stage-level performance with actual vs target metrics';
COMMENT ON VIEW v_value_stream_summary IS 'Stream-level summary with aggregated lead time and FTY';
