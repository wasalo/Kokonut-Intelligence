import { describe, it, expect } from 'vitest';
import {
  isValidTransition,
  isRoleAuthorized,
  getValidNextStatuses,
  stashPendingTransition,
  consumePendingTransition,
  LIFECYCLE_COLLECTIONS,
} from './workflow.js';
import { roleNameToSlug } from './roles.js';
import { normalizeFeedbackPayload, validateStakeholderFeedback } from './feedback.js';
import { isValidMetricProposalTransition } from './metric-proposal.js';
import { validateImpactClaim } from './impact-claim.js';
import { enforceAgentTaskSafety, prepareAgentActionLog } from './agent-safety.js';

describe('roleNameToSlug', () => {
  it('normalizes Directus role display names', () => {
    expect(roleNameToSlug('Finance')).toBe('finance');
    expect(roleNameToSlug('Field Worker')).toBe('field_worker');
    expect(roleNameToSlug('Supervisor')).toBe('supervisor');
  });
});

describe('isValidTransition', () => {
  it('allows draft → submitted', () => {
    expect(isValidTransition('expense_event', 'draft', 'submitted')).toBe(true);
  });

  it('blocks draft → published', () => {
    expect(isValidTransition('expense_event', 'draft', 'published')).toBe(false);
  });

  it('allows rejected → draft rework', () => {
    expect(isValidTransition('mrv_claim', 'rejected', 'draft')).toBe(true);
  });

  it('covers all lifecycle collections', () => {
    for (const collection of LIFECYCLE_COLLECTIONS) {
      expect(isValidTransition(collection, 'draft', 'submitted')).toBe(true);
      expect(isValidTransition(collection, 'published', 'draft')).toBe(false);
    }
  });
});

describe('isRoleAuthorized', () => {
  it('allows finance role to verify expenses', () => {
    expect(isRoleAuthorized('expense_event', 'verified', ['finance'])).toBe(true);
  });

  it('blocks field_worker from verifying expenses', () => {
    expect(isRoleAuthorized('expense_event', 'verified', ['field_worker'])).toBe(false);
  });

  it('allows admin for any restricted transition', () => {
    expect(isRoleAuthorized('expense_event', 'verified', ['admin'])).toBe(true);
    expect(isRoleAuthorized('mrv_claim', 'published', ['admin'])).toBe(true);
  });

  it('routes Phase 2 review collections', () => {
    expect(isRoleAuthorized('stakeholder_feedback', 'published', ['manager'])).toBe(true);
    expect(isRoleAuthorized('impact_claim', 'verified', ['analyst'])).toBe(true);
    expect(isRoleAuthorized('impact_claim', 'published', ['analyst'])).toBe(false);
  });

  it('allows manager to verify MRV claims', () => {
    expect(isRoleAuthorized('mrv_claim', 'verified', ['manager'])).toBe(true);
  });

  it('passes when no role restriction exists', () => {
    expect(isRoleAuthorized('expense_event', 'submitted', ['field_worker'])).toBe(true);
  });
});

describe('getValidNextStatuses', () => {
  it('returns submitted from draft', () => {
    expect(getValidNextStatuses('attestation_record', 'draft')).toEqual(['submitted']);
  });
});

describe('pending transition stash', () => {
  it('round-trips from_status between filter and action hooks', () => {
    stashPendingTransition('harvest_event', 'abc-123', 'draft');
    expect(consumePendingTransition('harvest_event', 'abc-123')).toBe('draft');
    expect(consumePendingTransition('harvest_event', 'abc-123')).toBeUndefined();
  });
});

describe('stakeholder feedback workflow', () => {
  it('defaults feedback to private draft', () => {
    const payload: Record<string, any> = {};
    normalizeFeedbackPayload(payload);
    expect(payload.consent_given).toBe(false);
    expect(payload.is_public).toBe(false);
    expect(payload.status).toBe('draft');
  });

  it('blocks public feedback without consent', () => {
    expect(() => validateStakeholderFeedback({ is_public: true, status: 'published' })).toThrow(/consent/);
  });
});

describe('metric proposal workflow', () => {
  it('allows proposed → approved and blocks implemented → approved', () => {
    expect(isValidMetricProposalTransition('proposed', 'approved')).toBe(true);
    expect(isValidMetricProposalTransition('implemented', 'approved')).toBe(false);
  });
});

describe('impact claim workflow', () => {
  it('blocks public carbon claims below level 6', () => {
    expect(() => validateImpactClaim({
      public_claim: true,
      status: 'published',
      claim_category: 'carbon',
      claim_type: 'published_record',
      evidence_maturity: 5,
    })).toThrow(/level 6/);
  });

  it('allows level 6 externally verified public carbon claims', () => {
    expect(() => validateImpactClaim({
      public_claim: true,
      status: 'published',
      claim_category: 'carbon',
      claim_type: 'third_party_verified_claim',
      evidence_maturity: 6,
      external_verifier: 'External MRV reviewer',
      methodology_ref: 'IPCC 2006 GHG Guidelines',
    })).not.toThrow();
  });
});

describe('agent safety workflow', () => {
  it('blocks agent tasks from direct publish', () => {
    expect(() => enforceAgentTaskSafety({ initiator_type: 'agent', review_status: 'published' })).toThrow(/Agent tasks/);
  });

  it('marks high-risk action logs for approval', () => {
    const payload = prepareAgentActionLog({ action: 'publish' });
    expect(payload.high_risk).toBe(true);
    expect(payload.requires_human_approval).toBe(true);
  });
});
