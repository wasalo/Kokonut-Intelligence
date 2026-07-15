-- ============================================================
-- 229_stakeholder_decision_controls.sql
-- ============================================================

ALTER TABLE stakeholder_decision ADD COLUMN IF NOT EXISTS approval_actor_type VARCHAR(20) NOT NULL DEFAULT 'human'
    CHECK (approval_actor_type IN ('human', 'agent', 'system'));
ALTER TABLE stakeholder_decision ADD COLUMN IF NOT EXISTS approval_role VARCHAR(80) NOT NULL DEFAULT 'stakeholder_reviewer';
ALTER TABLE stakeholder_decision ADD COLUMN IF NOT EXISTS approval_evidence JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE stakeholder_decision ADD COLUMN IF NOT EXISTS material_harm_review_status VARCHAR(20) NOT NULL DEFAULT 'not_required'
    CHECK (material_harm_review_status IN ('not_required', 'required', 'clear', 'waived', 'blocked'));
ALTER TABLE stakeholder_decision ADD COLUMN IF NOT EXISTS minority_review_status VARCHAR(20) NOT NULL DEFAULT 'not_required'
    CHECK (minority_review_status IN ('not_required', 'required', 'reviewed', 'blocked'));
ALTER TABLE stakeholder_decision ADD COLUMN IF NOT EXISTS independent_reviewed_by UUID REFERENCES party(id) ON DELETE SET NULL;
ALTER TABLE stakeholder_decision ADD COLUMN IF NOT EXISTS independent_reviewed_at TIMESTAMPTZ;

ALTER TABLE stakeholder_decision DROP CONSTRAINT IF EXISTS chk_stakeholder_decision_human_approval;
ALTER TABLE stakeholder_decision ADD CONSTRAINT chk_stakeholder_decision_human_approval CHECK (
    approval_status <> 'approved'
    OR (approved_by_party_id IS NOT NULL AND approval_actor_type = 'human')
);

ALTER TABLE stakeholder_decision DROP CONSTRAINT IF EXISTS chk_stakeholder_decision_review_gates;
ALTER TABLE stakeholder_decision ADD CONSTRAINT chk_stakeholder_decision_review_gates CHECK (
    approval_status <> 'approved'
    OR material_harm_review_status IN ('not_required', 'clear', 'waived')
);

CREATE OR REPLACE FUNCTION enforce_stakeholder_decision_approval()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.approval_status = 'approved' AND NEW.status IN ('approved', 'in_execution') THEN
        IF NEW.approval_actor_type <> 'human' OR NEW.approved_by_party_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM party WHERE id = NEW.approved_by_party_id AND party_type = 'person') THEN
            RAISE EXCEPTION 'stakeholder decisions require an authenticated human approver';
        END IF;
        IF NEW.material_harm_review_status IN ('required', 'blocked') THEN
            RAISE EXCEPTION 'stakeholder decision has unresolved material harm';
        END IF;
        IF NEW.minority_review_status IN ('required', 'blocked') THEN
            RAISE EXCEPTION 'stakeholder decision has unresolved minority review';
        END IF;
        IF EXISTS (
            SELECT 1 FROM stakeholder_decision_participant p
            WHERE p.decision_id = NEW.id
              AND p.party_id = NEW.approved_by_party_id
              AND p.stakeholder_role = 'affected'
              AND p.stakeholder_role <> 'decision_maker'
        ) THEN
            RAISE EXCEPTION 'affected-party participants cannot approve their own stakeholder decision';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_stakeholder_decision_approval ON stakeholder_decision;
CREATE TRIGGER trg_stakeholder_decision_approval
BEFORE INSERT OR UPDATE ON stakeholder_decision
FOR EACH ROW EXECUTE FUNCTION enforce_stakeholder_decision_approval();

DROP VIEW IF EXISTS v_stakeholder_decision_lineage;
CREATE VIEW v_stakeholder_decision_lineage AS
SELECT
    sd.id AS decision_id,
    sd.decision_key,
    sd.title,
    sd.decision_type,
    sd.scope_type,
    sd.scope_id,
    sd.status,
    sd.approval_status,
    sd.approval_actor_type,
    sd.approval_role,
    sd.material_harm_review_status,
    sd.minority_review_status,
    creator.display_name AS created_by_name,
    approver.display_name AS approved_by_name,
    sd.approved_at,
    sd.decision_log_id,
    sd.work_item_id,
    COUNT(DISTINCT sdp.id) AS participant_count,
    COUNT(DISTINCT sdp.id) FILTER (WHERE sdp.participation_status = 'participated') AS participating_count,
    COUNT(DISTINCT sdp.id) FILTER (WHERE sdp.minority_view) AS minority_participant_count,
    COUNT(DISTINCT sdt.id) AS tradeoff_count,
    COUNT(DISTINCT sdt.id) FILTER (WHERE sdt.direction = 'harm' AND NOT sdt.accepted) AS unresolved_harm_count,
    COUNT(DISTINCT sde.id) AS evidence_count,
    COUNT(DISTINCT sde.id) FILTER (WHERE sde.verified) AS verified_evidence_count,
    COUNT(DISTINCT sdo.id) AS outcome_count,
    MAX(sdo.observed_at) AS last_outcome_at
FROM stakeholder_decision sd
LEFT JOIN party creator ON creator.id = sd.created_by_party_id
LEFT JOIN party approver ON approver.id = sd.approved_by_party_id
LEFT JOIN stakeholder_decision_participant sdp ON sdp.decision_id = sd.id
LEFT JOIN stakeholder_decision_tradeoff sdt ON sdt.decision_id = sd.id
LEFT JOIN stakeholder_decision_evidence sde ON sde.decision_id = sd.id
LEFT JOIN stakeholder_decision_outcome sdo ON sdo.decision_id = sd.id
GROUP BY sd.id, sd.decision_key, sd.title, sd.decision_type, sd.scope_type, sd.scope_id,
         sd.status, sd.approval_status, sd.approval_actor_type, sd.approval_role,
         sd.material_harm_review_status, sd.minority_review_status, creator.display_name,
         approver.display_name, sd.approved_at, sd.decision_log_id, sd.work_item_id;
