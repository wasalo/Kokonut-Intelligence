import { afterEach, describe, expect, it, vi } from 'vitest';
import registerHook from './index.js';
import { resolveUserRoles } from './roles.js';
import { batchCalculateNoi, setDb } from './metrics-calculator.js';
import { errorClass } from './error-safety.js';

describe('Directus exception logging', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setDb(() => ({}));
  });

  it('returns only bounded exception class labels', () => {
    expect(errorClass(new TypeError('synthetic exception details'))).toBe('TypeError');
    expect(errorClass({ name: 'UntrustedExceptionNameWithDetails' })).toBe('NonError');

    const malformedName = new Error('private database details');
    Object.defineProperty(malformedName, 'name', { get: () => { throw new Error('private'); } });
    expect(errorClass(malformedName)).toBe('Error');
  });

  it('does not log role lookup exception messages', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const database = () => ({
      where: () => ({ first: async () => { throw new Error('simulated database connection details'); } }),
    });

    await expect(resolveUserRoles(database, { accountability: { role: 'role-id' } })).resolves.toEqual([]);

    expect(log).toHaveBeenCalledWith('[Kokonut] Failed to resolve role name: Error');
    expect(log.mock.calls.flat().join(' ')).not.toContain('simulated database connection details');
  });

  it('does not log NOI calculation exception messages', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const database = (table: string) => {
      const query: any = {
        whereIn: () => query,
        where: () => query,
        select: async () => [{ id: 'cycle-1' }],
        first: async () => { throw new Error('private query parameter'); },
      };
      if (table === 'crop_cycle') query.first = undefined;
      return query;
    };

    setDb(database);
    const result = await batchCalculateNoi();
    expect(result).toEqual({ succeeded: 0, failed: 1 });
    expect(log).toHaveBeenCalledWith('[Kokonut] Failed to calculate NOI for crop cycle cycle-1: Error');
    expect(log.mock.calls.flat().join(' ')).not.toContain('private query parameter');
  });

  it('reports partial daily NOI failures as a failed reconciliation summary', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const callbacks: Array<() => Promise<void>> = [];
    const database = (table: string) => {
      const query: any = {
        whereIn: () => query,
        where: () => query,
        select: async () => [{ id: 'cycle-1' }],
        first: async () => { throw new Error('private query parameter'); },
      };
      if (table === 'crop_cycle') query.first = undefined;
      return query;
    };

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: () => undefined,
        schedule: (_expression: string, callback: () => Promise<void>) => callbacks.push(callback),
      },
      {
        database,
        env: {
          KOKONUT_DIRECTUS_SCHEDULE_NOI_RECONCILIATION: 'true',
          KOKONUT_DIRECTUS_SCHEDULE_WEEKLY_ACTIVITY_AGGREGATION: 'true',
        },
      },
    );

    await callbacks[0]();

    expect(log).toHaveBeenCalledWith(
      '[Kokonut] NOI reconciliation completed with partial failures: succeeded=0 failed=1',
    );
    expect(log.mock.calls.flat().join(' ')).not.toContain('private query parameter');
  });

  it('does not log raw errors from schedule callbacks', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const callbacks: Array<() => Promise<void>> = [];
    const database = () => { throw new Error('private connection details'); };

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: () => undefined,
        schedule: (_expression: string, callback: () => Promise<void>) => callbacks.push(callback),
      },
      {
        database,
        env: {
          KOKONUT_DIRECTUS_SCHEDULE_NOI_RECONCILIATION: 'true',
          KOKONUT_DIRECTUS_SCHEDULE_WEEKLY_ACTIVITY_AGGREGATION: 'true',
        },
      },
    );

    await callbacks[0]();
    await callbacks[1]();

    expect(log).toHaveBeenCalledWith('[Kokonut] NOI reconciliation failed: Error');
    expect(log).toHaveBeenCalledWith(
      '[Kokonut] Weekly verified farm activity aggregation failed: Error',
    );
    expect(log.mock.calls.flat().join(' ')).not.toContain('private connection details');
  });
});
