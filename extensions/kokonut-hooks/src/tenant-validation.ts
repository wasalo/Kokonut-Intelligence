const REFERENCE_TABLES: Record<string, string[]> = {
  plot_id: ['plot'],
  crop_cycle_id: ['crop_cycle'],
  harvest_id: ['harvest_event'],
};

const TENANT_SCOPED_COLLECTIONS = [
  'farm_activity',
  'harvest_event',
  'expense_event',
  'sales_event',
  'loss_event',
  'labor_event',
  'field_note',
  'stakeholder_feedback',
  'metric_proposal',
  'mrv_claim',
];

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
  if (!TENANT_SCOPED_COLLECTIONS.includes(collection)) return payload;

  const locationId = payload.location_id;
  if (!isUuid(locationId)) return payload;

  for (const [field, tables] of Object.entries(REFERENCE_TABLES)) {
    const referenceId = payload[field];
    if (referenceId === undefined || referenceId === null) continue;
    if (!isUuid(referenceId)) throw new Error(`Invalid ${field}`);

    let reference: any;
    for (const table of tables) {
      reference = await database(table).where('id', referenceId).first('location_id');
      if (reference) break;
    }
    if (!reference) throw new Error(`Unknown ${field}`);
    if (reference.location_id !== locationId) {
      throw new Error(`${field} belongs to a different location`);
    }
  }

  return payload;
}
