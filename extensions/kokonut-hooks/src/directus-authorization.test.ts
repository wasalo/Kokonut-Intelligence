import { describe, expect, it, vi } from 'vitest';
import {
  authorizeDirectusCreate,
  authorizeDirectusRead,
  authorizeDirectusReadResult,
  authorizeDirectusRows,
  createDirectusTenantStore,
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
