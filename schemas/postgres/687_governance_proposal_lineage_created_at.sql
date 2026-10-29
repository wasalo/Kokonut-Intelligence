-- Add the proposal timestamp required by the existing ordered list reader.
-- Keep all migration-246 columns in place and append the new field.

BEGIN;

CREATE OR REPLACE VIEW v_governance_proposal_lineage AS
SELECT
    p.id AS proposal_id,
    p.proposal_key,
    p.circle_id,
    c.circle_key,
    p.proposal_type,
    p.title,
    p.status,
    p.tension_id,
    p.proposed_by_party_id,
    proposer.display_name AS proposer_name,
    p.proposed_by_role_id,
    role.role_key AS proposer_role_key,
    p.harm_review_status,
    p.minority_review_status,
    p.approved_by_party_id,
    approver.display_name AS approver_name,
    p.approved_at,
    p.implementation_work_item_id,
    p.review_due_at,
    COUNT(o.id) AS objection_count,
    COUNT(o.id) FILTER (WHERE o.status = 'open') AS open_objection_count,
    COUNT(o.id) FILTER (
        WHERE o.status = 'open'
          AND o.objection_type IN ('material_harm', 'consent_failure')
    ) AS open_material_objection_count,
    COUNT(r.id) AS review_count,
    p.created_at
FROM governance_proposal p
JOIN governance_circle c ON c.id = p.circle_id
LEFT JOIN party proposer ON proposer.id = p.proposed_by_party_id
LEFT JOIN governance_role role ON role.id = p.proposed_by_role_id
LEFT JOIN party approver ON approver.id = p.approved_by_party_id
LEFT JOIN governance_proposal_objection o ON o.proposal_id = p.id
LEFT JOIN governance_proposal_review r ON r.proposal_id = p.id
GROUP BY p.id, p.proposal_key, p.circle_id, c.circle_key, p.proposal_type,
         p.title, p.status, p.tension_id, p.proposed_by_party_id,
         proposer.display_name, p.proposed_by_role_id, role.role_key,
         p.harm_review_status, p.minority_review_status, p.approved_by_party_id,
         approver.display_name, p.approved_at, p.implementation_work_item_id,
         p.review_due_at, p.created_at;

COMMENT ON VIEW v_governance_proposal_lineage IS
    'Internal proposal lineage with objection/review health and creation ordering';

COMMIT;
