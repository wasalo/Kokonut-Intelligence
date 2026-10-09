-- ============================================================
-- 230_stakeholder_public_safety.sql
-- ============================================================

ALTER TABLE nature_stewardship_obligation ADD COLUMN IF NOT EXISTS public_summary TEXT;
ALTER TABLE nature_stewardship_obligation ADD COLUMN IF NOT EXISTS public_evidence JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE nature_stewardship_obligation ADD COLUMN IF NOT EXISTS limitations TEXT;
ALTER TABLE party_trust_evidence ADD COLUMN IF NOT EXISTS audience VARCHAR(20) NOT NULL DEFAULT 'internal'
    CHECK (audience IN ('private', 'internal', 'public'));

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'v_public_ecological_stewardship' AND column_name = 'evidence'
    ) THEN
        ALTER VIEW v_public_ecological_stewardship RENAME COLUMN evidence TO public_evidence;
    END IF;
END;
$$;
CREATE OR REPLACE VIEW v_public_ecological_stewardship AS
SELECT o.id AS obligation_id, o.proxy_party_id, p.display_name AS proxy_name,
       o.title, o.obligation_type, o.metric_key, o.target_value, o.target_unit,
       o.target_date, o.status, o.public_evidence,
       COALESCE(o.limitations, 'Proxy interests are documented ecological obligations; no consent or vote is claimed.') AS limitation
FROM nature_stewardship_obligation o
JOIN party p ON p.id = o.proxy_party_id
WHERE o.status IN ('approved', 'in_progress', 'met')
  AND p.privacy_level = 'public'
  AND COALESCE(o.evidence_maturity, 0) >= 4
  AND NULLIF(TRIM(COALESCE(o.public_summary, '')), '') IS NOT NULL;

CREATE OR REPLACE VIEW v_public_stakeholder_representation AS
SELECT activity_type, activity_id, invited_count, participated_count,
       participation_rate_pct, contribution_rate_pct, minority_view_count,
       minority_view_preserved_count
FROM v_stakeholder_representation_metrics
WHERE invited_count >= 5
  AND NOT EXISTS (
      SELECT 1 FROM stakeholder_participation sp
      WHERE sp.activity_type = v_stakeholder_representation_metrics.activity_type
        AND sp.activity_id = v_stakeholder_representation_metrics.activity_id
        AND sp.invitation_status = 'attended'
        AND sp.party_id IS NOT NULL
        AND sp.consent_checked = FALSE
  );

CREATE OR REPLACE VIEW v_stakeholder_cockpit_internal AS
SELECT
    (SELECT COUNT(*) FROM party WHERE status = 'active') AS active_party_count,
    (SELECT COUNT(*) FROM party_relationship WHERE status = 'active') AS active_relationship_count,
    (SELECT COUNT(*) FROM stakeholder_interest WHERE status NOT IN ('met', 'retired')) AS open_interest_count,
    (SELECT COUNT(*) FROM stakeholder_engagement_plan WHERE status IN ('draft', 'active')) AS active_engagement_plan_count,
    (SELECT COUNT(*) FROM v_stakeholder_commitment_health WHERE is_overdue) AS overdue_commitment_count,
    (SELECT COUNT(*) FROM stakeholder_grievance_case WHERE status NOT IN ('closed', 'rejected', 'dismissed')) AS open_grievance_count,
    (SELECT COUNT(*) FROM stakeholder_decision WHERE status IN ('submitted', 'approved', 'in_execution')) AS active_decision_count,
    (SELECT COUNT(*) FROM stakeholder_decision_tradeoff WHERE direction IN ('harm', 'risk') AND NOT accepted) AS unresolved_harm_count,
    (SELECT COUNT(*) FROM relationship_risk_indicator WHERE status IN ('open', 'monitoring')) AS open_relationship_risk_count,
    (SELECT COUNT(*) FROM buyer_verification WHERE status = 'pending') AS pending_buyer_verification_count,
    (SELECT COUNT(*) FROM party_trust_evidence WHERE correction_status = 'requested' OR appeal_status = 'open') AS contested_trust_evidence_count,
    (SELECT COUNT(*) FROM nature_stewardship_obligation WHERE status IN ('proposed', 'in_progress', 'breached')) AS stewardship_action_count,
    (SELECT COUNT(*) FROM value_stream_stakeholder_outcome WHERE status IN ('draft', 'active')) AS unverified_value_stream_outcome_count,
    NOW() AS generated_at;

CREATE OR REPLACE VIEW v_public_stakeholder_trust AS
SELECT p.id AS party_id, p.display_name, p.party_type,
       COUNT(e.id) FILTER (WHERE e.status = 'active') AS evidence_count,
       COUNT(e.id) FILTER (WHERE e.status = 'active' AND e.direction = 'supporting') AS supporting_evidence_count,
       COUNT(r.id) FILTER (WHERE r.status IN ('open', 'monitoring')) AS open_risk_count,
       'Trust information is aggregated and advisory; inspect governed evidence before any decision.' AS limitation
FROM party p
LEFT JOIN party_trust_evidence e ON e.subject_party_id = p.id AND e.audience = 'public'
LEFT JOIN relationship_risk_indicator r ON r.subject_party_id = p.id
WHERE p.privacy_level = 'public'
GROUP BY p.id, p.display_name, p.party_type;
