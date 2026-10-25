import { describe, expect, it, vi } from 'vitest';
import registerHook from './index.js';

describe('Directus hook event registration', () => {
  it('uses collection-qualified Directus item event names', () => {
    const events: string[] = [];
    const register = (event: string) => events.push(event);

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: register,
        action: register,
        schedule: () => undefined,
      },
      { database: {}, env: {} },
    );

    expect(events.length).toBeGreaterThan(0);
    expect(events.every((event) => /^[a-z][a-z0-9_]*\.items\.(query|read|create|update|delete)$/.test(event))).toBe(true);
    expect(events).toContain('farm_activity.items.query');
    expect(events).toContain('farm_activity.items.read');
    expect(events).toContain('farm_activity.items.create');
    expect(events).toContain('farm_activity.items.update');
    expect(events).toContain('farm_activity.items.delete');
    expect(events).toContain('harvest_event.items.create');
    expect(events).toContain('harvest_event.items.update');
    expect(events).toContain('revenue_event.items.query');
    expect(events).toContain('revenue_event.items.read');
    expect(events).toContain('revenue_event.items.create');
    expect(events).toContain('revenue_event.items.update');
    expect(events).toContain('revenue_event.items.delete');
    expect(events).toContain('stakeholder_feedback_review.items.create');
  });

  it('binds feedback-review creation and reviewer validation to the request transaction', async () => {
    const locationA = '11111111-1111-4111-8111-111111111111';
    const locationB = '22222222-2222-4222-8222-222222222222';
    const feedbackId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    const staffId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
    const operatorId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
    const issuer = 'https://identity.example.test';
    const userId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const globalDatabase = vi.fn();
    const createRequestDatabase = (parentLocationId: string) => vi.fn((table: string) => {
      const builder: any = {};
      for (const method of [
        'select', 'distinct', 'whereNull', 'whereNotNull', 'whereRaw', 'whereIn',
      ]) {
        builder[method] = vi.fn(() => builder);
      }
      builder.where = vi.fn(() => builder);
      builder.first = vi.fn(async () => {
        if (table === 'public.directus_users') return { external_identifier: 'test-subject' };
        if (table === 'public.operator_identity') return { id: operatorId };
        if (table === 'public.operator_scope_grant as grant_row') return { location_id: locationA };
        if (table === 'staff') return { id: staffId };
        return undefined;
      });
      builder.then = (resolve: (value: unknown) => unknown, reject: (reason: unknown) => unknown) => {
        const rows = table === 'public.operator_scope_grant as grant_row'
          ? [{ location_id: locationA }]
          : table === 'public.stakeholder_feedback'
            ? [{ id: feedbackId, location_id: parentLocationId }]
            : [];
        return Promise.resolve(rows).then(resolve, reject);
      };
      return builder;
    });
    const filters = new Map<string, (...args: any[]) => Promise<any>>();

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => Promise<any>) => {
          filters.set(event, callback);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database: globalDatabase, env: { KOKONUT_OPERATOR_OIDC_ISSUER: issuer } },
    );

    const createReview = filters.get('stakeholder_feedback_review.items.create');
    expect(createReview).toBeDefined();
    const ownRequestDatabase = createRequestDatabase(locationA);
    const payload = { feedback_id: feedbackId, reviewer_id: staffId };
    await expect(createReview!(payload, {}, {
      database: ownRequestDatabase,
      accountability: { user: userId },
    })).resolves.toBe(payload);
    expect(ownRequestDatabase).toHaveBeenCalledWith('public.stakeholder_feedback');
    expect(ownRequestDatabase).toHaveBeenCalledWith('staff');
    expect(ownRequestDatabase).toHaveBeenCalledWith('public.operator_scope_grant as grant_row');
    expect(globalDatabase).not.toHaveBeenCalled();

    const foreignRequestDatabase = createRequestDatabase(locationB);
    await expect(createReview!(payload, {}, {
      database: foreignRequestDatabase,
      accountability: { user: userId },
    })).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    expect(foreignRequestDatabase).not.toHaveBeenCalledWith('staff');
    expect(globalDatabase).not.toHaveBeenCalled();
  });

  it('stores the authenticated actor separately from the staff reviewer reference', async () => {
    const feedbackId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    const directusUserId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const inserts: Array<{ table: string; row: Record<string, unknown> }> = [];
    const database = (table: string) => ({
      insert: async (row: Record<string, unknown>) => {
        inserts.push({ table, row });
      },
    });
    const actions = new Map<string, Array<(...args: any[]) => Promise<void>>>();

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: (event: string, callback: (...args: any[]) => Promise<void>) => {
          const callbacks = actions.get(event) || [];
          callbacks.push(callback);
          actions.set(event, callbacks);
        },
        schedule: () => undefined,
      },
      { database, env: {} },
    );

    const feedbackAction = actions.get('stakeholder_feedback.items.update')?.at(-1);
    expect(feedbackAction).toBeDefined();
    await feedbackAction!({
      keys: [feedbackId],
      payload: { status: 'published' },
      accountability: { user: directusUserId },
    });
    await feedbackAction!({
      keys: [feedbackId],
      payload: { status: 'rejected', rejection_reason: 'Please review.' },
      accountability: { user: directusUserId },
    });

    expect(inserts).toEqual([{
      table: 'stakeholder_feedback_review',
      row: {
        feedback_id: feedbackId,
        reviewer_id: null,
        action: 'published_summary',
        response_text: 'Public summary published.',
        metadata: { actor_directus_user_id: directusUserId },
      },
    }, {
      table: 'stakeholder_feedback_review',
      row: {
        feedback_id: feedbackId,
        reviewer_id: null,
        action: 'dismissed',
        response_text: 'Please review.',
        metadata: { actor_directus_user_id: directusUserId },
      },
    }]);
  });

  it('binds Directus update reads and workflow checks to the request database', async () => {
    const globalDatabase = vi.fn();
    const requestTables: string[] = [];
    const requestDatabase = vi.fn((table: string) => {
      requestTables.push(table);
      const builder: any = {
        where: vi.fn(() => builder),
        first: vi.fn(async () => {
          if (table === 'stakeholder_feedback') {
            return { status: 'submitted', is_public: false };
          }
          if (table === 'metric_proposal') {
            return { status: 'proposed', proposal_date: '2020-01-01' };
          }
          if (table === 'impact_claim') {
            return { status: 'submitted', public_claim: false };
          }
          if (table === 'farm_activity') return { status: 'submitted' };
          if (table === 'sales_event') {
            return { total_amount: 100, return_amount: 0, discount_amount: 0 };
          }
          return undefined;
        }),
      };
      return builder;
    });
    const filters = new Map<string, Array<(...args: any[]) => Promise<any>>>();

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => Promise<any>) => {
          const callbacks = filters.get(event) || [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database: globalDatabase, env: {} },
    );

    const context = { database: requestDatabase };
    await filters.get('stakeholder_feedback.items.update')?.at(-1)?.(
      { consent_notes: 'reviewed' },
      { keys: ['feedback-1'], accountability: { admin: true } },
      context,
    );
    await filters.get('metric_proposal.items.update')?.at(-1)?.(
      { status: 'discussed' },
      { keys: ['proposal-1'] },
      context,
    );
    await filters.get('impact_claim.items.update')?.at(-1)?.(
      { status: 'verified' },
      { keys: ['claim-1'], accountability: { admin: true } },
      context,
    );
    await filters.get('farm_activity.items.update')?.at(-1)?.(
      { status: 'verified' },
      { keys: ['activity-1'], accountability: { admin: true } },
      context,
    );
    await filters.get('sales_event.items.update')?.at(-1)?.(
      { total_amount: 100 },
      { keys: ['sale-1'], accountability: { admin: true } },
      context,
    );

    expect(requestTables).toEqual(expect.arrayContaining([
      'stakeholder_feedback',
      'metric_proposal',
      'impact_claim',
      'farm_activity',
      'sales_event',
    ]));
    expect(globalDatabase).not.toHaveBeenCalled();
  });

  it('does not register Directus schedules unless explicitly enabled', () => {
    const schedules: string[] = [];
    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: () => undefined,
        schedule: (cron: string) => schedules.push(cron),
      },
      { database: {}, env: {} },
    );

    expect(schedules).toEqual([]);
  });

  it('registers each Directus schedule only for its explicit flag', () => {
    const schedules: string[] = [];
    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: () => undefined,
        schedule: (cron: string) => schedules.push(cron),
      },
      {
        database: {},
        env: {
          KOKONUT_DIRECTUS_SCHEDULE_NOI_RECONCILIATION: ' TRUE ',
          KOKONUT_DIRECTUS_SCHEDULE_WEEKLY_ACTIVITY_AGGREGATION: 'false',
        },
      },
    );

    expect(schedules).toEqual(['0 2 * * *']);
  });

  it('rejects cross-location references on scoped updates using the request transaction', async () => {
    const locationA = '11111111-1111-4111-8111-111111111111';
    const locationB = '22222222-2222-4222-8222-222222222222';
    const rowId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    const cropCycleId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
    const operatorId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
    const issuer = 'https://identity.example.test';
    const userId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const globalDatabase = vi.fn();
    const requestDatabase = vi.fn((table: string) => {
      const builder: any = {
        select: vi.fn(() => builder),
        distinct: vi.fn(() => builder),
        where: vi.fn(() => builder),
        whereIn: vi.fn(() => builder),
        whereNull: vi.fn(() => builder),
        whereNotNull: vi.fn(() => builder),
        whereRaw: vi.fn(() => builder),
        first: vi.fn(async () => {
          if (table === 'public.directus_users') return { external_identifier: 'test-subject' };
          if (table === 'public.operator_identity') return { id: operatorId };
          if (table === 'public.operator_scope_grant as grant_row') return { location_id: locationA };
          if (table === 'crop_cycle') return { location_id: locationB };
          return undefined;
        }),
        then: (resolve: (value: unknown) => unknown, reject: (reason: unknown) => unknown) => (
          Promise.resolve(table === 'public.expense_event'
            ? [{ id: rowId, location_id: locationA }]
            : []).then(resolve, reject)
        ),
      };
      return builder;
    });
    const filters = new Map<string, Array<(...args: any[]) => Promise<any>>>();

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => Promise<any>) => {
          const callbacks = filters.get(event) || [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database: globalDatabase, env: { KOKONUT_OPERATOR_OIDC_ISSUER: issuer } },
    );

    const authorizeAndValidateUpdate = filters.get('expense_event.items.update')?.[0];
    expect(authorizeAndValidateUpdate).toBeDefined();
    await expect(authorizeAndValidateUpdate!(
      { crop_cycle_id: cropCycleId },
      { keys: [rowId] },
      { database: requestDatabase, accountability: { user: userId } },
    )).rejects.toMatchObject({ code: 'INVALID_PAYLOAD', status: 400 });

    expect(requestDatabase).toHaveBeenCalledWith('crop_cycle');
    expect(globalDatabase).not.toHaveBeenCalled();
  });

  it('keeps financial ClickHouse delivery in the transactional PostgreSQL outbox', async () => {
    const actions = new Map<string, (...args: any[]) => Promise<void>>();
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: (event: string, callback: (...args: any[]) => Promise<void>) => {
          actions.set(event, callback);
        },
        schedule: () => undefined,
      },
      { database: {} },
    );

    await actions.get('sales_event.items.create')!({ payload: { id: 'sale-1', total_amount: 12 } });
    await actions.get('expense_event.items.create')!({ payload: { id: 'expense-1', amount: 8 } });

    expect(fetch).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it('reports the weekly Directus query as an aggregation, not persisted snapshots', async () => {
    const schedules = new Map<string, () => Promise<void>>();
    const rows = [{ week: '2026-10-19', location_id: 'location-a', activity_count: 3 }];
    const queryCalls: string[] = [];
    const write = vi.fn();
    const database = Object.assign((table: string) => {
      queryCalls.push(`table:${table}`);
      const builder: any = {
        where: vi.fn((...args: unknown[]) => {
          queryCalls.push(`where:${args[0]}`);
          return builder;
        }),
        whereRaw: vi.fn(() => {
          queryCalls.push('whereRaw');
          return builder;
        }),
        select: vi.fn(() => {
          queryCalls.push('select');
          return builder;
        }),
        groupBy: vi.fn(() => {
          queryCalls.push('groupBy');
          return builder;
        }),
        insert: write,
        update: write,
        delete: write,
        then: (resolve: (value: unknown) => unknown) => Promise.resolve(rows).then(resolve),
      };
      return builder;
    }, {
      raw: vi.fn((sql: string) => sql),
    });
    const log = vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: () => undefined,
        schedule: (cron: string, callback: () => Promise<void>) => {
          schedules.set(cron, callback);
        },
      },
      { database, env: { KOKONUT_DIRECTUS_SCHEDULE_WEEKLY_ACTIVITY_AGGREGATION: 'true' } },
    );

    await schedules.get('0 3 * * 0')!();

    expect(queryCalls).toEqual([
      'table:farm_activity',
      'where:status',
      'whereRaw',
      'select',
      'groupBy',
    ]);
    expect(log).toHaveBeenCalledWith(
      '[Kokonut] Weekly verified farm activity query returned 1 location-week rows; no snapshot records were persisted',
    );
    expect(log.mock.calls.flat().join(' ')).not.toContain('snapshots created');
    expect(error).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
    log.mockRestore();
    error.mockRestore();
  });

  it('wires the pre-read tenant filter to request accountability, issuer, and transaction', async () => {
    const callbacks = new Map<string, (...args: any[]) => Promise<any>>();
    const tables: string[] = [];
    const locationId = '11111111-1111-4111-8111-111111111111';
    const userId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const operatorId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
    const subject = 'zitadel-subject';
    const issuer = 'https://identity.example.test';

    const database = (table: string) => {
      tables.push(table);
      const builder: any = {
        select: () => builder,
        distinct: () => builder,
        where: () => builder,
        whereNull: () => builder,
        whereNotNull: () => builder,
        whereRaw: () => builder,
        first: async () => table === 'public.directus_users'
          ? { external_identifier: subject }
          : table === 'public.operator_identity'
            ? { id: operatorId }
            : undefined,
        then: (resolve: (value: any) => any, reject: (reason: any) => any) => (
          Promise.resolve(table === 'public.operator_scope_grant as grant_row'
            ? [{ location_id: locationId }]
            : []).then(resolve, reject)
        ),
      };
      return builder;
    };

    const filter = (event: string, callback: (...args: any[]) => Promise<any>) => {
      callbacks.set(event, callback);
    };
    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      { filter, action: () => undefined, schedule: () => undefined },
      { database, env: { KOKONUT_OPERATOR_OIDC_ISSUER: issuer } },
    );

    const filterQuery = callbacks.get('farm_activity.items.query');
    expect(filterQuery).toBeDefined();
    const requestDatabase = database;
    const input = { filter: { status: { _eq: 'draft' } } };
    const result = await filterQuery!(input, { collection: 'farm_activity' }, {
      database: requestDatabase,
      accountability: { user: userId },
    });

    expect(result.filter).toEqual({
      _and: [
        { status: { _eq: 'draft' } },
        { location_id: { _in: [locationId] } },
      ],
    });
    expect(tables).toEqual([
      'public.directus_users',
      'public.operator_identity',
      'public.operator_scope_grant as grant_row',
    ]);
  });
});
