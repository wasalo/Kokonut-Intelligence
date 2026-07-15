-- ============================================================
-- 208_strategy_map.sql — Strategy Map (Balanced Scorecard)
-- ============================================================
-- Links strategic objectives across four BSC perspectives to
-- execution via work_items and tracks initiative progress.

CREATE TABLE IF NOT EXISTS strategy_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(30) NOT NULL DEFAULT 'location'
        CHECK (entity_type IN ('location', 'organization', 'platform')),
    entity_id UUID,
    perspective VARCHAR(30) NOT NULL
        CHECK (perspective IN ('financial', 'customer', 'internal_process', 'learning_growth')),
    objective_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    strategic_theme VARCHAR(100),
    statement TEXT NOT NULL,
    target_value NUMERIC,
    current_value NUMERIC,
    unit VARCHAR(30),
    weight NUMERIC DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 10),
    status VARCHAR(20) NOT NULL DEFAULT 'on_track'
        CHECK (status IN ('on_track', 'at_risk', 'behind', 'achieved', 'not_started')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sm_entity ON strategy_map(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_sm_perspective ON strategy_map(perspective);
CREATE INDEX IF NOT EXISTS idx_sm_theme ON strategy_map(strategic_theme);
CREATE INDEX IF NOT EXISTS idx_sm_status ON strategy_map(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sm_statement_scope
    ON strategy_map (
        entity_type,
        COALESCE(entity_id, '00000000-0000-0000-0000-000000000000'::uuid),
        perspective,
        statement
    );

DROP TRIGGER IF EXISTS trg_sm_updated_at ON strategy_map;
CREATE TRIGGER trg_sm_updated_at
    BEFORE UPDATE ON strategy_map
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Strategy → Capability mapping
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_capability_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_map_id UUID NOT NULL REFERENCES strategy_map(id) ON DELETE CASCADE,
    capability_id UUID NOT NULL REFERENCES business_capability(id) ON DELETE CASCADE,
    contribution_type VARCHAR(20) NOT NULL DEFAULT 'primary'
        CHECK (contribution_type IN ('primary', 'enabling')),
    expected_impact TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_map_id, capability_id)
);

CREATE INDEX IF NOT EXISTS idx_scm_strategy ON strategy_capability_map(strategy_map_id);
CREATE INDEX IF NOT EXISTS idx_scm_capability ON strategy_capability_map(capability_id);

-- ============================================================
-- Strategy Initiatives (execution tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_initiative (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_map_id UUID NOT NULL REFERENCES strategy_map(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    owner VARCHAR(100),
    start_date DATE,
    target_date DATE,
    completion_pct NUMERIC DEFAULT 0 CHECK (completion_pct >= 0 AND completion_pct <= 100),
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'completed', 'cancelled', 'on_hold')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_si_strategy ON strategy_initiative(strategy_map_id);
CREATE INDEX IF NOT EXISTS idx_si_status ON strategy_initiative(status);
CREATE INDEX IF NOT EXISTS idx_si_owner ON strategy_initiative(owner);

DROP TRIGGER IF EXISTS trg_si_updated_at ON strategy_initiative;
CREATE TRIGGER trg_si_updated_at
    BEFORE UPDATE ON strategy_initiative
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- View: Strategy execution dashboard
-- ============================================================
CREATE OR REPLACE VIEW v_strategy_execution AS
SELECT
    sm.id AS strategy_id,
    sm.entity_type,
    sm.entity_id,
    sm.perspective,
    sm.strategic_theme,
    sm.statement AS objective_statement,
    sm.target_value,
    sm.current_value,
    sm.unit,
    sm.weight,
    sm.status AS objective_status,
    CASE
        WHEN sm.target_value IS NOT NULL AND sm.target_value > 0
        THEN ROUND((COALESCE(sm.current_value, 0) / sm.target_value * 100)::numeric, 1)
        ELSE NULL
    END AS progress_pct,
    (SELECT COUNT(*) FROM strategy_initiative si WHERE si.strategy_map_id = sm.id) AS initiative_count,
    (SELECT COUNT(*) FROM strategy_initiative si
     WHERE si.strategy_map_id = sm.id AND si.status = 'completed') AS completed_initiatives,
    (SELECT ROUND(AVG(si.completion_pct), 1)
     FROM strategy_initiative si
     WHERE si.strategy_map_id = sm.id AND si.status = 'in_progress') AS avg_initiative_progress,
    sm.created_at,
    sm.updated_at,
    (SELECT COUNT(*) FROM strategy_capability_map scm WHERE scm.strategy_map_id = sm.id) AS capability_count
FROM strategy_map sm;

COMMENT ON TABLE strategy_map IS 'Balanced Scorecard strategy map: financial, customer, internal_process, learning_growth perspectives';
COMMENT ON TABLE strategy_capability_map IS 'Links strategic objectives to the capabilities required for execution';
COMMENT ON TABLE strategy_initiative IS 'Execution initiatives linked to strategic objectives with work_item tracking';
COMMENT ON VIEW v_strategy_execution IS 'Strategy execution dashboard with progress calculation and initiative rollup';
