-- Risk mitigation dashboard: public-safe material risk register with mitigation, oversight, and residual risk.
SELECT
  l.name AS location,
  r.risk_category,
  r.likelihood,
  r.impact_level,
  r.residual_risk_level,
  r.owner_role,
  r.review_cadence,
  r.next_review_date,
  r.insurance_scope,
  r.oversight_mechanism,
  r.technical_support_provider,
  r.evidence_maturity,
  r.evidence_maturity_label,
  r.public_summary
FROM v_public_risk_mitigation_summary r
JOIN location l ON l.id = r.location_id
ORDER BY r.next_review_date NULLS LAST, r.risk_category;
