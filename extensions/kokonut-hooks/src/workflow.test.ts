import { describe, it, expect } from 'vitest';
import {
  isValidTransition,
  isRoleAuthorized,
  getValidNextStatuses,
  stashPendingTransition,
  consumePendingTransition,
  LIFECYCLE_COLLECTIONS,
  handleWorkflowTransition,
} from './workflow.js';
import { enforceStakeholderGovernanceSafety } from './agent-safety.js';
import { roleNameToSlug } from './roles.js';
import { normalizeFeedbackPayload, validateStakeholderFeedback } from './feedback.js';
import { handleMetricProposalUpdate, isValidMetricProposalTransition } from './metric-proposal.js';
import { stampImpactClaimReview, validateImpactClaim } from './impact-claim.js';
import { enforceAgentTaskSafety, enforceAiSummarySafety, prepareAgentActionLog } from './agent-safety.js';

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

  it('rejects unknown collections instead of failing open', () => {
    expect(isValidTransition('unknown_collection', 'draft', 'published')).toBe(false);
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

  it('fails closed for unrouted non-initial transitions', () => {
    expect(isRoleAuthorized('credit_class', 'deprecated', ['admin'])).toBe(false);
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

describe('tenant lifecycle audit transaction', () => {
  it('writes the transition through the request database before returning the update payload', async () => {
    const inserts: Array<{ table: string; row: Record<string, unknown> }> = [];
    const db = (table: string) => ({
      where: () => ({ first: async () => ({ status: 'submitted' }) }),
      insert: async (row: Record<string, unknown>) => {
        inserts.push({ table, row });
      },
    });
    const payload: Record<string, unknown> = { status: 'verified' };

    await expect(handleWorkflowTransition(
      'field_note', payload, { id: 'note-1' }, ['admin'], db,
      { user: 'operator-1' }, true,
    )).resolves.toBe(payload);

    expect(inserts).toEqual([{
      table: 'workflow_history',
      row: {
        collection: 'field_note',
        record_id: 'note-1',
        from_status: 'submitted',
        to_status: 'verified',
        changed_by: 'operator-1',
        notes: null,
        rejection_reason: null,
      },
    }]);
    expect(consumePendingTransition('field_note', 'note-1')).toBeUndefined();
  });

  it('fails the update when the request-transaction audit insert fails', async () => {
    const db = (table: string) => ({
      where: () => ({ first: async () => ({ status: 'submitted' }) }),
      insert: async () => {
        if (table === 'workflow_history') throw new Error('private database detail');
      },
    });

    await expect(handleWorkflowTransition(
      'field_note', { status: 'verified' }, { id: 'note-2' }, ['admin'], db,
      { user: 'operator-1' }, true,
    )).rejects.toThrow('Unable to record workflow transition for field_note');
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

  it('fails closed when the review lookup context is unavailable', async () => {
    await expect(
      handleWorkflowTransition(
        'stakeholder_feedback',
        { status: 'verified' },
        { id: 'feedback-1', status: 'submitted' },
        ['manager'],
      ),
    ).rejects.toThrow(/review period/);
  });

  it('rejects invalid feedback submission dates', async () => {
    const db = () => ({
      where: () => ({
        first: async (field: string) => field === 'status' ? { status: 'submitted' } : { submitted_at: 'invalid' },
      }),
    });
    await expect(
      handleWorkflowTransition(
        'stakeholder_feedback',
        { status: 'verified' },
        { id: 'feedback-2' },
        ['manager'],
        db,
      ),
    ).rejects.toThrow(/valid date/);
  });
});

describe('metric proposal workflow', () => {
  it('allows proposed → approved and blocks implemented → approved', () => {
    expect(isValidMetricProposalTransition('proposed', 'approved')).toBe(true);
    expect(isValidMetricProposalTransition('implemented', 'approved')).toBe(false);
  });

  it('does not treat the Directus user UUID as a staff reviewer ID', async () => {
    const payload: Record<string, any> = { status: 'approved' };
    const db = () => ({
      where: () => ({
        first: async () => ({ status: 'proposed', proposal_date: '2020-01-01' }),
      }),
    });

    await handleMetricProposalUpdate(payload, { keys: ['proposal-1'] }, db);

    expect(payload.review_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(payload).not.toHaveProperty('reviewed_by');
  });

  it('preserves an explicit staff reviewer for tenant validation', async () => {
    const staffId = 'staff-1';
    const payload = { status: 'approved', reviewed_by: staffId };
    const db = () => ({
      where: () => ({
        first: async () => ({ status: 'proposed', proposal_date: '2020-01-01' }),
      }),
    });

    await handleMetricProposalUpdate(payload, { keys: ['proposal-1'] }, db);

    expect(payload.reviewed_by).toBe(staffId);
  });
});

describe('impact claim workflow', () => {
  it('does not copy the Directus user UUID into the staff reviewer field', async () => {
    const payload: Record<string, any> = { status: 'verified' };

    await stampImpactClaimReview(payload);

    expect(payload.review_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(payload).not.toHaveProperty('reviewer_id');
  });

  it('preserves an explicitly selected staff reviewer', async () => {
    const payload: Record<string, any> = { status: 'verified', reviewer_id: 'staff-1' };

    await stampImpactClaimReview(payload);

    expect(payload.reviewer_id).toBe('staff-1');
  });

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
    expect(() => enforceAgentTaskSafety(
      { initiator_type: 'human', review_status: 'published' },
      ['agent_write'],
    )).toThrow(/Agent tasks/);
  });

  it('does not trust the payload initiator type', () => {
    expect(() => enforceAgentTaskSafety({ initiator_type: 'agent', review_status: 'published' })).not.toThrow();
  });

  it('detects agents by resolved role slug, not by raw UUID', () => {
    // Raw accountability role UUIDs must never be treated as agent slugs.
    expect(() => enforceAgentTaskSafety(
      { initiator_type: 'human', review_status: 'published' },
      ['8f3c1b2a-0000-4000-8000-000000000001'],
    )).not.toThrow();
    expect(() => enforceAgentTaskSafety(
      { review_status: 'published' },
      ['agent_write'],
    )).toThrow(/Agent tasks/);
  });

  it('uses accountability to restrict agent AI summaries', () => {
    expect(() => enforceAiSummarySafety(
      { created_by: 'human', status: 'published' },
      ['agent_write'],
    )).toThrow(/AI summaries/);
  });

  it('does not trust payload creator fields for AI summary safety', () => {
    expect(() => enforceAiSummarySafety({ created_by: 'agent', status: 'published' })).not.toThrow();
  });

  it('marks high-risk action logs for approval', () => {
    const payload = prepareAgentActionLog({ action: 'publish' });
    expect(payload.high_risk).toBe(true);
    expect(payload.requires_human_approval).toBe(true);
  });

  it('blocks agents from human-governed stakeholder writes', () => {
    expect(() => enforceStakeholderGovernanceSafety(
      'stakeholder_decision',
      { status: 'draft' },
      ['agent_write'],
    )).toThrow(/human-governed stakeholder collection/);
  });

  it('allows human stakeholder writes', () => {
    expect(() => enforceStakeholderGovernanceSafety(
      'stakeholder_decision',
      { status: 'draft' },
      ['manager'],
    )).not.toThrow();
  });

  it('allows agents to draft governance tensions and proposals only', () => {
    expect(() => enforceStakeholderGovernanceSafety(
      'governance_tension',
      { status: 'draft', action: 'create' },
      ['agent_write'],
    )).not.toThrow();
    expect(() => enforceStakeholderGovernanceSafety(
      'governance_proposal',
      { status: 'approved', action: 'update' },
      ['agent_write'],
    )).toThrow(/human-governed stakeholder collection/);
  });
});
