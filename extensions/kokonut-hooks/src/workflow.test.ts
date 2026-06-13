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
