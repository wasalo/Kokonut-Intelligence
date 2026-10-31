-- Add the timestamp used by the ordered governance tension reader.
-- Preserve the existing migration-244 view columns and append created_at.

BEGIN;

CREATE OR REPLACE VIEW v_governance_tension_health AS
SELECT
    t.id AS tension_id,
    t.tension_key,
    t.title,
    t.description,
    t.tension_type,
    t.severity,
    t.urgency,
    t.circle_id,
    c.circle_key,
    c.name AS circle_name,
    t.scope_type,
    t.scope_id,
    t.status,
    t.reported_by_party_id,
    reporter.display_name AS reported_by_name,
    t.affected_party_id,
    affected.display_name AS affected_party_name,
    t.owner_role_id,
    r.role_key AS owner_role_key,
    t.owner_party_id,
    owner_party.display_name AS owner_party_name,
    t.work_item_id,
    t.decision_id,
    t.grievance_id,
    t.review_due_at,
    t.deferred_until,
    COUNT(l.id) AS link_count,
    CASE WHEN t.review_due_at IS NOT NULL AND t.review_due_at < NOW()
         AND t.status IN ('submitted', 'triaged', 'in_progress', 'deferred')
         THEN TRUE ELSE FALSE END AS is_overdue,
    t.created_at
FROM governance_tension t
LEFT JOIN governance_circle c ON c.id = t.circle_id
LEFT JOIN party reporter ON reporter.id = t.reported_by_party_id
LEFT JOIN party affected ON affected.id = t.affected_party_id
LEFT JOIN governance_role r ON r.id = t.owner_role_id
LEFT JOIN party owner_party ON owner_party.id = t.owner_party_id
LEFT JOIN governance_tension_link l ON l.tension_id = t.id
GROUP BY t.id, t.tension_key, t.title, t.description, t.tension_type,
         t.severity, t.urgency, t.circle_id, c.circle_key, c.name,
         t.scope_type, t.scope_id, t.status, t.reported_by_party_id,
         reporter.display_name, t.affected_party_id, affected.display_name,
         t.owner_role_id, r.role_key, t.owner_party_id, owner_party.display_name,
         t.work_item_id, t.decision_id, t.grievance_id, t.review_due_at,
         t.deferred_until, t.created_at;

COMMENT ON VIEW v_governance_tension_health IS
    'Internal tension triage, ownership, linkage, overdue health, and creation ordering';

COMMIT;
