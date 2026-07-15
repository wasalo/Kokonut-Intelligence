-- Migration 206: Environmental Scanning Workflow
--
-- Tables:
--   env_scan          -- Master scan record with 5-step lifecycle
--   env_scan_step     -- Individual steps (identify/gather/analyze/communicate/decide)
--   env_scan_source   -- Configurable data sources for each scan
--
-- Views:
--   v_env_scan_status      -- Current scan status per location
--   v_env_scan_findings    -- Aggregated findings across scans

BEGIN;

-- ============================================================
-- 1. env_scan -- master scan record
-- ============================================================
CREATE TABLE IF NOT EXISTS env_scan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    scan_type VARCHAR(50) DEFAULT 'full'
        CHECK (scan_type IN ('full', 'quick', 'focused', 'update')),
    current_step INTEGER DEFAULT 1 CHECK (current_step >= 1 AND current_step <= 5),
    completed_steps INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 5,
    summary TEXT,
    key_findings JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '[]',
    period_start DATE,
    period_end DATE,
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'in_progress', 'completed', 'reviewed', 'published')),
    metadata JSONB DEFAULT '{}',
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_es_location ON env_scan(location_id);
CREATE INDEX IF NOT EXISTS idx_es_status ON env_scan(status);

DROP TRIGGER IF EXISTS trg_env_scan_updated_at ON env_scan;
CREATE TRIGGER trg_env_scan_updated_at
    BEFORE UPDATE ON env_scan
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE env_scan IS 'Environmental scan implementing 5-step scanning workflow';

-- ============================================================
-- 2. env_scan_step -- individual steps
-- ============================================================
CREATE TABLE IF NOT EXISTS env_scan_step (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES env_scan(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL CHECK (step_number >= 1 AND step_number <= 5),
    step_name VARCHAR(50) NOT NULL
        CHECK (step_name IN ('identify', 'gather', 'analyze', 'communicate', 'decide')),
    status VARCHAR(50) DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed')),
    data_source JSONB DEFAULT '{}',
    findings TEXT,
    recommendations TEXT,
    evidence_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(scan_id, step_number)
);

CREATE INDEX IF NOT EXISTS idx_ess_scan ON env_scan_step(scan_id);
CREATE INDEX IF NOT EXISTS idx_ess_location ON env_scan_step(location_id);

DROP TRIGGER IF EXISTS trg_env_scan_step_updated_at ON env_scan_step;
CREATE TRIGGER trg_env_scan_step_updated_at
    BEFORE UPDATE ON env_scan_step
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE env_scan_step IS 'Individual steps within an environmental scan';

-- ============================================================
-- 3. env_scan_source -- configurable data sources
-- ============================================================
CREATE TABLE IF NOT EXISTS env_scan_source (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES env_scan(id) ON DELETE CASCADE,
    source_table VARCHAR(100) NOT NULL,
    source_view VARCHAR(100),
    source_description TEXT,
    step_number INTEGER CHECK (step_number >= 1 AND step_number <= 5),
    query_params JSONB DEFAULT '{}',
    last_fetched_at TIMESTAMPTZ,
    record_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_essrc_scan ON env_scan_source(scan_id);

DROP TRIGGER IF EXISTS trg_env_scan_source_updated_at ON env_scan_source;
CREATE TRIGGER trg_env_scan_source_updated_at
    BEFORE UPDATE ON env_scan_source
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE env_scan_source IS 'Configurable data sources for environmental scans';

-- ============================================================
-- 4. v_env_scan_status -- current scan status per location
-- ============================================================
CREATE OR REPLACE VIEW v_env_scan_status AS
SELECT
    es.id AS scan_id,
    es.location_id,
    l.name AS location_name,
    es.title,
    es.scan_type,
    es.current_step,
    es.completed_steps,
    es.total_steps,
    es.status,
    es.created_at,
    es.updated_at,
    CASE
        WHEN es.completed_steps = es.total_steps THEN 'complete'
        WHEN es.completed_steps > 0 THEN 'in_progress'
        ELSE 'not_started'
    END AS progress_status
FROM env_scan es
LEFT JOIN location l ON l.id = es.location_id
ORDER BY es.created_at DESC;

-- ============================================================
-- 5. v_env_scan_findings -- aggregated findings
-- ============================================================
CREATE OR REPLACE VIEW v_env_scan_findings AS
SELECT
    es.id AS scan_id,
    es.location_id,
    l.name AS location_name,
    es.title,
    ess.step_number,
    ess.step_name,
    ess.findings,
    ess.recommendations,
    ess.evidence_count,
    ess.status AS step_status,
    es.status AS scan_status,
    ess.completed_at
FROM env_scan_step ess
JOIN env_scan es ON es.id = ess.scan_id
LEFT JOIN location l ON l.id = es.location_id
WHERE ess.findings IS NOT NULL
ORDER BY es.created_at DESC, ess.step_number;

COMMIT;
