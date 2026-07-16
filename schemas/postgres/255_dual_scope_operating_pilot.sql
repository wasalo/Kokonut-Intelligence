-- ============================================================
-- 255_dual_scope_operating_pilot.sql
-- Formal boundary between internal operations and Adelphi field work.
-- ============================================================

CREATE TABLE IF NOT EXISTS operating_pilot_scope (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type VARCHAR(20) NOT NULL UNIQUE CHECK (scope_type IN ('internal', 'adelphi')),
    scope_key VARCHAR(120) NOT NULL UNIQUE,
    scope_id UUID NOT NULL,
    governance_circle_id UUID REFERENCES governance_circle(id) ON DELETE SET NULL,
    authority_boundary TEXT NOT NULL,
    data_boundary TEXT NOT NULL,
    escalation_policy TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'active', 'paused', 'retired')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'active' OR approved_by_party_id IS NOT NULL),
    CHECK (status <> 'active' OR approved_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_operating_pilot_scope_id
    ON operating_pilot_scope(scope_id, status);

CREATE OR REPLACE VIEW v_operating_pilot_registry AS
SELECT ops.scope_type, ops.scope_key, ops.scope_id, ops.status,
       ops.authority_boundary, ops.data_boundary, ops.escalation_policy,
       gc.circle_key, gc.name AS circle_name,
       ops.approved_at
FROM operating_pilot_scope ops
LEFT JOIN governance_circle gc ON gc.id = ops.governance_circle_id;

DROP TRIGGER IF EXISTS trg_operating_pilot_scope_updated_at ON operating_pilot_scope;
CREATE TRIGGER trg_operating_pilot_scope_updated_at BEFORE UPDATE ON operating_pilot_scope
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE operating_pilot_scope IS 'Explicit operating boundary for the internal Kokonut and Adelphi field pilots';
