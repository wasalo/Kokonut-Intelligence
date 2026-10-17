import { createError } from '@directus/errors';
import { TENANT_SCOPED_COLLECTIONS } from './directus-authorization.js';

const REFERENCE_TABLES: Record<string, string[]> = {
  plot_id: ['plot'],
  crop_cycle_id: ['crop_cycle'],
  harvest_id: ['harvest_event'],
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

  for (const [field, tables] of Object.entries(REFERENCE_TABLES)) {
    const referenceId = payload[field];
    if (referenceId === undefined || referenceId === null) continue;
    if (!isUuid(referenceId)) throw invalidTenantPayload(`Invalid ${field}`);

    let reference: any;
    for (const table of tables) {
      reference = await database(table).where('id', referenceId).first('location_id');
      if (reference) break;
    }
    if (!reference) throw invalidTenantPayload(`Unknown ${field}`);
    if (reference.location_id !== locationId) {
      throw invalidTenantPayload(`${field} belongs to a different location`);
    }
  }

  return payload;
}
