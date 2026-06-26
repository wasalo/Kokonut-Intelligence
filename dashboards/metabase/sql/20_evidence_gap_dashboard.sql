-- Evidence gap dashboard: impact claims and stakeholder outcomes needing stronger evidence.
SELECT
  l.name AS location,
  ic.claim_category,
  ic.claim_type,
  ic.status,
  ic.public_claim,
  ic.evidence_maturity,
  em.label AS evidence_maturity_label,
  COUNT(*) AS claim_count,
  COUNT(*) FILTER (WHERE ic.public_claim = TRUE AND ic.evidence_maturity < 4) AS public_claims_below_public_threshold,
  COUNT(*) FILTER (
    WHERE ic.public_claim = TRUE
      AND ic.claim_category = 'carbon'
      AND (
        ic.evidence_maturity < 6
        OR ic.external_verifier IS NULL
        OR ic.methodology_ref IS NULL
      )
  ) AS carbon_publication_gaps,
  COUNT(*) FILTER (WHERE ic.evidence_cid IS NULL AND ic.evidence_hash IS NULL AND ic.attestation_uid IS NULL) AS missing_evidence_links
FROM impact_claim ic
JOIN location l ON l.id = ic.location_id
LEFT JOIN evidence_maturity_level em ON em.level = ic.evidence_maturity
WHERE ic.status != 'rejected'
GROUP BY l.name, ic.claim_category, ic.claim_type, ic.status, ic.public_claim, ic.evidence_maturity, em.label
ORDER BY carbon_publication_gaps DESC, public_claims_below_public_threshold DESC, missing_evidence_links DESC, claim_count DESC;
