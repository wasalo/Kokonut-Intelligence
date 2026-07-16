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

export const STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS = new Set([
  'party_resolution_case',
  'stakeholder_consent',
  'stakeholder_grievance_case',
  'grievance_remedy',
  'stakeholder_decision',
  'stakeholder_decision_evidence',
  'buyer_verification',
  'market_dispute',
  'cooperative_distribution_decision',
  'coordination_alliance',
  'coordination_participant',
  'coordination_objective',
  'coordination_contribution',
  'coordination_benefit',
  'coordination_risk',
  'coordination_knowledge_exchange',
  'coordination_review',
  'coordination_learning_link',
  'coordination_metric_observation',
  'coordination_conflict_declaration',
  'coordination_benefit_harm_analysis',
  'coordination_minority_view',
  'coordination_appeal',
  'coordination_remedy',
  'coordination_approval',
  'coordination_partner_event',
  'coordination_market_observation',
  'party_trust_evidence',
  'stewardship_proxy_authority',
  'nature_stewardship_obligation',
  'future_generation_principle',
  'governance_circle',
  'governance_role',
  'governance_role_accountability',
  'governance_role_domain',
  'governance_role_policy',
  'governance_role_assignment',
  'governance_tension',
  'governance_tension_link',
  'governance_tension_event',
  'governance_proposal',
  'governance_proposal_objection',
  'governance_proposal_review',
  'governance_tactical_session',
  'governance_tactical_item',
  'governance_circle_link',
]);

export function isHighRiskAgentAction(action: string | undefined): boolean {
  return HIGH_RISK_ACTIONS.has(action || '');
}

function isAgentActor(meta?: Record<string, any>): boolean {
  const role = meta?.accountability?.role;
  return typeof role === 'string' && (
    role === 'agent_read_only' ||
    role === 'agent_write' ||
    role === 'agent_full' ||
    role.startsWith('agent')
  );
}

export function enforceAgentTaskSafety(
  payload: Record<string, any>,
  meta?: Record<string, any>
): Record<string, any> {
  if (isAgentActor(meta) && payload.review_status && !AGENT_REVIEW_STATUSES.has(payload.review_status)) {
    throw new Error('Agent tasks can only be draft, submitted, or rejected');
  }

  if (isHighRiskAgentAction(payload.task_type)) {
    payload.high_risk = true;
    if (!payload.review_status) payload.review_status = 'submitted';
  }

  return payload;
}

export function enforceAiSummarySafety(payload: Record<string, any>, meta?: Record<string, any>): Record<string, any> {
  if (isAgentActor(meta) && payload.status && !AGENT_AI_STATUSES.has(payload.status)) {
    throw new Error('Agent-created AI summaries can only be draft, submitted, or rejected');
  }
  return payload;
}

export function enforceStakeholderGovernanceSafety(
  collection: string,
  payload: Record<string, any>,
  meta?: Record<string, any>
): Record<string, any> {
  if (collection === 'coordination_alliance' && isAgentActor(meta) && payload.status === 'draft') {
    return payload;
  }
  if (isAgentActor(meta) && collection === 'governance_tension' && (!payload.action || payload.action === 'create') && payload.status === 'draft') {
    return payload;
  }
  if (isAgentActor(meta) && collection === 'governance_proposal' && (!payload.action || payload.action === 'create') && payload.status === 'draft') {
    return payload;
  }
  if (isAgentActor(meta) && collection === 'governance_tactical_item' && (!payload.action || payload.action === 'create') && (!payload.status || payload.status === 'open')) {
    return payload;
  }
  if (isAgentActor(meta) && STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS.has(collection)) {
    throw new Error(`Agent writes are blocked for human-governed stakeholder collection ${collection}`);
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
