import { createError } from '@directus/errors';
import { TENANT_SCOPED_COLLECTIONS } from './directus-authorization.js';

type TenantReferenceLookup = (
  database: any,
  referenceId: string,
  locationId: string,
) => Promise<{ location_id?: string | null } | undefined>;

async function lookupStaffAtLocation(
  database: any,
  referenceId: string,
  locationId: string,
): Promise<{ location_id: string } | undefined> {
  const directlyAssigned = await database('staff')
    .where({ id: referenceId, location_id: locationId })
    .first('id');
  if (directlyAssigned) return { location_id: locationId };

  const farmMember = await database('farm_staff_member as member_ref')
    .join('farm as farm_ref', 'member_ref.farm_id', 'farm_ref.id')
    .where({
      'member_ref.staff_id': referenceId,
      'farm_ref.location_id': locationId,
    })
    .first('member_ref.staff_id');
  return farmMember ? { location_id: locationId } : undefined;
}

const TENANT_REFERENCE_LOOKUPS: Record<string, TenantReferenceLookup> = {
  farm_id: (database, referenceId, locationId) => database('farm')
    .where({ id: referenceId, location_id: locationId })
    .first('location_id'),
  plot_id: (database, referenceId, locationId) => database('plot as plot_ref')
    .join('farm as farm_ref', 'plot_ref.farm_id', 'farm_ref.id')
    .where({ 'plot_ref.id': referenceId, 'farm_ref.location_id': locationId })
    .first('farm_ref.location_id as location_id'),
  crop_cycle_id: (database, referenceId, locationId) => database('crop_cycle')
    .where({ id: referenceId, location_id: locationId })
    .first('location_id'),
  harvest_id: (database, referenceId, locationId) => database('harvest_event')
    .where({ id: referenceId, location_id: locationId })
    .first('location_id'),
  staff_id: lookupStaffAtLocation,
  reviewed_by: lookupStaffAtLocation,
  reviewer_id: lookupStaffAtLocation,
  parent_scenario_id: (database, referenceId, locationId) => database('forecast_scenario')
    .where({ id: referenceId, location_id: locationId })
    .first('location_id'),
  infrastructure_asset_id: (database, referenceId, locationId) => database('infrastructure_asset')
    .where({ id: referenceId, location_id: locationId })
    .first('location_id'),
  sensor_device_id: (database, referenceId, locationId) => database('sensor_device')
    .where({ id: referenceId, location_id: locationId })
    .first('location_id'),
  sensor_alert_id: (database, referenceId, locationId) => database('sensor_alert as alert_ref')
    .join('sensor_device as device_ref', 'alert_ref.sensor_device_id', 'device_ref.id')
    .where({
      'alert_ref.id': referenceId,
      'device_ref.location_id': locationId,
    })
    .first('device_ref.location_id as location_id'),
};

// These references are meaningful only on retirement certificates. Keep them
// collection-scoped: other tenant collections may use the same field names
// for unrelated or network-wide concepts.
const TENANT_COLLECTION_REFERENCE_LOOKUPS: Record<string, Record<string, TenantReferenceLookup>> = {
  retirement_certificate: {
    retirement_id: (database, referenceId, locationId) => database('credit_retirement')
      .where({ id: referenceId, location_id: locationId })
      .first('location_id'),
    credit_id: (database, referenceId, locationId) => database('carbon_credit')
      .where({ id: referenceId, location_id: locationId })
      .first('location_id'),
    credit_batch_id: (database, referenceId, locationId) => database('credit_batch')
      .where({ id: referenceId, location_id: locationId })
      .first('location_id'),
  },
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
  collection: string,
  locationId: string,
  payload: Record<string, any>,
): Promise<void> {
  const lookups = {
    ...TENANT_REFERENCE_LOOKUPS,
    ...TENANT_COLLECTION_REFERENCE_LOOKUPS[collection],
  };
  for (const [field, lookup] of Object.entries(lookups)) {
    const referenceId = payload[field];
    if (referenceId === undefined || referenceId === null) continue;
    if (!isUuid(referenceId)) throw invalidTenantPayload(`Invalid ${field}`);

    const reference = await lookup(database, referenceId, locationId);
    if (!reference) throw invalidTenantPayload(`${field} is unavailable for this location`);
    if (reference.location_id !== locationId) {
      throw invalidTenantPayload(`${field} is unavailable for this location`);
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

  await validateReferencesAtLocation(database, collection, locationId, payload);

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
    await validateReferencesAtLocation(database, collection, locationId, payload);
  }

  return payload;
}
