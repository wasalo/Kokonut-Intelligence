-- ============================================================
-- 233_stakeholder_approval_integration.sql
-- ============================================================

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
        IF EXISTS (
            SELECT 1 FROM stakeholder_minority_view mv
            WHERE mv.activity_type = 'decision' AND mv.activity_id = NEW.id
              AND mv.preserved = FALSE
              AND NULLIF(TRIM(COALESCE(mv.decision_response, '')), '') IS NULL
        ) THEN
            RAISE EXCEPTION 'stakeholder decision has an unaddressed minority view';
        END IF;
        IF EXISTS (SELECT 1 FROM nature_decision_impact ndi WHERE ndi.decision_id = NEW.id)
           AND NOT EXISTS (
               SELECT 1 FROM nature_decision_impact ndi
               JOIN stewardship_proxy_authority spa ON spa.proxy_party_id = ndi.proxy_party_id
               WHERE ndi.decision_id = NEW.id AND spa.status = 'active'
                 AND (spa.scope_type = 'network' OR (spa.scope_type = NEW.scope_type AND spa.scope_id IS NOT DISTINCT FROM NEW.scope_id))
           ) THEN
            RAISE EXCEPTION 'nature or future-generation impacts require active proxy authority';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_linked_decision_log_approval()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.approval_status = 'approved' AND EXISTS (
        SELECT 1 FROM stakeholder_decision sd WHERE sd.decision_log_id = NEW.id
    ) THEN
        IF NEW.approved_by IS NULL OR NOT EXISTS (
            SELECT 1 FROM party WHERE id::text = NEW.approved_by AND party_type = 'person'
        ) THEN
            RAISE EXCEPTION 'linked stakeholder decision logs require an authorized human party approver';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_linked_decision_log_approval ON decision_log;
CREATE TRIGGER trg_linked_decision_log_approval
BEFORE INSERT OR UPDATE ON decision_log
FOR EACH ROW EXECUTE FUNCTION enforce_linked_decision_log_approval();
