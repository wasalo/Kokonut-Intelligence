import { describe, expect, it, vi } from 'vitest';
import {
  authorizeDirectusCreate,
  authorizeDirectusFeedbackReviewCreate,
  authorizeDirectusRead,
  authorizeDirectusReadResult,
  authorizeDirectusRows,
  createDirectusTenantStore,
  READ_ONLY_TENANT_SCOPED_COLLECTIONS,
  TENANT_SCOPED_COLLECTIONS,
  type DirectusTenantStore,
} from './directus-authorization.js';

const locationA = '11111111-1111-4111-8111-111111111111';
const locationB = '22222222-2222-4222-8222-222222222222';
const rowA = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const rowB = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const operatorId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const issuer = 'https://identity.example.test';
const accountability = { user: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd' };

function makeStore(overrides: Partial<DirectusTenantStore> = {}) {
  const store: DirectusTenantStore = {
    resolveOperator: vi.fn().mockResolvedValue(operatorId),
    authorizedLocations: vi.fn().mockResolvedValue([locationA]),
    canAccessLocation: vi.fn().mockImplementation(async (_operator, _collection, _action, location) => (
      location === locationA
    )),
    loadRows: vi.fn().mockImplementation(async (_collection, ids: string[]) => (
      ids.filter((id) => id === rowA || id === rowB).map((id) => ({
        id,
        location_id: id === rowA ? locationA : locationB,
      }))
    )),
    ...overrides,
  };
  return store;
}

describe('Directus tenant authorization', () => {
  it('requires exact location grants for every reviewed tenant-scoped collection', async () => {
    expect(TENANT_SCOPED_COLLECTIONS).toEqual([
      'farm_activity',
      'harvest_event',
      'expense_event',
      'sales_event',
      'loss_event',
      'labor_event',
      'field_note',
      'forecast_scenario',
      'forecast_output',
      'water_access',
      'capex_breakdown',
      'report_snapshot',
      'noi_snapshot',
      'dashboard_dataset',
      'farm_registry_record',
      'inventory_event',
      'maintenance_event',
      'revenue_event',
      'stakeholder_outcome',
      'stakeholder_feedback',
      'credit_batch',
      'project_credit_class_enrollment',
      'retirement_certificate',
      'metric_proposal',
      'mrv_claim',
      'metric_value',
    ]);
    expect(READ_ONLY_TENANT_SCOPED_COLLECTIONS).toEqual([
      'retirement_certificate',
      'metric_value',
      'forecast_output',
      'noi_snapshot',
      'water_access',
      'capex_breakdown',
    ]);

    const store = makeStore();
    for (const collection of TENANT_SCOPED_COLLECTIONS) {
      await expect(authorizeDirectusRead(
        store, accountability, issuer, collection, {},
      )).resolves.toMatchObject({
        filter: { location_id: { _in: [locationA] } },
      });
      if ((READ_ONLY_TENANT_SCOPED_COLLECTIONS as readonly string[]).includes(collection)) {
        await expect(authorizeDirectusCreate(
          store, accountability, issuer, collection, { location_id: locationA },
        )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
        await expect(authorizeDirectusRows(
          store, accountability, issuer, collection, 'update', [rowA], {},
        )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
        await expect(authorizeDirectusRows(
          store, accountability, issuer, collection, 'delete', [rowA],
        )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
        continue;
      }
      await authorizeDirectusCreate(
        store, accountability, issuer, collection, { location_id: locationA },
      );
      await authorizeDirectusRows(
        store, accountability, issuer, collection, 'update', [rowA], {},
      );
      await authorizeDirectusRows(
        store, accountability, issuer, collection, 'delete', [rowA],
      );
      expect(store.authorizedLocations).toHaveBeenCalledWith(operatorId, collection, 'read');
      expect(store.canAccessLocation).toHaveBeenCalledWith(
        operatorId, collection, 'create', locationA,
      );
      expect(store.canAccessLocation).toHaveBeenCalledWith(
        operatorId, collection, 'update', locationA,
      );
      expect(store.canAccessLocation).toHaveBeenCalledWith(
        operatorId, collection, 'delete', locationA,
      );
    }
    const writableCollectionCount = TENANT_SCOPED_COLLECTIONS.length - READ_ONLY_TENANT_SCOPED_COLLECTIONS.length;
    expect(store.authorizedLocations).toHaveBeenCalledTimes(TENANT_SCOPED_COLLECTIONS.length);
    expect(store.canAccessLocation).toHaveBeenCalledTimes(writableCollectionCount * 3);
    expect(store.loadRows).toHaveBeenCalledTimes(writableCollectionCount * 2);
  });

  it('denies read-only collection writes before resolving identity or loading rows', async () => {
    const store = makeStore();
    for (const collection of READ_ONLY_TENANT_SCOPED_COLLECTIONS) {
      await expect(authorizeDirectusCreate(
        store, accountability, issuer, collection, { location_id: locationA },
      )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
      await expect(authorizeDirectusRows(
        store, accountability, issuer, collection, 'update', [rowA], {},
      )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
      await expect(authorizeDirectusRows(
        store, accountability, issuer, collection, 'delete', [rowA],
      )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    }

    expect(store.resolveOperator).not.toHaveBeenCalled();
    expect(store.canAccessLocation).not.toHaveBeenCalled();
    expect(store.loadRows).not.toHaveBeenCalled();
  });

  it('scopes metric-value reads and rejects unassigned rows', async () => {
    const store = makeStore();
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'metric_value', {
        fields: ['id', 'metric_id', 'location_id', 'value'],
      },
    )).resolves.toEqual({
      fields: ['id', 'metric_id', 'location_id', 'value'],
      filter: { location_id: { _in: [locationA] } },
    });
    expect(store.authorizedLocations).toHaveBeenCalledWith(
      operatorId, 'metric_value', 'read',
    );

    const unassigned = makeStore({
      loadRows: vi.fn().mockResolvedValue([{ id: rowA, location_id: null }]),
    });
    await expect(authorizeDirectusReadResult(
      unassigned, accountability, issuer, 'metric_value', { id: rowA },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('scopes forecast-output reads and rejects rows without a direct location', async () => {
    const store = makeStore();
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'forecast_output', { fields: ['id', 'location_id', 'value'] },
    )).resolves.toEqual({
      fields: ['id', 'location_id', 'value'],
      filter: { location_id: { _in: [locationA] } },
    });

    const unassigned = makeStore({
      loadRows: vi.fn().mockResolvedValue([{ id: rowA, location_id: null }]),
    });
    await expect(authorizeDirectusReadResult(
      unassigned, accountability, issuer, 'forecast_output', { id: rowA },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('scopes NOI snapshot reads by exact location and keeps the collection read-only', async () => {
    const store = makeStore();
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'noi_snapshot', {
        fields: ['id', 'location_id', 'period_start', 'period_end', 'noi'],
      },
    )).resolves.toEqual({
      fields: ['id', 'location_id', 'period_start', 'period_end', 'noi'],
      filter: { location_id: { _in: [locationA] } },
    });
    expect(store.authorizedLocations).toHaveBeenCalledWith(
      operatorId, 'noi_snapshot', 'read',
    );

    await expect(authorizeDirectusReadResult(
      store, accountability, issuer, 'noi_snapshot', { id: rowB },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });

    await expect(authorizeDirectusCreate(
      store, accountability, issuer, 'noi_snapshot', { location_id: locationA },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'noi_snapshot', 'update', [rowA], {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'noi_snapshot', 'delete', [rowA],
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('scopes water-access reads by exact location and denies Directus writes', async () => {
    const store = makeStore();
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'water_access', {
        fields: ['id', 'location_id', 'source_type', 'status'],
      },
    )).resolves.toEqual({
      fields: ['id', 'location_id', 'source_type', 'status'],
      filter: { location_id: { _in: [locationA] } },
    });
    expect(store.authorizedLocations).toHaveBeenCalledWith(
      operatorId, 'water_access', 'read',
    );

    await expect(authorizeDirectusReadResult(
      store, accountability, issuer, 'water_access', { id: rowB },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });

    await expect(authorizeDirectusCreate(
      store, accountability, issuer, 'water_access', { location_id: locationA },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'water_access', 'update', [rowA], {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'water_access', 'delete', [rowA],
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('scopes CAPEX breakdown reads to the granted location and denies Directus writes', async () => {
    const store = makeStore();
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'capex_breakdown', {
        fields: ['id', 'location_id', 'category', 'amount_usd'],
      },
    )).resolves.toEqual({
      fields: ['id', 'location_id', 'category', 'amount_usd'],
      filter: { location_id: { _in: [locationA] } },
    });
    expect(store.authorizedLocations).toHaveBeenCalledWith(
      operatorId, 'capex_breakdown', 'read',
    );

    await expect(authorizeDirectusReadResult(
      store, accountability, issuer, 'capex_breakdown', { id: rowB },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });

    await expect(authorizeDirectusCreate(
      store, accountability, issuer, 'capex_breakdown', { location_id: locationA },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'capex_breakdown', 'update', [rowA], {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'capex_breakdown', 'delete', [rowA],
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('maps active Directus OIDC subjects by exact issuer and excludes legacy null-tenant grants', async () => {
    const calls: Array<{ table: string; method: string; args: unknown[] }> = [];
    const database = (table: string) => {
      const builder: any = {};
      for (const method of ['select', 'distinct', 'where', 'whereNull', 'whereNotNull', 'whereRaw', 'whereIn']) {
        builder[method] = (...args: unknown[]) => {
          calls.push({ table, method, args });
          return builder;
        };
      }
      builder.first = async () => table === 'public.directus_users'
        ? { external_identifier: 'zitadel-subject' }
        : table === 'public.operator_identity'
          ? { id: operatorId }
          : { location_id: locationA };
      builder.then = (resolve: (value: any) => any, reject: (reason: any) => any) => (
        Promise.resolve(table === 'public.operator_scope_grant as grant_row'
          ? [{ location_id: locationA }]
          : []).then(resolve, reject)
      );
      return builder;
    };
    const store = createDirectusTenantStore(database);

    await expect(store.resolveOperator(accountability.user!, issuer)).resolves.toBe(operatorId);
    await expect(store.authorizedLocations(operatorId, 'farm_activity', 'read'))
      .resolves.toEqual([locationA]);
    await expect(store.canAccessLocation(operatorId, 'farm_activity', 'create', locationA))
      .resolves.toBe(true);

    expect(calls).toContainEqual({
      table: 'public.directus_users',
      method: 'where',
      args: [{ id: accountability.user, status: 'active' }],
    });
    expect(calls).toContainEqual({
      table: 'public.operator_identity',
      method: 'where',
      args: [{ issuer, subject: 'zitadel-subject', enabled: true }],
    });
    expect(calls.filter((call) => call.method === 'whereNotNull')).toHaveLength(2);
    expect(calls.some((call) => (
      call.method === 'whereRaw' &&
      String(call.args[0]).includes('public.operator_scope_grant_allows')
    ))).toBe(true);
  });

  it('resolves reads from the authenticated Directus user and configured issuer', async () => {
    const store = makeStore();
    const query = { filter: { status: { _eq: 'published' } }, limit: 25 };

    const result = await authorizeDirectusRead(
      store, accountability, issuer, 'farm_activity', query,
    );

    expect(store.resolveOperator).toHaveBeenCalledWith(accountability.user, issuer);
    expect(store.authorizedLocations).toHaveBeenCalledWith(operatorId, 'farm_activity', 'read');
    expect(result).toEqual({
      filter: {
        _and: [
          { status: { _eq: 'published' } },
          { location_id: { _in: [locationA] } },
        ],
      },
      limit: 25,
    });

    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'farm_activity', { filter: null },
    )).resolves.toMatchObject({ filter: { location_id: { _in: [locationA] } } });
  });

  it('fails closed on nested relation fields and deep relation queries', async () => {
    const store = makeStore();
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'farm_activity', {
        fields: ['id', 'related_collection.name'],
      },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'farm_activity', {
        deep: { related_collection: { _filter: { status: { _eq: 'published' } } } },
      },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'farm_activity', {
        fields: ['*', 'location_id'],
      },
    )).resolves.toMatchObject({
      filter: { location_id: { _in: [locationA] } },
    });
  });

  it('rejects relation predicates and relation-based ordering/grouping', async () => {
    const store = makeStore();
    const relationQueries = [
      { filter: { farm: { name: { _eq: 'Foreign farm' } } } },
      { filter: { _and: [{ status: { _eq: 'draft' } }, { farm: { id: { _eq: rowB } } }] } },
      { filter: { farm: { _some: { name: { _eq: 'Foreign farm' } } } } },
      { filter: { 'farm.name': { _eq: 'Foreign farm' } } },
      { sort: ['farm.name'] },
      { sort: '-farm.name' },
      { groupBy: ['farm.name'] },
    ];

    for (const query of relationQueries) {
      await expect(authorizeDirectusRead(
        store, accountability, issuer, 'farm_activity', query,
      )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    }

    // Scalar predicates, including structured JSON containment, remain
    // available because the JSON operand is not interpreted as a relation.
    await expect(authorizeDirectusRead(
      store, accountability, issuer, 'farm_activity', {
        filter: {
          _and: [
            { status: { _eq: 'draft' } },
            { metadata: { _contains: { source: 'field' } } },
          ],
        },
        sort: ['-created_at'],
        groupBy: ['status'],
      },
    )).resolves.toMatchObject({ filter: { _and: expect.any(Array) } });
  });

  it('fails closed when the user, issuer, operator, or grants are missing', async () => {
    await expect(authorizeDirectusRead(
      makeStore(), undefined, issuer, 'farm_activity', {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRead(
      makeStore(), accountability, undefined, 'farm_activity', {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRead(
      makeStore({ resolveOperator: vi.fn().mockResolvedValue(undefined) }),
      accountability, issuer, 'farm_activity', {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRead(
      makeStore({ authorizedLocations: vi.fn().mockResolvedValue([]) }),
      accountability, issuer, 'farm_activity', {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('checks both single and bulk read results against the granted locations', async () => {
    const store = makeStore();
    const own = { id: rowA, location_id: locationA };
    const projected = { id: own.id };
    await expect(authorizeDirectusReadResult(
      store, accountability, issuer, 'farm_activity', projected,
    )).resolves.toBe(projected);
    await expect(authorizeDirectusReadResult(
      store, accountability, issuer, 'farm_activity', [own, { id: rowB, location_id: locationB }],
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusReadResult(
      store, accountability, issuer, 'farm_activity', { id: rowB, location_id: locationB },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusReadResult(
      makeStore({ authorizedLocations: vi.fn().mockResolvedValue([]) }),
      accountability, issuer, 'farm_activity', [],
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('requires a create grant for a non-null location', async () => {
    const store = makeStore();
    await expect(authorizeDirectusCreate(
      store, accountability, issuer, 'farm_activity', { location_id: locationA },
    )).resolves.toBeUndefined();
    expect(store.canAccessLocation).toHaveBeenCalledWith(
      operatorId, 'farm_activity', 'create', locationA,
    );

    await expect(authorizeDirectusCreate(
      store, accountability, issuer, 'farm_activity', { location_id: null },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusCreate(
      makeStore({ canAccessLocation: vi.fn().mockResolvedValue(false) }),
      accountability, issuer, 'farm_activity', { location_id: locationB },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('scopes feedback-review creation to the exact parent feedback location', async () => {
    const store = makeStore();

    await expect(authorizeDirectusFeedbackReviewCreate(
      store, accountability, issuer, { feedback_id: rowA },
    )).resolves.toBe(locationA);
    expect(store.loadRows).toHaveBeenCalledWith('stakeholder_feedback', [rowA]);
    expect(store.authorizedLocations).toHaveBeenCalledWith(
      operatorId, 'stakeholder_feedback_review', 'create',
    );
    expect(store.canAccessLocation).toHaveBeenCalledWith(
      operatorId, 'stakeholder_feedback_review', 'create', locationA,
    );

    await expect(authorizeDirectusFeedbackReviewCreate(
      store, accountability, issuer, { feedback_id: rowB },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusFeedbackReviewCreate(
      store, accountability, issuer, { feedback_id: 'not-a-uuid' },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusFeedbackReviewCreate(
      makeStore({ authorizedLocations: vi.fn().mockResolvedValue([]) }),
      accountability, issuer, { feedback_id: rowA },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });

  it('checks every update/delete key and prohibits changing a row location', async () => {
    const store = makeStore();
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'farm_activity', 'update', [rowA],
      { description: 'updated' },
    )).resolves.toEqual([{ id: rowA, location_id: locationA }]);

    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'farm_activity', 'update', [rowA, rowB], {},
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'farm_activity', 'update', [rowA],
      { location_id: locationB },
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'farm_activity', 'delete', [rowB],
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
    await expect(authorizeDirectusRows(
      store, accountability, issuer, 'farm_activity', 'delete', [],
    )).rejects.toMatchObject({ code: 'FORBIDDEN', status: 403 });
  });
});
