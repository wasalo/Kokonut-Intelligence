-- Migration 201: SWOT Enhancement — TOWS Matrix, Factor Classification, Competitor SWOT
--
-- Tables:
--   swot_factor        – Classified individual SWOT factors
--   towS_strategy      – TOWS matrix strategic options (SO/ST/WO/WT)
--   competitor_swot    – Competitor strengths/weaknesses
--   swot_temporal      – SWOT version snapshots over time
--   swot_action_link   – Links SWOT factors/strategies to actions
--
-- Views:
--   v_strategic_fit
--   v_tows_summary
--   v_competitor_landscape

BEGIN;

-- ============================================================
-- 1. swot_factor — classified SWOT items
-- ============================================================
CREATE TABLE IF NOT EXISTS swot_factor (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    swot_id UUID NOT NULL REFERENCES swot_analysis(id) ON DELETE CASCADE,
    factor_type VARCHAR(20) NOT NULL
        CHECK (factor_type IN ('strength', 'weakness', 'opportunity', 'threat')),
    classification VARCHAR(10) NOT NULL
        CHECK (classification IN ('internal', 'external')),
    category VARCHAR(50) NOT NULL
        CHECK (category IN (
            'human_resources', 'physical_resources', 'financial',
            'activities_processes', 'past_experiences',
            'future_trends', 'economy', 'funding_sources',
            'demographics', 'physical_environment', 'legislation', 'events'
        )),
    description TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    confidence NUMERIC(3,2) DEFAULT 0.5
        CHECK (confidence >= 0 AND confidence <= 1),
    source TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sf_swot ON swot_factor(swot_id);
CREATE INDEX IF NOT EXISTS idx_sf_type ON swot_factor(factor_type);
CREATE INDEX IF NOT EXISTS idx_sf_classification ON swot_factor(classification);
CREATE INDEX IF NOT EXISTS idx_sf_category ON swot_factor(category);

-- ============================================================
-- 2. towS_strategy — TOWS matrix output
-- ============================================================
CREATE TABLE IF NOT EXISTS towS_strategy (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    swot_id UUID NOT NULL REFERENCES swot_analysis(id) ON DELETE CASCADE,
    strategy_type VARCHAR(2) NOT NULL
        CHECK (strategy_type IN ('SO', 'ST', 'WO', 'WT')),
    strategy_label VARCHAR(50) NOT NULL,
    description TEXT,
    factor_pairs JSONB DEFAULT '[]',
    action_items TEXT[],
    priority INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'under_review', 'approved', 'implemented', 'rejected')),
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ts_swot ON towS_strategy(swot_id);
CREATE INDEX IF NOT EXISTS idx_ts_type ON towS_strategy(strategy_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ts_swot_type ON towS_strategy(swot_id, strategy_type);
CREATE INDEX IF NOT EXISTS idx_ts_status ON towS_strategy(status);

-- ============================================================
-- 3. competitor_swot — competitive intelligence
-- ============================================================
CREATE TABLE IF NOT EXISTS competitor_swot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    competitor_name VARCHAR(255) NOT NULL,
    competitor_type VARCHAR(50),
    strengths TEXT[],
    weaknesses TEXT[],
    market_position TEXT,
    competitive_threat_level VARCHAR(20) DEFAULT 'moderate'
        CHECK (competitive_threat_level IN ('low', 'moderate', 'high', 'critical')),
    last_assessed TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cs_location ON competitor_swot(location_id);
CREATE INDEX IF NOT EXISTS idx_cs_threat ON competitor_swot(competitive_threat_level);

-- ============================================================
-- 4. swot_temporal — temporal snapshots
-- ============================================================
CREATE TABLE IF NOT EXISTS swot_temporal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    swot_id UUID NOT NULL REFERENCES swot_analysis(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    strengths_diff JSONB,
    weaknesses_diff JSONB,
    opportunities_diff JSONB,
    threats_diff JSONB,
    change_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(swot_id, version)
);

CREATE INDEX IF NOT EXISTS idx_st_swot ON swot_temporal(swot_id);

-- ============================================================
-- 5. swot_action_link — link to decisions/work items
-- ============================================================
CREATE TABLE IF NOT EXISTS swot_action_link (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    swot_id UUID NOT NULL REFERENCES swot_analysis(id) ON DELETE CASCADE,
    factor_id UUID REFERENCES swot_factor(id) ON DELETE SET NULL,
    strategy_id UUID REFERENCES towS_strategy(id) ON DELETE SET NULL,
    target_type VARCHAR(50) NOT NULL
        CHECK (target_type IN ('decision_policy', 'work_item', 'recommendation', 'manual')),
    target_id UUID,
    action_description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'accepted', 'in_progress', 'completed', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sal_swot ON swot_action_link(swot_id);
CREATE INDEX IF NOT EXISTS idx_sal_factor ON swot_action_link(factor_id);
CREATE INDEX IF NOT EXISTS idx_sal_strategy ON swot_action_link(strategy_id);
CREATE INDEX IF NOT EXISTS idx_sal_target ON swot_action_link(target_type, target_id);

-- ============================================================
-- Views
-- ============================================================

CREATE OR REPLACE VIEW v_strategic_fit AS
SELECT
    sf.swot_id,
    COUNT(*) FILTER (WHERE sf.factor_type = 'strength') AS strength_count,
    COUNT(*) FILTER (WHERE sf.factor_type = 'weakness') AS weakness_count,
    COUNT(*) FILTER (WHERE sf.factor_type = 'opportunity') AS opportunity_count,
    COUNT(*) FILTER (WHERE sf.factor_type = 'threat') AS threat_count,
    CASE
        WHEN COUNT(*) FILTER (WHERE sf.factor_type = 'opportunity') = 0 THEN 0
        ELSE ROUND(
            (COUNT(*) FILTER (WHERE sf.factor_type = 'strength')::NUMERIC /
             COUNT(*) FILTER (WHERE sf.factor_type = 'opportunity')) * 100, 1
        )
    END AS strategic_fit_score
FROM swot_factor sf
GROUP BY sf.swot_id;

CREATE OR REPLACE VIEW v_tows_summary AS
SELECT
    ts.swot_id,
    ts.strategy_type,
    ts.strategy_label,
    ts.description,
    ts.status,
    ts.priority,
    jsonb_array_length(ts.factor_pairs) AS pair_count,
    ts.action_items,
    ts.created_at
FROM towS_strategy ts
ORDER BY ts.swot_id, ts.strategy_type;

CREATE OR REPLACE VIEW v_competitor_landscape AS
SELECT
    cs.location_id,
    l.name AS location_name,
    COUNT(*) AS competitor_count,
    COUNT(*) FILTER (WHERE cs.competitive_threat_level = 'high') AS high_threat_count,
    COUNT(*) FILTER (WHERE cs.competitive_threat_level = 'critical') AS critical_threat_count,
    MAX(cs.last_assessed) AS last_assessed
FROM competitor_swot cs
JOIN location l ON l.id = cs.location_id
GROUP BY cs.location_id, l.name;

COMMIT;
