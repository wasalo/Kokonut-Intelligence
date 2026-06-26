const METRIC_PROPOSAL_TRANSITIONS: Record<string, string[]> = {
  proposed: ['discussed', 'approved', 'rejected'],
  discussed: ['approved', 'rejected'],
  approved: ['implemented', 'deprecated'],
  implemented: ['deprecated'],
  deprecated: [],
  rejected: ['proposed'],
};

const REVIEW_STATUSES = new Set(['approved', 'implemented', 'deprecated', 'rejected']);

export function isValidMetricProposalTransition(fromStatus: string, toStatus: string): boolean {
  return METRIC_PROPOSAL_TRANSITIONS[fromStatus]?.includes(toStatus) || false;
}

export async function handleMetricProposalUpdate(
  payload: Record<string, any>,
  meta: Record<string, any>,
  db: any,
  accountability?: Record<string, any>
): Promise<Record<string, any>> {
  if (!payload.status) return payload;

  const recordId = meta.keys?.[0] ?? meta.keys?.id;
  if (!recordId) return payload;

  const current = await db('metric_proposal').where('id', recordId).first('status', 'proposal_date');
  const currentStatus = current?.status;
  if (!currentStatus || currentStatus === payload.status) return payload;

  if (!isValidMetricProposalTransition(currentStatus, payload.status)) {
    throw new Error(
      `Invalid metric_proposal status transition: ${currentStatus} → ${payload.status}`
    );
  }

  // Enforce 30-day discussion period before approval
  if (payload.status === 'approved' && current?.proposal_date) {
    const proposalDate = new Date(current.proposal_date);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - proposalDate.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays < 30) {
      throw new Error(
        `Metric proposal requires at least 30 days of discussion before approval. ` +
        `Proposed: ${current.proposal_date}, days elapsed: ${diffDays}`
      );
    }
  }

  if (REVIEW_STATUSES.has(payload.status)) {
    payload.review_date = payload.review_date || new Date().toISOString().slice(0, 10);
    if (accountability?.user) payload.reviewed_by = payload.reviewed_by || accountability.user;
  }

  if (payload.status === 'implemented' && !payload.metric_definition_id) {
    throw new Error('Implemented metric proposals require metric_definition_id');
  }

  return payload;
}

export async function logMetricProposalTransition(
  db: any,
  recordId: string,
  toStatus: string,
  changedBy?: string,
  notes?: string
): Promise<void> {
  await db('workflow_history').insert({
    collection: 'metric_proposal',
    record_id: recordId,
    to_status: toStatus,
    changed_by: changedBy || null,
    notes: notes || null,
  });
}
