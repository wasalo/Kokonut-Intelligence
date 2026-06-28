SELECT policy_name, governance_body, policy_scope, voting_method, voting_cap_pct,
  quadratic_or_conviction_enabled, one_person_one_vote_enabled,
  worker_or_operator_veto_enabled, community_veto_enabled, enforcement_mode,
  evidence_maturity, evidence_maturity_label, public_summary
FROM v_public_anti_capture_governance_policy
ORDER BY policy_scope, policy_name;
