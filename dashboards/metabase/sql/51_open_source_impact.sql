-- Open-source impact dashboard: reusable artifacts and verification outputs.
SELECT
  artifact_name,
  artifact_type,
  repository_path,
  external_url,
  license,
  version,
  reuse_status,
  reuse_count,
  supported_use_cases,
  verification_outputs,
  maintenance_owner,
  evidence_maturity,
  evidence_maturity_label,
  public_summary
FROM v_public_open_source_impact_artifact
ORDER BY reuse_count DESC, artifact_type, artifact_name;
