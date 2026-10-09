-- ============================================================
-- 261_strategy_governance_reporting.sql
-- Scope-dependent governance links for strategy approval.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_governance_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    record_type VARCHAR(40) NOT NULL CHECK (record_type IN ('governance_circle', 'stakeholder_decision', 'governance_proposal', 'stakeholder_grievance')),
    record_id UUID NOT NULL,
    relationship VARCHAR(30) NOT NULL CHECK (relationship IN ('approval', 'consultation', 'constraint', 'escalation', 'implementation')),
    required BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'linked'
        CHECK (status IN ('linked', 'approved', 'rejected', 'superseded')),
    note TEXT,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_plan_id, record_type, record_id, relationship)
);

CREATE INDEX IF NOT EXISTS idx_strategy_governance_plan
    ON strategy_governance_link(strategy_plan_id, relationship, status);
CREATE INDEX IF NOT EXISTS idx_strategy_governance_record
    ON strategy_governance_link(record_type, record_id, status);

COMMENT ON TABLE strategy_governance_link IS 'Links strategy plans to scope-appropriate governance circles, stakeholder decisions, proposals, and constraints';
