-- GNH alignment dashboard: public-safe domain alignment, safeguards, and gaps.
SELECT
  l.name AS location,
  g.assessment_date,
  g.gnh_domain,
  g.principle_refs,
  g.alignment_score,
  g.strengths,
  g.gaps,
  g.safeguards,
  g.evidence_maturity,
  g.evidence_maturity_label,
  g.public_summary
FROM v_public_gnh_alignment_summary g
JOIN location l ON l.id = g.location_id
ORDER BY g.assessment_date DESC, g.gnh_domain;
