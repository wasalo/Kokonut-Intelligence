-- ============================================================
-- 225_stakeholder_cockpit.sql - Unified stakeholder cockpit views
-- ============================================================

CREATE OR REPLACE VIEW v_stakeholder_cockpit_internal AS
SELECT
    (SELECT COUNT(*) FROM party WHERE status = 'active') AS active_party_count,
    (SELECT COUNT(*) FROM party_relationship WHERE status = 'active') AS active_relationship_count,
    (SELECT COUNT(*) FROM stakeholder_interest WHERE status NOT IN ('met', 'retired')) AS open_interest_count,
    (SELECT COUNT(*) FROM stakeholder_engagement_plan WHERE status IN ('draft', 'active')) AS active_engagement_plan_count,
    (SELECT COUNT(*) FROM v_stakeholder_commitment_health WHERE is_overdue) AS overdue_commitment_count,
    (SELECT COUNT(*) FROM stakeholder_grievance_case WHERE status NOT IN ('closed', 'rejected')) AS open_grievance_count,
    (SELECT COUNT(*) FROM stakeholder_decision WHERE status IN ('submitted', 'approved', 'in_execution')) AS active_decision_count,
    (SELECT COUNT(*) FROM stakeholder_decision_tradeoff WHERE direction IN ('harm', 'risk') AND NOT accepted) AS unresolved_harm_count,
    (SELECT COUNT(*) FROM relationship_risk_indicator WHERE status IN ('open', 'monitoring')) AS open_relationship_risk_count,
    (SELECT COUNT(*) FROM buyer_verification WHERE status = 'pending') AS pending_buyer_verification_count,
    (SELECT COUNT(*) FROM party_trust_evidence WHERE correction_status = 'requested' OR appeal_status = 'open') AS contested_trust_evidence_count,
    (SELECT COUNT(*) FROM nature_stewardship_obligation WHERE status IN ('proposed', 'in_progress', 'breached')) AS stewardship_action_count,
    (SELECT COUNT(*) FROM value_stream_stakeholder_outcome WHERE status IN ('draft', 'active')) AS unverified_value_stream_outcome_count,
    NOW() AS generated_at;

CREATE OR REPLACE VIEW v_public_stakeholder_cockpit AS
SELECT
    (SELECT COUNT(*) FROM party WHERE status = 'active' AND privacy_level = 'public') AS public_party_count,
    (SELECT COUNT(*) FROM v_public_stakeholder_representation) AS representation_summary_count,
    (SELECT COUNT(*) FROM stakeholder_outcome WHERE status IN ('verified', 'published') AND evidence_maturity >= 4) AS verified_outcome_count,
    (SELECT COUNT(*) FROM impact_claim WHERE status = 'published' AND evidence_maturity >= 4) AS verified_impact_claim_count,
    (SELECT COUNT(*) FROM stakeholder_distribution WHERE status IN ('verified', 'published')) AS verified_distribution_count,
    (SELECT COUNT(*) FROM v_public_ecological_stewardship) AS ecological_stewardship_count,
    (SELECT COUNT(*) FROM stakeholder_feedback WHERE status = 'published' AND consent_given = TRUE AND is_public = TRUE) AS published_feedback_count,
    'Public cockpit excludes private consent, protected grievances, unresolved decision lineage, contested trust evidence, and small-group participation.' AS privacy_limitation,
    'Counts indicate governed records, not absence of impact or stakeholder satisfaction.' AS uncertainty_limitation,
    NOW() AS generated_at;

COMMENT ON VIEW v_stakeholder_cockpit_internal IS 'Operator cockpit aggregate; includes governance health and unresolved risk indicators';
COMMENT ON VIEW v_public_stakeholder_cockpit IS 'Public-safe aggregate cockpit; excludes protected and unresolved internal records';
