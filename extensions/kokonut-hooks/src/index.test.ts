import { describe, expect, it, vi } from 'vitest';
import registerHook, { resolveHookDatabase } from './index.js';
import { consumePendingTransition } from './workflow.js';
import { TENANT_SCOPED_COLLECTIONS } from './directus-authorization.js';

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
    for (const collection of TENANT_SCOPED_COLLECTIONS) {
      for (const operation of ['query', 'read', 'create', 'update', 'delete']) {
        expect(events, `${collection} ${operation} authorization hook`)
          .toContain(`${collection}.items.${operation}`);
      }
    }
  });

  it('rejects legacy dashboard SQL writes while allowing registered query IDs', () => {
    const filters = new Map<string, Array<(...args: any[]) => any>>();

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => any) => {
          const callbacks = filters.get(event) ?? [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database: () => undefined, env: {} },
    );

    for (const operation of ['create', 'update']) {
      const hook = filters.get(`dashboard_dataset.items.${operation}`)?.[0];
      expect(hook).toBeDefined();
      let thrown: unknown;
      try {
        hook!({ query_id: 'public_farm_summary_count', query_sql: null });
      } catch (error) {
        thrown = error;
      }
      expect(thrown).toMatchObject({
        code: 'INVALID_PAYLOAD',
        status: 400,
        message: 'dashboard_dataset.query_sql is read-only; use query_id',
      });
      const payload = { query_id: 'public_farm_summary_count' };
      expect(hook!(payload)).toBe(payload);
    }
  });

  it('blocks dashboard query side channels before querying Directus data', async () => {
    const filters = new Map<string, Array<(...args: any[]) => any>>();
    const database = vi.fn();

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => any) => {
          const callbacks = filters.get(event) ?? [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database, env: {} },
    );

    const queryHook = filters.get('dashboard_dataset.items.query')?.[0];
    expect(queryHook).toBeDefined();
    for (const query of [
      { fields: ['id', 'query_sql'] },
      { filter: { query_sql: { _contains: 'secret' } } },
      { sort: ['query_sql'] },
      { search: 'private_schema' },
    ]) {
      await expect(queryHook!(query, {}, { database })).rejects.toMatchObject({
        code: 'FORBIDDEN',
        status: 403,
      });
    }
    expect(database).not.toHaveBeenCalled();
  });

  it('redacts legacy dashboard SQL after tenant read authorization', async () => {
    const filters = new Map<string, Array<(...args: any[]) => any>>();
    const datasetId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    const locationId = '11111111-1111-4111-8111-111111111111';
    const operatorId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
    const userId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const dataset = {
      id: datasetId,
      location_id: locationId,
      query_id: 'public_farm_summary_count',
      query_sql: 'SELECT private_schema.sensitive_rows',
    };
    const database = vi.fn((table: string) => {
      const rows = table === 'public.operator_scope_grant as grant_row'
        ? [{ location_id: locationId }]
        : table === 'public.dashboard_dataset'
          ? [{ id: datasetId, location_id: locationId }]
          : [];
      const first = table === 'public.directus_users'
        ? { external_identifier: 'external-subject' }
        : table === 'public.operator_identity'
          ? { id: operatorId }
          : undefined;
      const builder: Record<string, any> = {
        select: () => builder,
        distinct: () => builder,
        where: () => builder,
        whereNull: () => builder,
        whereNotNull: () => builder,
        whereRaw: () => builder,
        whereIn: () => builder,
        first: async () => first,
        then: (resolve: (value: unknown) => unknown, reject: (error: unknown) => unknown) => (
          Promise.resolve(rows).then(resolve, reject)
        ),
      };
      return builder;
    });

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => any) => {
          const callbacks = filters.get(event) ?? [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database, env: { KOKONUT_OPERATOR_OIDC_ISSUER: 'https://identity.example.test' } },
    );

    const readFilter = filters.get('dashboard_dataset.items.read')?.[0];
    const result = await readFilter!([dataset], {}, {
      accountability: { user: userId },
      database,
    });

    expect(result).toEqual([{
      id: datasetId,
      location_id: locationId,
      query_id: 'public_farm_summary_count',
    }]);
    expect(dataset.query_sql).toBe('SELECT private_schema.sensitive_rows');
  });

  it('fails closed when tenant item hooks lack the request transaction database', async () => {
    const globalDatabase = vi.fn();
    const filters = new Map<string, Array<(...args: any[]) => Promise<any>>>();
    const userId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const rowId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    const locationId = '11111111-1111-4111-8111-111111111111';

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => Promise<any>) => {
          const callbacks = filters.get(event) ?? [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database: globalDatabase, env: { KOKONUT_OPERATOR_OIDC_ISSUER: 'https://identity.example.test' } },
    );

    const cases: Array<[string, unknown, Record<string, unknown>]> = [
      ['farm_activity.items.query', { filter: {} }, {}],
      ['farm_activity.items.read', [{ id: rowId, location_id: locationId }], {}],
      ['farm_activity.items.create', { location_id: locationId }, {}],
      ['farm_activity.items.update', {}, { keys: [rowId] }],
      ['farm_activity.items.delete', [rowId], {}],
      ['stakeholder_feedback_review.items.create', { feedback_id: rowId }, {}],
    ];

    for (const [event, payload, meta] of cases) {
      const filter = filters.get(event)?.[0];
      expect(filter).toBeDefined();
      await expect(Promise.resolve().then(() => filter!(
        payload, meta, { accountability: { user: userId } },
      )))
        .rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    }
    expect(globalDatabase).not.toHaveBeenCalled();
  });

  it('keeps tenant lifecycle and business filters on the request database', async () => {
    const globalDatabase = vi.fn();
    const filters = new Map<string, Array<(...args: any[]) => Promise<any>>>();
    const userId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const tenantCollections = TENANT_SCOPED_COLLECTIONS;

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => Promise<any>) => {
          const callbacks = filters.get(event) ?? [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: () => undefined,
        schedule: () => undefined,
      },
      { database: globalDatabase, env: { KOKONUT_OPERATOR_OIDC_ISSUER: 'https://identity.example.test' } },
    );

    for (const collection of tenantCollections) {
      const hooks = filters.get(`${collection}.items.update`);
      expect(hooks?.length, `${collection} update hooks`).toBeGreaterThanOrEqual(2);
      for (const hook of hooks!.slice(1)) {
        await expect(hook({}, { keys: [] }, { accountability: { user: userId } }))
          .rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
      }
    }
    expect(globalDatabase).not.toHaveBeenCalled();
  });

  it('preserves request database selection and non-tenant extension fallback', () => {
    const requestDatabase = vi.fn();
    const extensionDatabase = vi.fn();

    expect(resolveHookDatabase('farm_activity', { database: requestDatabase }, extensionDatabase))
      .toBe(requestDatabase);
    expect(() => resolveHookDatabase('farm_activity', {}, extensionDatabase))
      .toThrowError(/Directus tenant access denied/);
    expect(() => resolveHookDatabase('farm_activity', { database: {} }, extensionDatabase))
      .toThrowError(/Directus tenant access denied/);
    expect(resolveHookDatabase('agent_task', {}, extensionDatabase)).toBe(extensionDatabase);
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

  it('records feedback decisions through the request transaction before the item update', async () => {
    const feedbackId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    const directusUserId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    const inserts: Array<{ table: string; row: Record<string, unknown> }> = [];
    const workflowAudits: Array<Record<string, unknown>> = [];
    const operations: string[] = [];
    const statuses = ['verified', 'verified', 'submitted', 'submitted', 'verified', 'verified'];
    const requestDatabase = vi.fn((table: string) => {
      const builder: any = {
        where: vi.fn(() => builder),
        first: vi.fn(async () => {
          if (table === 'stakeholder_feedback') {
            operations.push('feedback-read');
            return {
              status: statuses.shift(),
              is_public: false,
              submitted_at: '2020-01-01T00:00:00Z',
            };
          }
          return undefined;
        }),
        insert: vi.fn(async (row: Record<string, unknown>) => {
          if (table === 'workflow_history') {
            operations.push('workflow-audit');
            workflowAudits.push(row);
          } else {
            operations.push('review-insert');
            inserts.push({ table, row });
          }
        }),
      };
      return builder;
    });
    const globalDatabase = vi.fn();
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

    const feedbackUpdate = filters.get('stakeholder_feedback.items.update')?.at(-1);
    expect(feedbackUpdate).toBeDefined();
    const context = { database: requestDatabase };
    await feedbackUpdate!({ status: 'published' }, {
      keys: [feedbackId],
      accountability: { admin: true, user: directusUserId },
    }, context);
    await feedbackUpdate!({ status: 'rejected', rejection_reason: 'Please review.' }, {
      keys: [feedbackId],
      accountability: { admin: true, user: directusUserId },
    }, context);

    await expect(feedbackUpdate!({ status: 'published' }, {
      keys: [feedbackId],
      accountability: { admin: true, user: directusUserId },
    }, {
      database: vi.fn((table: string) => {
        const builder: any = {
          where: vi.fn(() => builder),
          first: vi.fn(async () => ({
            status: table === 'stakeholder_feedback' ? 'verified' : undefined,
            is_public: false,
            submitted_at: '2020-01-01T00:00:00Z',
          })),
          insert: vi.fn(async () => {
            if (table === 'stakeholder_feedback_review') {
              throw new Error('review storage unavailable');
            }
          }),
        };
        return builder;
      }),
    })).rejects.toThrow('review storage unavailable');
    expect(consumePendingTransition('stakeholder_feedback', feedbackId)).toBeUndefined();
    expect(workflowAudits).toEqual([
      expect.objectContaining({
        collection: 'stakeholder_feedback',
        from_status: 'verified',
        to_status: 'published',
      }),
      expect.objectContaining({
        collection: 'stakeholder_feedback',
        from_status: 'submitted',
        to_status: 'rejected',
        rejection_reason: 'Please review.',
      }),
    ]);

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
    expect(operations).toEqual([
      'feedback-read', 'feedback-read', 'workflow-audit', 'review-insert',
      'feedback-read', 'feedback-read', 'workflow-audit', 'review-insert',
    ]);
    expect(globalDatabase).not.toHaveBeenCalled();
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
        insert: vi.fn(async () => undefined),
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

  it('records tenant lifecycle and metric-proposal audit through the request transaction', async () => {
    const globalDatabase = vi.fn();
    const writes: Array<{ table: string; row: Record<string, unknown> }> = [];
    const requestDatabase = vi.fn((table: string) => {
      const builder = {
        where: () => builder,
        first: async () => table === 'metric_proposal'
          ? { status: 'proposed', proposal_date: '2020-01-01' }
          : { status: 'submitted' },
        insert: async (row: Record<string, unknown>) => {
        writes.push({ table, row });
        },
      };
      return builder;
    });
    const filters = new Map<string, Array<(...args: any[]) => Promise<any>>>();
    const actions = new Set<string>();

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: (event: string, callback: (...args: any[]) => Promise<any>) => {
          const callbacks = filters.get(event) ?? [];
          callbacks.push(callback);
          filters.set(event, callbacks);
        },
        action: (event: string) => actions.add(event),
        schedule: () => undefined,
      },
      { database: globalDatabase, env: {} },
    );

    const payload = { status: 'verified' };
    await expect(filters.get('farm_activity.items.update')?.at(-1)?.(
      payload,
      { keys: ['activity-1'], accountability: { admin: true, user: 'operator-1' } },
      { database: requestDatabase },
    )).resolves.toBe(payload);
    const proposalPayload = { status: 'discussed' };
    await expect(filters.get('metric_proposal.items.update')?.at(-1)?.(
      proposalPayload,
      { keys: ['proposal-1'], accountability: { admin: true, user: 'operator-1' } },
      { database: requestDatabase },
    )).resolves.toBe(proposalPayload);

    expect(writes).toEqual([
      {
        table: 'workflow_history',
        row: {
          collection: 'farm_activity',
          record_id: 'activity-1',
          from_status: 'submitted',
          to_status: 'verified',
          changed_by: 'operator-1',
          notes: null,
          rejection_reason: null,
        },
      },
      {
        table: 'workflow_history',
        row: {
          collection: 'metric_proposal',
          record_id: 'proposal-1',
          to_status: 'discussed',
          changed_by: 'operator-1',
          notes: null,
        },
      },
    ]);
    expect(requestDatabase).toHaveBeenCalledWith('farm_activity');
    expect(requestDatabase).toHaveBeenCalledWith('metric_proposal');
    expect(requestDatabase).toHaveBeenCalledWith('workflow_history');
    expect(actions.has('farm_activity.items.update')).toBe(false);
    expect(actions.has('metric_proposal.items.update')).toBe(false);
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

  it('recalculates NOI using the event request database without global fallback', async () => {
    const actions = new Map<string, (...args: any[]) => Promise<void>>();
    const globalDatabase = vi.fn();
    const requestTables: string[] = [];
    const snapshots: Array<Record<string, unknown>> = [];
    const requestDatabase = vi.fn((table: string) => {
      requestTables.push(table);
      const builder: any = {
        where: vi.fn(() => builder),
        first: vi.fn(async () => ({
          crop_cycle_id: 'cycle-1',
          location_id: 'location-1',
          period_start: '2026-01-01T00:00:00Z',
          period_end: '2026-01-31T00:00:00Z',
          gross_revenue: '100',
          returns_discounts: '0',
          net_revenue: '100',
          direct_crop_costs: '40',
          allocated_shared_costs: '10',
          total_costs: '50',
          noi: '50',
          operating_margin_pct: '50',
          loss_rate_pct: '0',
        })),
      };
      builder.insert = vi.fn((row: Record<string, unknown>) => ({
        onConflict: vi.fn(() => ({
          merge: vi.fn(async () => { snapshots.push(row); }),
        })),
      }));
      return builder;
    });

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: () => undefined,
        action: (event: string, callback: (...args: any[]) => Promise<void>) => {
          actions.set(event, callback);
        },
        schedule: () => undefined,
      },
      { database: globalDatabase, env: {} },
    );

    for (const event of [
      'harvest_event.items.create',
      'sales_event.items.create',
      'expense_event.items.create',
    ]) {
      await actions.get(event)!(
        { payload: { crop_cycle_id: 'cycle-1' } },
        { database: requestDatabase },
      );
    }

    expect(requestTables).toEqual([
      'v_crop_cycle_noi', 'noi_snapshot',
      'v_crop_cycle_noi', 'noi_snapshot',
      'v_crop_cycle_noi', 'noi_snapshot',
    ]);
    expect(snapshots).toHaveLength(3);
    expect(snapshots[0]).toMatchObject({
      crop_cycle_id: 'cycle-1',
      location_id: 'location-1',
      noi: 50,
    });
    expect(globalDatabase).not.toHaveBeenCalled();

    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    await actions.get('harvest_event.items.create')!(
      { payload: { crop_cycle_id: 'cycle-1' } },
      { database: undefined },
    );
    expect(globalDatabase).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith('[Kokonut] Skipping NOI recalculation: request database unavailable');
    error.mockRestore();
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
