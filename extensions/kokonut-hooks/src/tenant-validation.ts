import { createError } from '@directus/errors';
import { TENANT_SCOPED_COLLECTIONS } from './directus-authorization.js';

type TenantReferenceLookup = (
  database: any,
  referenceId: string,
) => Promise<{ location_id?: string | null } | undefined>;

const TENANT_REFERENCE_LOOKUPS: Record<string, TenantReferenceLookup> = {
  farm_id: (database, referenceId) => database('farm')
    .where('id', referenceId)
    .first('location_id'),
  plot_id: (database, referenceId) => database('plot as plot_ref')
    .join('farm as farm_ref', 'plot_ref.farm_id', 'farm_ref.id')
    .where('plot_ref.id', referenceId)
    .first('farm_ref.location_id as location_id'),
  crop_cycle_id: (database, referenceId) => database('crop_cycle')
    .where('id', referenceId)
    .first('location_id'),
  harvest_id: (database, referenceId) => database('harvest_event')
    .where('id', referenceId)
    .first('location_id'),
};

const InvalidTenantPayloadError = createError<{ message: string }>(
  'INVALID_PAYLOAD',
  ({ message }) => message,
  400,
);

function invalidTenantPayload(message: string): Error {
  return new InvalidTenantPayloadError({ message });
}

function isUuid(value: unknown): value is string {
  return typeof value === 'string' &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

async function validateReferencesAtLocation(
  database: any,
  locationId: string,
  payload: Record<string, any>,
): Promise<void> {
  for (const [field, lookup] of Object.entries(TENANT_REFERENCE_LOOKUPS)) {
    const referenceId = payload[field];
    if (referenceId === undefined || referenceId === null) continue;
    if (!isUuid(referenceId)) throw invalidTenantPayload(`Invalid ${field}`);

    const reference = await lookup(database, referenceId);
    if (!reference) throw invalidTenantPayload(`Unknown ${field}`);
    if (reference.location_id !== locationId) {
      throw invalidTenantPayload(`${field} belongs to a different location`);
    }
  }
}

/** Validate foreign references against the record's explicit location. */
export async function validateTenantReferences(
  database: any,
  collection: string,
  payload: Record<string, any>
): Promise<Record<string, any>> {
  if (!(TENANT_SCOPED_COLLECTIONS as readonly string[]).includes(collection)) return payload;

  const locationId = payload.location_id;
  // The request-level authorization hook rejects missing/null tenant scope;
  // this helper validates only the explicit scope and its foreign references.
  // An explicitly supplied but malformed scope must never skip validation.
  if (locationId !== undefined && locationId !== null && !isUuid(locationId)) {
    throw invalidTenantPayload('Invalid location_id');
  }
  if (locationId === undefined || locationId === null) return payload;

  await validateReferencesAtLocation(database, locationId, payload);

  return payload;
}

/** Validate changed references against every authorized target row's location. */
export async function validateTenantReferencesForRows(
  database: any,
  collection: string,
  payload: Record<string, any>,
  rows: ReadonlyArray<{ location_id: string | null }>,
): Promise<Record<string, any>> {
  if (!(TENANT_SCOPED_COLLECTIONS as readonly string[]).includes(collection)) return payload;
  if (rows.length === 0) throw invalidTenantPayload('No tenant rows to validate');
  if (payload.location_id !== undefined && payload.location_id !== null && !isUuid(payload.location_id)) {
    throw invalidTenantPayload('Invalid location_id');
  }

  const locationIds = new Set<string>();
  for (const row of rows) {
    if (!isUuid(row.location_id)) throw invalidTenantPayload('Invalid location_id');
    if (payload.location_id !== undefined && payload.location_id !== row.location_id) {
      throw invalidTenantPayload('location_id cannot be changed');
    }
    locationIds.add(row.location_id);
  }

  for (const locationId of locationIds) {
    await validateReferencesAtLocation(database, locationId, payload);
  }

  return payload;
}
