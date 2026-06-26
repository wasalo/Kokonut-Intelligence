const PUBLIC_CONSENT_SCOPES = new Set(['public_summary', 'public_quote', 'public_full']);

export function normalizeFeedbackPayload(payload: Record<string, any>): Record<string, any> {
  if (payload.consent_given === undefined) payload.consent_given = false;
  if (payload.consent_scope === undefined) payload.consent_scope = 'private_review';
  if (payload.is_public === undefined) payload.is_public = false;
  if (payload.status === undefined) payload.status = 'draft';
  if (payload.evidence_maturity === undefined) payload.evidence_maturity = 1;
  return payload;
}

export function validateStakeholderFeedback(payload: Record<string, any>): void {
  if (payload.is_public !== true) return;

  if (payload.consent_given !== true) {
    throw new Error('Stakeholder feedback requires explicit consent before public exposure');
  }

  if (!PUBLIC_CONSENT_SCOPES.has(payload.consent_scope)) {
    throw new Error('Stakeholder feedback public exposure requires public consent scope');
  }

  if (payload.status !== 'published') {
    throw new Error('Public stakeholder feedback must be published');
  }

  if (!String(payload.public_summary || '').trim()) {
    throw new Error('Public stakeholder feedback requires a non-empty public_summary');
  }
}

export async function recordFeedbackReview(
  db: any,
  feedbackId: string,
  action: string,
  reviewerId?: string,
  responseText?: string
): Promise<void> {
  await db('stakeholder_feedback_review').insert({
    feedback_id: feedbackId,
    reviewer_id: reviewerId || null,
    action,
    response_text: responseText || null,
  });
}
