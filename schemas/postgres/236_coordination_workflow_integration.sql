-- ============================================================
-- 236_coordination_workflow_integration.sql
-- ============================================================

ALTER TABLE coordination_alliance
    ADD COLUMN IF NOT EXISTS stakeholder_decision_id UUID REFERENCES stakeholder_decision(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS cooperative_proposal_id UUID REFERENCES cooperative_proposal(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_coord_alliance_decision
    ON coordination_alliance(stakeholder_decision_id);
CREATE INDEX IF NOT EXISTS idx_coord_alliance_proposal
    ON coordination_alliance(cooperative_proposal_id);

DROP TRIGGER IF EXISTS trg_lt_coordination_alliance ON coordination_alliance;
CREATE TRIGGER trg_lt_coordination_alliance
    AFTER UPDATE OF status ON coordination_alliance
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

COMMENT ON COLUMN coordination_alliance.stakeholder_decision_id IS 'Governed stakeholder decision supporting alliance approval or material change';
COMMENT ON COLUMN coordination_alliance.cooperative_proposal_id IS 'Cooperative proposal or motion supporting alliance approval where applicable';
