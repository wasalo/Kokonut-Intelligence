-- ============================================================
-- 250_work_selection_claims.sql
-- Instrumented work opportunities and governed self-selection.
-- ============================================================

ALTER TABLE work_item
    ADD COLUMN IF NOT EXISTS work_type VARCHAR(50) NOT NULL DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS estimated_effort_hours NUMERIC(10,2)
        CHECK (estimated_effort_hours IS NULL OR estimated_effort_hours >= 0),
    ADD COLUMN IF NOT EXISTS governance_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS capability_id UUID REFERENCES business_capability(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS selection_mode VARCHAR(20) NOT NULL DEFAULT 'assigned'
        CHECK (selection_mode IN ('assigned', 'self_selected', 'delegated', 'volunteer', 'rotational')),
    ADD COLUMN IF NOT EXISTS autonomy_level VARCHAR(20) NOT NULL DEFAULT 'guided'
        CHECK (autonomy_level IN ('guided', 'bounded', 'autonomous')),
    ADD COLUMN IF NOT EXISTS skill_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS allocation_status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (allocation_status IN ('open', 'claimed', 'allocated', 'paused', 'closed')),
    ADD COLUMN IF NOT EXISTS assignee_party_id UUID REFERENCES party(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_work_item_selection
    ON work_item(selection_mode, allocation_status, status);
CREATE INDEX IF NOT EXISTS idx_work_item_governance_role
    ON work_item(governance_role_id, allocation_status);
CREATE INDEX IF NOT EXISTS idx_work_item_capability
    ON work_item(capability_id, allocation_status);
CREATE INDEX IF NOT EXISTS idx_work_item_assignee_party
    ON work_item(assignee_party_id, status);

CREATE TABLE IF NOT EXISTS work_item_claim (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
    claimant_party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    claimant_role_id UUID REFERENCES governance_role(id) ON DELETE SET NULL,
    proposed_effort_hours NUMERIC(10,2) CHECK (proposed_effort_hours IS NULL OR proposed_effort_hours >= 0),
    capability_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'accepted', 'rejected', 'withdrawn')),
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    decision_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (work_item_id, claimant_party_id),
    CHECK (status NOT IN ('accepted', 'rejected') OR reviewed_by_party_id IS NOT NULL),
    CHECK (status NOT IN ('accepted', 'rejected') OR reviewed_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_work_item_claim_item
    ON work_item_claim(work_item_id, status);
CREATE INDEX IF NOT EXISTS idx_work_item_claimant
    ON work_item_claim(claimant_party_id, status);

CREATE TABLE IF NOT EXISTS work_item_selection_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
    claim_id UUID REFERENCES work_item_claim(id) ON DELETE SET NULL,
    actor_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN ('opened', 'claimed', 'accepted', 'rejected', 'withdrawn', 'allocated', 'rebalanced')),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_work_item_selection_event_item
    ON work_item_selection_event(work_item_id, created_at);

CREATE OR REPLACE VIEW v_work_opportunity_queue AS
SELECT
    wi.id AS work_item_id,
    wi.organization_id,
    wi.location_id,
    wi.title,
    wi.description,
    wi.work_type,
    wi.priority,
    wi.status,
    wi.selection_mode,
    wi.autonomy_level,
    wi.estimated_effort_hours,
    wi.governance_role_id,
    gr.role_key,
    wi.capability_id,
    bc.name AS capability_name,
    wi.skill_requirements,
    wi.allocation_status,
    COUNT(wic.id) FILTER (WHERE wic.status = 'proposed') AS open_claim_count,
    COUNT(wic.id) FILTER (WHERE wic.status = 'accepted') AS accepted_claim_count,
    wi.due_at,
    wi.sla_at
FROM work_item wi
LEFT JOIN governance_role gr ON gr.id = wi.governance_role_id
LEFT JOIN business_capability bc ON bc.id = wi.capability_id
LEFT JOIN work_item_claim wic ON wic.work_item_id = wi.id
WHERE wi.selection_mode <> 'assigned'
  AND wi.allocation_status IN ('open', 'claimed')
  AND wi.status NOT IN ('done', 'cancelled')
GROUP BY wi.id, wi.organization_id, wi.location_id, wi.title, wi.description,
         wi.work_type, wi.priority, wi.status, wi.selection_mode,
         wi.autonomy_level, wi.estimated_effort_hours, wi.governance_role_id,
         gr.role_key, wi.capability_id, bc.name, wi.skill_requirements,
         wi.allocation_status, wi.due_at, wi.sla_at;

DROP TRIGGER IF EXISTS trg_work_item_claim_updated_at ON work_item_claim;
CREATE TRIGGER trg_work_item_claim_updated_at
    BEFORE UPDATE ON work_item_claim
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE work_item_claim IS 'Governed claim by a party to self-select or volunteer for an instrumented work opportunity';
COMMENT ON TABLE work_item_selection_event IS 'Append-only audit trail for autonomous work selection and allocation decisions';
COMMENT ON VIEW v_work_opportunity_queue IS 'Open work opportunities with role, capability, and claim context';
