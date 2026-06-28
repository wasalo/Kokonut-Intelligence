SELECT protocol_name, target_region, federation_scope, permissionless_forking_enabled,
  local_adaptation_rights, mutual_aid_commitments, shared_infrastructure,
  onboarding_requirements, anti_extractive_safeguards, conflict_resolution_path,
  protocol_status, evidence_maturity, evidence_maturity_label, public_summary
FROM v_public_federation_protocol
ORDER BY protocol_status, federation_scope, protocol_name;
