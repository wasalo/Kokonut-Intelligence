-- Governance cockpit projections for internal operators and public-safe counts.

CREATE OR REPLACE VIEW v_governance_cockpit_internal AS
SELECT
    (SELECT COUNT(*) FROM governance_circle WHERE status = 'active') AS active_circle_count,
    (SELECT COUNT(*) FROM governance_role WHERE status IN ('approved', 'active')) AS active_role_count,
    (SELECT COUNT(*) FROM governance_role r WHERE r.status IN ('approved', 'active') AND NOT EXISTS (
        SELECT 1 FROM governance_role_assignment a WHERE a.role_id = r.id AND a.status = 'active' AND a.assignment_type = 'primary'
    )) AS unassigned_role_count,
    (SELECT COUNT(*) FROM governance_role_assignment WHERE status = 'active' AND review_due_at < NOW()) AS overdue_assignment_review_count,
    (SELECT COUNT(*) FROM governance_tension WHERE status IN ('submitted', 'triaged', 'in_progress', 'deferred')) AS unresolved_tension_count,
    (SELECT COUNT(*) FROM governance_tension WHERE status IN ('submitted', 'triaged', 'in_progress', 'deferred') AND severity >= 4) AS high_severity_tension_count,
    (SELECT COUNT(*) FROM governance_proposal WHERE status IN ('submitted', 'in_review')) AS proposals_awaiting_review_count,
    (SELECT COUNT(*) FROM governance_proposal_objection WHERE status = 'open') AS open_objection_count,
    (SELECT COUNT(*) FROM governance_proposal_objection WHERE status = 'open' AND objection_type IN ('material_harm', 'consent_failure')) AS material_objection_count,
    (SELECT COUNT(*) FROM governance_circle_link WHERE status = 'active' AND term_end IS NOT NULL AND term_end < NOW() + INTERVAL '30 days') AS links_expiring_soon_count,
    (SELECT COUNT(*) FROM governance_tactical_item WHERE status IN ('open', 'in_progress') AND due_at < NOW()) AS overdue_tactical_item_count,
    (SELECT COUNT(*) FROM governance_tactical_item WHERE status IN ('open', 'in_progress')) AS open_tactical_item_count,
    NOW() AS generated_at;

CREATE OR REPLACE VIEW v_governance_cockpit_public AS
SELECT
    (SELECT COUNT(*) FROM governance_circle WHERE status = 'active') AS active_circle_count,
    (SELECT COUNT(*) FROM governance_role WHERE status = 'active') AS active_role_count,
    (SELECT COUNT(*) FROM governance_tension WHERE status IN ('resolved', 'closed')) AS resolved_tension_count,
    (SELECT COUNT(*) FROM governance_proposal WHERE status = 'implemented') AS implemented_proposal_count,
    'Public cockpit exposes aggregate governance throughput only; private tensions, objections, identities, and protected stakeholder records are excluded.' AS privacy_limitation,
    NOW() AS generated_at;

COMMENT ON VIEW v_governance_cockpit_internal IS 'Internal role, tension, proposal, representation, and tactical governance health';
COMMENT ON VIEW v_governance_cockpit_public IS 'Public-safe aggregate governance throughput projection';
