-- Land stewardship dashboard: public-safe commons stewardship and anti-speculation evidence.
SELECT
  l.name AS location,
  s.commitment_date,
  s.stewardship_model,
  s.landlord_dependency_risk,
  s.anti_speculation_terms,
  s.community_benefit_rights,
  s.commons_transition_path,
  s.evidence_maturity,
  s.evidence_maturity_label,
  s.public_summary
FROM v_public_land_stewardship_summary s
JOIN location l ON l.id = s.location_id
ORDER BY s.commitment_date DESC, s.stewardship_model;
