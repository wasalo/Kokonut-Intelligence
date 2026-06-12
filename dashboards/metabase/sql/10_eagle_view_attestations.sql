-- Eagle View: Attestation Coverage
-- Onchain/offchain attestation status and coverage across claim types

SELECT
  COALESCE(ar.claim_type, 'unattested') as claim_type,
  COUNT(ar.id) as total_records,
  COUNT(CASE WHEN ar.status = 'published' THEN 1 END) as published,
  COUNT(CASE WHEN ar.status = 'verified' THEN 1 END) as verified,
  COUNT(CASE WHEN ar.status = 'submitted' THEN 1 END) as submitted,
  COUNT(CASE WHEN ar.status = 'draft' THEN 1 END) as draft,
  COUNT(CASE WHEN ar.status = 'rejected' THEN 1 END) as rejected,
  COUNT(CASE WHEN ar.chain IS NOT NULL THEN 1 END) as onchain_count,
  COUNT(CASE WHEN ar.chain IS NULL THEN 1 END) as offchain_count,
  CASE 
    WHEN COUNT(ar.id) > 0 
    THEN ROUND(COUNT(CASE WHEN ar.status = 'published' THEN 1 END)::numeric / COUNT(ar.id) * 100, 1)
    ELSE 0 
  END as publication_rate_pct
FROM attestation_record ar
GROUP BY ar.claim_type
ORDER BY total_records DESC;
