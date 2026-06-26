export function normalizeImpactClaimPayload(payload: Record<string, any>): Record<string, any> {
  if (payload.public_claim === undefined) payload.public_claim = false;
  if (payload.evidence_maturity === undefined) payload.evidence_maturity = 1;
  if (payload.status === undefined) payload.status = 'draft';
  return payload;
}

export function validateImpactClaim(payload: Record<string, any>): void {
  if (payload.public_claim !== true) return;

  if (payload.status !== 'published') {
    throw new Error('Public impact claims must be published');
  }

  if (Number(payload.evidence_maturity || 0) < 4) {
    throw new Error('Public impact claims require evidence maturity level 4 or higher');
  }

  if (payload.claim_category === 'carbon') {
    if (Number(payload.evidence_maturity) !== 6) {
      throw new Error('Public carbon claims require evidence maturity level 6');
    }
    if (payload.claim_type !== 'third_party_verified_claim') {
      throw new Error('Public carbon claims require claim_type third_party_verified_claim');
    }
    if (!String(payload.external_verifier || '').trim()) {
      throw new Error('Public carbon claims require external_verifier');
    }
    if (!String(payload.methodology_ref || '').trim()) {
      throw new Error('Public carbon claims require methodology_ref');
    }
  }
}

export async function stampImpactClaimReview(
  payload: Record<string, any>,
  accountability?: Record<string, any>
): Promise<Record<string, any>> {
  if (['verified', 'published', 'rejected'].includes(payload.status)) {
    payload.review_date = payload.review_date || new Date().toISOString().slice(0, 10);
    if (accountability?.user) payload.reviewer_id = payload.reviewer_id || accountability.user;
  }
  return payload;
}
