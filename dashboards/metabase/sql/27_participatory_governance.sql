-- Participatory governance dashboard: public-safe feedback-to-action traceability.
SELECT
  l.name AS location,
  p.action_type,
  p.action_date,
  p.stakeholder_group,
  p.feedback_type,
  p.sentiment,
  p.metric_name,
  p.metric_proposal_status,
  p.decision_status,
  p.evidence_maturity,
  p.evidence_maturity_label,
  p.public_summary
FROM v_public_participatory_governance_summary p
JOIN location l ON l.id = p.location_id
ORDER BY p.action_date DESC, p.action_type;
