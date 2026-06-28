-- Capital alignment dashboard: public-safe anti-extractive capital assessment evidence.
SELECT
  l.name AS location,
  c.assessment_date,
  c.provider_name,
  c.provider_type,
  c.alignment_status,
  c.extractive_risk_level,
  c.commons_reinvestment_commitment_pct,
  c.community_control_terms,
  c.profit_extraction_limits,
  c.evidence_maturity,
  c.evidence_maturity_label,
  c.public_summary
FROM v_public_capital_alignment_summary c
JOIN location l ON l.id = c.location_id
ORDER BY c.assessment_date DESC, c.provider_type;
