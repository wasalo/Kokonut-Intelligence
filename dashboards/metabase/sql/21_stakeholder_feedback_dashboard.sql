-- Stakeholder feedback dashboard: consent, sentiment, review, and public summary readiness.
SELECT
  l.name AS location,
  sf.stakeholder_group,
  sf.feedback_type,
  sf.sentiment,
  sf.status,
  sf.consent_given,
  sf.consent_scope,
  sf.is_public,
  sf.evidence_maturity,
  COUNT(*) AS feedback_count,
  COUNT(*) FILTER (WHERE sf.is_public = TRUE) AS public_feedback_count,
  COUNT(*) FILTER (WHERE sf.consent_given = FALSE) AS private_or_no_consent_count,
  COUNT(*) FILTER (WHERE sf.harms_or_unintended_consequences IS NOT NULL) AS harm_or_unintended_consequence_count,
  COUNT(*) FILTER (WHERE sfr.id IS NOT NULL) AS reviewed_count,
  MAX(sf.feedback_date) AS latest_feedback_date
FROM stakeholder_feedback sf
JOIN location l ON l.id = sf.location_id
LEFT JOIN stakeholder_feedback_review sfr ON sfr.feedback_id = sf.id
WHERE sf.status != 'rejected'
GROUP BY l.name, sf.stakeholder_group, sf.feedback_type, sf.sentiment, sf.status,
         sf.consent_given, sf.consent_scope, sf.is_public, sf.evidence_maturity
ORDER BY latest_feedback_date DESC, feedback_count DESC;
