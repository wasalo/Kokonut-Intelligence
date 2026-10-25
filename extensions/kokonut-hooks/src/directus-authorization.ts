import { createError } from '@directus/errors';

export const TENANT_SCOPED_COLLECTIONS = [
  'farm_activity',
  'harvest_event',
  'expense_event',
  'sales_event',
  'loss_event',
  'labor_event',
  'field_note',
  'revenue_event',
  'stakeholder_feedback',
  'metric_proposal',
  'mrv_claim',
] as const;

export type TenantScopedCollection = (typeof TENANT_SCOPED_COLLECTIONS)[number];
export type DirectusAction = 'read' | 'create' | 'update' | 'delete';

type Accountability = { user?: string | null } | null | undefined;
type TenantRow = { id: string; location_id: string | null };

export interface DirectusTenantStore {
  resolveOperator(userId: string, issuer: string): Promise<string | undefined>;
  authorizedLocations(operatorId: string, collection: string, action: DirectusAction): Promise<string[]>;
  canAccessLocation(
    operatorId: string,
    collection: string,
    action: DirectusAction,
    locationId: string,
  ): Promise<boolean>;
  loadRows(collection: string, ids: string[]): Promise<TenantRow[]>;
}

const ForbiddenTenantAccessError = createError<{ message: string }>(
  'FORBIDDEN',
  ({ message }) => message,
  403,
);

function deny(): Error {
  // Keep authorization failures deliberately generic so they do not reveal
  // whether a user, operator, grant, or location exists.
  return new ForbiddenTenantAccessError({ message: 'Directus tenant access denied' });
}

function isTenantCollection(collection: string): collection is TenantScopedCollection {
  return (TENANT_SCOPED_COLLECTIONS as readonly string[]).includes(collection);
}

function isUuid(value: unknown): value is string {
  return typeof value === 'string' &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function requestsRelationExpansion(query: Record<string, any>): boolean {
  const deep = query.deep;
  if (deep !== undefined && deep !== null) {
    if (typeof deep !== 'object' || Array.isArray(deep)) return true;
    if (Object.keys(deep).length > 0) return true;
  }

  const fields = query.fields;
  if (fields === undefined || fields === null) return false;
  const requestedFields = Array.isArray(fields)
    ? fields
    : typeof fields === 'string'
      ? fields.split(',')
      : null;
  if (!requestedFields || !requestedFields.every((field) => typeof field === 'string')) return true;

  return requestedFields.some((field: string) => {
    const normalized = field.trim();
    return normalized.length === 0 ||
      (normalized !== '*' && (normalized.includes('.') || normalized.includes('*')));
  });
}

/** Build the authorization store on the request's Knex transaction. */
export function createDirectusTenantStore(database: any): DirectusTenantStore {
  return {
    async resolveOperator(userId, issuer) {
      const user = await database('public.directus_users')
        .select('external_identifier')
        .where({ id: userId, status: 'active' })
        .first();
      const subject = user?.external_identifier;
      if (typeof subject !== 'string' || subject.length === 0) return undefined;

      const operator = await database('public.operator_identity')
        .select('id')
        .where({ issuer, subject, enabled: true })
        .first();
      return typeof operator?.id === 'string' ? operator.id : undefined;
    },

    async authorizedLocations(operatorId, collection, action) {
      const rows = await database('public.operator_scope_grant as grant_row')
        .distinct('grant_row.location_id')
        .where({
          'grant_row.operator_id': operatorId,
          'grant_row.resource': collection,
          'grant_row.action': action,
        })
        .whereNull('grant_row.revoked_at')
        .whereNotNull('grant_row.organization_id')
        .whereRaw(
          'public.operator_scope_grant_allows(?, grant_row.resource, grant_row.action, grant_row.location_id)',
          [operatorId],
        );
      return rows
        .map((row: { location_id?: unknown }) => row.location_id)
        .filter((locationId: unknown): locationId is string => isUuid(locationId));
    },

    async canAccessLocation(operatorId, collection, action, locationId) {
      const grant = await database('public.operator_scope_grant as grant_row')
        .select('grant_row.location_id')
        .where({
          'grant_row.operator_id': operatorId,
          'grant_row.resource': collection,
          'grant_row.action': action,
          'grant_row.location_id': locationId,
        })
        .whereNull('grant_row.revoked_at')
        .whereNotNull('grant_row.organization_id')
        .whereRaw(
          'public.operator_scope_grant_allows(?, grant_row.resource, grant_row.action, grant_row.location_id)',
          [operatorId],
        )
        .first();
      return Boolean(grant);
    },

    async loadRows(collection, ids) {
      return await database(`public.${collection}`)
        .select('id', 'location_id')
        .whereIn('id', ids);
    },
  };
}

async function resolveOperator(
  store: DirectusTenantStore,
  accountability: Accountability,
  issuer: unknown,
): Promise<string> {
  if (!accountability?.user || typeof issuer !== 'string' || issuer.trim() === '') throw deny();
  const operatorId = await store.resolveOperator(accountability.user, issuer);
  if (!operatorId) throw deny();
  return operatorId;
}

/** Add a grant-derived location predicate before Directus reads the collection. */
export async function authorizeDirectusRead(
  store: DirectusTenantStore,
  accountability: Accountability,
  issuer: unknown,
  collection: string,
  query: Record<string, any>,
): Promise<Record<string, any>> {
  if (!isTenantCollection(collection)) return query;
  const operatorId = await resolveOperator(store, accountability, issuer);
  const locations = await store.authorizedLocations(operatorId, collection, 'read');
  if (locations.length === 0 || !query || typeof query !== 'object' || Array.isArray(query)) throw deny();
  // Nested Directus fields/deep queries can traverse a relation whose own
  // authorization has not yet been mapped to an organization/location grant.
  // Keep the root row scoped and fail closed until each relation has a contract.
  if (requestsRelationExpansion(query)) throw deny();

  const tenantFilter = { location_id: { _in: [...new Set(locations)] } };
  return {
    ...query,
    filter: query.filter === undefined || query.filter === null
      ? tenantFilter
      : { _and: [query.filter, tenantFilter] },
  };
}

/** Defense in depth for Directus read paths that emit an item payload. */
export async function authorizeDirectusReadResult(
  store: DirectusTenantStore,
  accountability: Accountability,
  issuer: unknown,
  collection: string,
  payload: unknown,
): Promise<unknown> {
  if (!isTenantCollection(collection) || payload === null || payload === undefined) return payload;
  const operatorId = await resolveOperator(store, accountability, issuer);
  const locations = new Set(await store.authorizedLocations(operatorId, collection, 'read'));
  if (locations.size === 0) throw deny();
  const items = Array.isArray(payload) ? payload : [payload];
  const ids = items.map((item) => (
    item && typeof item === 'object' ? (item as Record<string, unknown>).id : undefined
  ));
  if (!ids.every(isUuid)) throw deny();
  const rows = await store.loadRows(collection, [...new Set(ids as string[])]);
  const rowById = new Map(rows.map((row) => [row.id, row]));
  if (rowById.size !== new Set(ids).size) throw deny();
  for (const id of new Set(ids as string[])) {
    const row = rowById.get(id);
    if (!row || !isUuid(row.location_id) || !locations.has(row.location_id)) throw deny();
  }
  return payload;
}

/** Require every target row to be in scope; bulk requests never partially pass. */
export async function authorizeDirectusRows(
  store: DirectusTenantStore,
  accountability: Accountability,
  issuer: unknown,
  collection: string,
  action: Exclude<DirectusAction, 'read' | 'create'>,
  requestedIds: unknown,
  payload?: Record<string, any>,
): Promise<TenantRow[]> {
  if (!isTenantCollection(collection)) return [];
  const operatorId = await resolveOperator(store, accountability, issuer);
  const ids = Array.isArray(requestedIds)
    ? requestedIds
    : requestedIds === undefined || requestedIds === null
      ? []
      : [requestedIds];
  if (ids.length === 0 || !ids.every(isUuid)) throw deny();

  const rows = await store.loadRows(collection, [...new Set(ids)]);
  const byId = new Map(rows.map((row) => [row.id, row]));
  if (byId.size !== new Set(ids).size) throw deny();

  for (const id of new Set(ids)) {
    const row = byId.get(id);
    if (!row || !isUuid(row.location_id)) throw deny();
    if (payload?.location_id !== undefined && payload.location_id !== row.location_id) throw deny();
    if (!await store.canAccessLocation(operatorId, collection, action, row.location_id)) throw deny();
  }

  return [...new Set(ids)].map((id) => byId.get(id)!);
}

/** Check the assigned location before a create; tenant rows cannot be global. */
export async function authorizeDirectusCreate(
  store: DirectusTenantStore,
  accountability: Accountability,
  issuer: unknown,
  collection: string,
  payload: Record<string, any>,
): Promise<void> {
  if (!isTenantCollection(collection)) return;
  const operatorId = await resolveOperator(store, accountability, issuer);
  if (!isUuid(payload?.location_id)) throw deny();
  if (!await store.canAccessLocation(operatorId, collection, 'create', payload.location_id)) throw deny();
}

/** Authorize the feedback-review child by its parent's tenant location. */
export async function authorizeDirectusFeedbackReviewCreate(
  store: DirectusTenantStore,
  accountability: Accountability,
  issuer: unknown,
  payload: Record<string, any>,
): Promise<string> {
  const operatorId = await resolveOperator(store, accountability, issuer);
  const locations = await store.authorizedLocations(
    operatorId,
    'stakeholder_feedback_review',
    'create',
  );
  const feedbackId = payload?.feedback_id;
  if (!isUuid(feedbackId) || locations.length === 0) throw deny();

  const rows = await store.loadRows('stakeholder_feedback', [feedbackId]);
  if (rows.length !== 1 || !isUuid(rows[0].location_id)) throw deny();
  const locationId = rows[0].location_id;
  if (!locations.includes(locationId) || !await store.canAccessLocation(
    operatorId,
    'stakeholder_feedback_review',
    'create',
    locationId,
  )) throw deny();

  return locationId;
}
