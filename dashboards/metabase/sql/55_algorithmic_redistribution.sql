SELECT mechanism_name, mechanism_type, beneficiary_scope, allocation_formula,
  funding_source, eligibility_criteria, privacy_safeguards, implementation_status,
  enforcement_mode, evidence_maturity, evidence_maturity_label, public_summary
FROM v_public_algorithmic_redistribution_mechanism
ORDER BY implementation_status, mechanism_type, mechanism_name;
