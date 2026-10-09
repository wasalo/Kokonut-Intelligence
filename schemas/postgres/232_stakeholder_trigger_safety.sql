-- ============================================================
-- 232_stakeholder_trigger_safety.sql
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_stakeholder_consent_transition()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    plan_record RECORD;
    new_status TEXT := to_jsonb(NEW)->>'status';
    new_is_public BOOLEAN := COALESCE((to_jsonb(NEW)->>'is_public')::BOOLEAN, FALSE);
BEGIN
    IF TG_TABLE_NAME = 'stakeholder_feedback'
       AND (new_status = 'published' OR new_is_public = TRUE) THEN
        IF NEW.party_id IS NULL
           OR NOT stakeholder_has_effective_consent(
               NEW.party_id, 'stakeholder_feedback',
               CASE WHEN new_is_public THEN 'public_summary' ELSE 'stakeholder_feedback_review' END,
               'location', NEW.location_id, 'system'
           ) THEN
            RAISE EXCEPTION 'canonical consent is required before publishing stakeholder feedback';
        END IF;
        NEW.canonical_consent_event_id := COALESCE(
            NEW.canonical_consent_event_id,
            (SELECT c.consent_event_id
             FROM v_effective_stakeholder_consent c
             WHERE c.party_id = NEW.party_id
               AND c.data_category = 'stakeholder_feedback'
               AND c.purpose = CASE WHEN new_is_public THEN 'public_summary' ELSE 'stakeholder_feedback_review' END
               AND c.consented = TRUE
             ORDER BY c.effective_at DESC LIMIT 1)
        );
    ELSIF TG_TABLE_NAME = 'stakeholder_touchpoint' AND new_status = 'completed' THEN
        SELECT p.* INTO plan_record
        FROM stakeholder_engagement_plan p
        WHERE p.id = NEW.plan_id;
        IF plan_record.stakeholder_party_id IS NULL
           OR NOT stakeholder_has_effective_consent(
               plan_record.stakeholder_party_id, 'stakeholder_engagement', NEW.purpose,
               plan_record.scope_type, plan_record.scope_id, 'system'
           ) THEN
            RAISE EXCEPTION 'canonical consent is required before completing stakeholder touchpoint';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_stakeholder_human_review_gate()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    new_status TEXT := to_jsonb(NEW)->>'status';
    new_preserved BOOLEAN := COALESCE((to_jsonb(NEW)->>'preserved')::BOOLEAN, TRUE);
BEGIN
    IF TG_TABLE_NAME = 'buyer_verification' AND new_status = 'verified' THEN
        IF NEW.verified_by_party_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM party WHERE id = NEW.verified_by_party_id AND party_type = 'person') THEN
            RAISE EXCEPTION 'buyer verification requires an identified human verifier';
        END IF;
    ELSIF TG_TABLE_NAME = 'stewardship_proxy_authority' AND new_status = 'active' THEN
        IF NEW.approved_by_party_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM party WHERE id = NEW.approved_by_party_id AND party_type = 'person') THEN
            RAISE EXCEPTION 'active proxy authority requires an identified human approver';
        END IF;
    ELSIF TG_TABLE_NAME = 'stakeholder_minority_view' AND new_preserved = FALSE
          AND NULLIF(TRIM(COALESCE(NEW.decision_response, '')), '') IS NULL THEN
        RAISE EXCEPTION 'unpreserved minority views require a documented decision response';
    END IF;
    RETURN NEW;
END;
$$;
