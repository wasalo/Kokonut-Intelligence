import { describe, expect, it } from 'vitest';
import { isHighRiskAgentAction, prepareAgentActionLog } from './agent-safety.js';

describe('agent high-risk action logging', () => {
  it('classifies verification as high risk', () => {
    expect(isHighRiskAgentAction('verify')).toBe(true);
  });

  it('marks verification log entries for independent review', () => {
    expect(prepareAgentActionLog({ action: 'verify' })).toMatchObject({
      action: 'verify',
      high_risk: true,
      requires_human_approval: true,
    });
  });
});
