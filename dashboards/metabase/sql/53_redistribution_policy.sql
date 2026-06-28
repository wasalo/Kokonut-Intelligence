SELECT policy_name, scenario_name, policy_scope, policy_status, revenue_basis,
  commons_allocation_pct, local_cooperative_allocation_pct, operator_allocation_pct,
  digital_commons_allocation_pct, reserve_allocation_pct, trigger_conditions,
  enforcement_mode, audit_cadence, evidence_maturity, evidence_maturity_label,
  public_summary
FROM v_public_commons_redistribution_policy
ORDER BY policy_status, policy_scope, policy_name;
