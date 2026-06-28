-- Evidence gap dashboard: impact claims and stakeholder outcomes needing stronger evidence.
-- Uses v_public_impact_claim_summary to inherit publication and evidence-maturity gates.
SELECT
  ic.location_id,
  ic.claim_category,
  ic.claim_type,
  ic.evidence_maturity,
  ic.evidence_maturity_label,
  ic.confidence_level,
  ic.methodology_ref,
  ic.external_verifier,
  ic.attestation_uid,
  ic.claim_text,
  ic.claim_value,
  ic.claim_unit
FROM v_public_impact_claim_summary ic
ORDER BY ic.evidence_maturity ASC, ic.claim_category;
