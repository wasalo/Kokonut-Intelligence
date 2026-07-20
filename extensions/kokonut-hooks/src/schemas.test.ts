import { describe, it, expect } from 'vitest';
import { z } from 'zod';
import {
  validateAgentTaskCreate,
  validateAgentTaskUpdate,
  validateAiSummaryCreate,
  validateAiSummaryUpdate,
  validateAgentActionLogCreate,
  validateImpactClaimCreate,
  validateStakeholderFeedbackCreate,
  validateExpenseEventCreate,
  validateExpenseEventUpdate,
  validateSalesEventCreate,
  validateRevenueEventCreate,
  formatZodError,
} from './schemas/index.js';

describe('agent_task schema', () => {
  it('accepts a valid create payload', () => {
    const p = validateAgentTaskCreate({ task_type: 'cids_export', status: 'draft' });
    expect(p.task_type).toBe('cids_export');
  });

  it('rejects a missing task_type', () => {
    expect(() => validateAgentTaskCreate({})).toThrow(z.ZodError);
  });

  it('allows partial update payload', () => {
    const p = validateAgentTaskUpdate({ review_status: 'submitted' });
    expect(p.review_status).toBe('submitted');
  });

  it('preserves unknown fields via passthrough', () => {
    const p = validateAgentTaskCreate({ task_type: 'cids_export', custom_field: 'x' });
    expect((p as any).custom_field).toBe('x');
  });
});

describe('ai_summary schema', () => {
  it('rejects invalid status enum', () => {
    expect(() => validateAiSummaryCreate({ status: 'verified' })).toThrow(z.ZodError);
  });

  it('accepts valid status', () => {
    expect(validateAiSummaryCreate({ status: 'submitted' }).status).toBe('submitted');
  });

  it('accepts partial update', () => {
    expect(validateAiSummaryUpdate({ title: 'Q3 summary' }).title).toBe('Q3 summary');
  });
});

describe('agent_action_log schema', () => {
  it('accepts a known high-risk action', () => {
    expect(validateAgentActionLogCreate({ action: 'publish' }).action).toBe('publish');
  });

  it('rejects an unknown action', () => {
    expect(() => validateAgentActionLogCreate({ action: 'weird_action' })).toThrow(z.ZodError);
  });
});

describe('impact_claim schema', () => {
  it('accepts valid evidence maturity', () => {
    expect(validateImpactClaimCreate({ evidence_maturity: 6 }).evidence_maturity).toBe(6);
  });

  it('rejects out-of-range maturity', () => {
    expect(() => validateImpactClaimCreate({ evidence_maturity: 9 })).toThrow(z.ZodError);
  });
});

describe('stakeholder_feedback schema', () => {
  it('rejects public feedback without consent', () => {
    expect(() =>
      validateStakeholderFeedbackCreate({
        is_public: true,
        consent_given: false,
        status: 'published',
        public_summary: 'ok',
      })
    ).toThrow(z.ZodError);
  });

  it('accepts valid public feedback', () => {
    const p = validateStakeholderFeedbackCreate({
      is_public: true,
      consent_given: true,
      consent_scope: 'public_review',
      status: 'published',
      public_summary: 'Community approved',
    });
    expect(p.is_public).toBe(true);
  });
});

describe('financial event schemas', () => {
  it('rejects negative expense amount', () => {
    expect(() => validateExpenseEventCreate({ amount: -5 })).toThrow(z.ZodError);
  });

  it('accepts valid expense', () => {
    expect(validateExpenseEventCreate({ amount: 12.5, currency: 'USD' }).amount).toBe(12.5);
  });

  it('accepts partial expense update', () => {
    expect(validateExpenseEventUpdate({ category: 'seeds' }).category).toBe('seeds');
  });

  it('rejects negative sales total', () => {
    expect(() => validateSalesEventCreate({ total_amount: -1 })).toThrow(z.ZodError);
  });

  it('accepts valid revenue event', () => {
    expect(validateRevenueEventCreate({ amount: 100, revenue_date: '2026-07-20' }).amount).toBe(100);
  });
});

describe('formatZodError', () => {
  it('produces a concise message without leaking internals', () => {
    try {
      validateExpenseEventCreate({ amount: -1 });
    } catch (error) {
      if (error instanceof z.ZodError) {
        const msg = formatZodError(error);
        expect(msg).toContain('amount:');
        expect(msg).toContain('not be negative');
      } else {
        throw error;
      }
    }
  });
});
