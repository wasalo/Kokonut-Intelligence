-- Correct participation denominators when one participant has multiple
-- accessibility requests or minority views.

CREATE OR REPLACE VIEW v_stakeholder_representation_metrics AS
SELECT
    sp.activity_type,
    sp.activity_id,
    COUNT(DISTINCT sp.id) AS invited_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.invitation_status IN ('accepted', 'attended')) AS accepted_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.invitation_status = 'attended') AS participated_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.invitation_status = 'declined') AS declined_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.invitation_status = 'absent') AS absent_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.contribution_count > 0) AS contributing_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.access_needs_recorded) AS access_needs_count,
    COUNT(DISTINCT sar.id) AS accessibility_request_count,
    COUNT(DISTINCT smv.id) AS minority_view_count,
    COUNT(DISTINCT smv.id) FILTER (WHERE smv.preserved) AS minority_view_preserved_count,
    ROUND(100.0 * COUNT(DISTINCT sp.id) FILTER (WHERE sp.invitation_status = 'attended') / NULLIF(COUNT(DISTINCT sp.id), 0), 2) AS participation_rate_pct,
    ROUND(100.0 * COUNT(DISTINCT sp.id) FILTER (WHERE sp.contribution_count > 0) / NULLIF(COUNT(DISTINCT sp.id) FILTER (WHERE sp.invitation_status = 'attended'), 0), 2) AS contribution_rate_pct
FROM stakeholder_participation sp
LEFT JOIN stakeholder_accessibility_request sar ON sar.participation_id = sp.id
LEFT JOIN stakeholder_minority_view smv ON smv.activity_type = sp.activity_type AND smv.activity_id = sp.activity_id
GROUP BY sp.activity_type, sp.activity_id;
