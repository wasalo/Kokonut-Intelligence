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
      { database: {} },
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
