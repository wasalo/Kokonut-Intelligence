-- ============================================================
-- 231_stakeholder_human_review_gates.sql
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_stakeholder_human_review_gate()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'buyer_verification' AND NEW.status = 'verified' THEN
        IF NEW.verified_by_party_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM party WHERE id = NEW.verified_by_party_id AND party_type = 'person') THEN
            RAISE EXCEPTION 'buyer verification requires an identified human verifier';
        END IF;
    ELSIF TG_TABLE_NAME = 'stewardship_proxy_authority' AND NEW.status = 'active' THEN
        IF NEW.approved_by_party_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM party WHERE id = NEW.approved_by_party_id AND party_type = 'person') THEN
            RAISE EXCEPTION 'active proxy authority requires an identified human approver';
        END IF;
    ELSIF TG_TABLE_NAME = 'stakeholder_minority_view' AND NEW.preserved = FALSE
          AND NULLIF(TRIM(COALESCE(NEW.decision_response, '')), '') IS NULL THEN
        RAISE EXCEPTION 'unpreserved minority views require a documented decision response';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_buyer_verification_human ON buyer_verification;
CREATE TRIGGER trg_buyer_verification_human
BEFORE INSERT OR UPDATE ON buyer_verification
FOR EACH ROW EXECUTE FUNCTION enforce_stakeholder_human_review_gate();

DROP TRIGGER IF EXISTS trg_proxy_authority_human ON stewardship_proxy_authority;
CREATE TRIGGER trg_proxy_authority_human
BEFORE INSERT OR UPDATE ON stewardship_proxy_authority
FOR EACH ROW EXECUTE FUNCTION enforce_stakeholder_human_review_gate();

DROP TRIGGER IF EXISTS trg_minority_view_response ON stakeholder_minority_view;
CREATE TRIGGER trg_minority_view_response
BEFORE INSERT OR UPDATE ON stakeholder_minority_view
FOR EACH ROW EXECUTE FUNCTION enforce_stakeholder_human_review_gate();

CREATE OR REPLACE VIEW v_stakeholder_proxy_authority AS
SELECT spa.id, spa.proxy_party_id, proxy.display_name AS proxy_name,
       spa.steward_party_id, steward.display_name AS steward_name,
       spa.authority_type, spa.basis, spa.scope_type, spa.scope_id,
       spa.status, spa.starts_at, spa.expires_at, approver.display_name AS approved_by_name
FROM stewardship_proxy_authority spa
JOIN party proxy ON proxy.id = spa.proxy_party_id
JOIN party steward ON steward.id = spa.steward_party_id
LEFT JOIN party approver ON approver.id = spa.approved_by_party_id;

COMMENT ON VIEW v_stakeholder_proxy_authority IS 'Proxy authority with explicit steward, scope, basis, and human approval';
