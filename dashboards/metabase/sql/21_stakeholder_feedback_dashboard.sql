-- Stakeholder feedback dashboard: consent, sentiment, review, and public summary readiness.
-- Uses v_public_stakeholder_feedback_summary to inherit publication, consent, and evidence-maturity gates.
SELECT
  sf.location_id,
  sf.stakeholder_group,
  sf.feedback_type,
  sf.sentiment,
  sf.evidence_maturity,
  sf.evidence_maturity_label,
  sf.public_summary,
  sf.feedback_date
FROM v_public_stakeholder_feedback_summary sf
ORDER BY sf.feedback_date DESC, sf.stakeholder_group;
