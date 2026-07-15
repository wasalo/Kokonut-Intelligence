-- Add scope fields to the engagement summary for location-scoped reports.

CREATE OR REPLACE VIEW v_stakeholder_engagement_summary AS
SELECT
    p.id AS plan_id,
    p.name,
    p.status,
    p.engagement_mode,
    sp.id AS stakeholder_party_id,
    sp.display_name AS stakeholder_name,
    COUNT(DISTINCT o.id) AS objective_count,
    COUNT(DISTINCT t.id) AS touchpoint_count,
    COUNT(DISTINCT c.id) AS commitment_count,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status IN ('open', 'in_progress')) AS open_commitment_count,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'fulfilled') AS fulfilled_commitment_count,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status IN ('open', 'in_progress') AND c.due_at < NOW()) AS overdue_commitment_count,
    COUNT(DISTINCT e.id) AS outcome_count,
    MAX(e.recorded_at) AS last_outcome_at,
    p.scope_type,
    p.scope_id
FROM stakeholder_engagement_plan p
JOIN party sp ON sp.id = p.stakeholder_party_id
LEFT JOIN stakeholder_engagement_objective o ON o.plan_id = p.id
LEFT JOIN stakeholder_touchpoint t ON t.plan_id = p.id
LEFT JOIN stakeholder_commitment c ON c.plan_id = p.id
LEFT JOIN stakeholder_engagement_outcome e ON e.plan_id = p.id
GROUP BY p.id, p.name, p.status, p.engagement_mode, p.scope_type, p.scope_id,
         sp.id, sp.display_name;
