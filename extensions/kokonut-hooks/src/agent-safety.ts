const HIGH_RISK_ACTIONS = new Set([
  'publish',
  'attest',
  'onchain_submit',
  'delete',
  'bulk_update',
  'financial_write',
  'status_change_to_published',
]);

const AGENT_REVIEW_STATUSES = new Set(['draft', 'submitted', 'rejected']);
const AGENT_AI_STATUSES = new Set(['draft', 'submitted', 'rejected']);

export function isHighRiskAgentAction(action: string | undefined): boolean {
  return HIGH_RISK_ACTIONS.has(action || '');
}

export function enforceAgentTaskSafety(payload: Record<string, any>): Record<string, any> {
  const initiatorType = payload.initiator_type || 'agent';
  if (initiatorType === 'agent' && payload.review_status && !AGENT_REVIEW_STATUSES.has(payload.review_status)) {
    throw new Error('Agent tasks can only be draft, submitted, or rejected');
  }

  if (isHighRiskAgentAction(payload.task_type)) {
    payload.high_risk = true;
    if (!payload.review_status) payload.review_status = 'submitted';
  }

  return payload;
}

export function enforceAiSummarySafety(payload: Record<string, any>): Record<string, any> {
  if (payload.created_by && payload.status && !AGENT_AI_STATUSES.has(payload.status)) {
    throw new Error('Agent-created AI summaries can only be draft, submitted, or rejected');
  }
  return payload;
}

export function prepareAgentActionLog(payload: Record<string, any>): Record<string, any> {
  const highRisk = isHighRiskAgentAction(payload.action);
  if (highRisk) {
    payload.high_risk = true;
    payload.requires_human_approval = true;
  } else if (payload.high_risk === undefined) {
    payload.high_risk = false;
  }
  return payload;
}
