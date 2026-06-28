-- Community governance dashboard: public-safe decision mechanisms and power distribution.
SELECT
  COALESCE(l.name, 'Network') AS location,
  g.mechanism_name,
  g.governance_level,
  g.decision_body,
  g.decision_method,
  g.quorum_rule,
  g.voting_or_consensus_rights,
  g.community_veto_rights,
  g.escalation_path,
  g.power_distribution_summary,
  g.participation_cadence,
  g.evidence_maturity,
  g.evidence_maturity_label,
  g.public_summary
FROM v_public_community_governance_mechanism g
LEFT JOIN location l ON l.id = g.location_id
ORDER BY g.governance_level, g.mechanism_name;
