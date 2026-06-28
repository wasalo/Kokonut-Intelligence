-- Governance inclusion dashboard: public-safe representation and pseudonymous participation evidence.
SELECT
  COALESCE(l.name, 'Network') AS location,
  g.observation_date,
  g.governance_body,
  g.inclusion_scope,
  g.represented_groups,
  g.missing_groups,
  g.pseudonymous_participation_enabled,
  g.marginalized_voice_count,
  g.total_participant_count,
  g.representation_coverage_pct,
  g.evidence_maturity,
  g.evidence_maturity_label,
  g.public_summary
FROM v_public_governance_inclusion_summary g
LEFT JOIN location l ON l.id = g.location_id
ORDER BY g.observation_date DESC, g.governance_body;
