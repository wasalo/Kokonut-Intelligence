-- ============================================================
-- 209_vision_mission.sql — Vision, Mission & Values
-- ============================================================
-- Platform-level strategic anchors with approval workflow.

CREATE TABLE IF NOT EXISTS vision_mission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(30) NOT NULL DEFAULT 'platform'
        CHECK (entity_type IN ('platform', 'location', 'organization')),
    entity_id UUID,
    statement_type VARCHAR(20) NOT NULL
        CHECK (statement_type IN ('vision', 'mission', 'values')),
    statement_text TEXT NOT NULL,
    effective_date DATE DEFAULT CURRENT_DATE,
    review_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'archived')),
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vm_entity ON vision_mission(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_vm_type ON vision_mission(statement_type);
CREATE INDEX IF NOT EXISTS idx_vm_status ON vision_mission(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_vm_statement_version
    ON vision_mission (
        entity_type,
        COALESCE(entity_id, '00000000-0000-0000-0000-000000000000'::uuid),
        statement_type,
        effective_date
    );

DROP TRIGGER IF EXISTS trg_vm_updated_at ON vision_mission;
CREATE TRIGGER trg_vm_updated_at
    BEFORE UPDATE ON vision_mission
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- View: Current active statements
-- ============================================================
CREATE OR REPLACE VIEW v_current_vision_mission AS
SELECT DISTINCT ON (entity_type, entity_id, statement_type)
    id,
    entity_type,
    entity_id,
    statement_type,
    statement_text,
    effective_date,
    review_date,
    status,
    approved_by,
    approved_at,
    created_at,
    updated_at
FROM vision_mission
WHERE status = 'approved'
ORDER BY entity_type, entity_id, statement_type, approved_at DESC;

COMMENT ON TABLE vision_mission IS 'Vision, mission, and values statements with approval workflow';
COMMENT ON VIEW v_current_vision_mission IS 'Currently approved vision/mission/values per entity';
