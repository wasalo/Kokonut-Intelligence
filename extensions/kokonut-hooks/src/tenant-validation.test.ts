import { describe, expect, it, vi } from 'vitest';
import {
  validateTenantReferences,
  validateTenantReferencesForRows,
} from './tenant-validation.js';

const locationId = '11111111-1111-4111-8111-111111111111';
const otherLocationId = '33333333-3333-4333-8333-333333333333';
const plotId = '22222222-2222-4222-8222-222222222222';
const farmId = '44444444-4444-4444-8444-444444444444';

function makeReferenceDatabase(referenceLocationId: string | null) {
  const joins: unknown[][] = [];
  const conditions: unknown[][] = [];
  const database = vi.fn((table: string) => {
    const builder: any = {
      join: vi.fn((...args: unknown[]) => {
        joins.push(args);
        return builder;
      }),
      where: vi.fn((...args: unknown[]) => {
        conditions.push(args);
        return builder;
      }),
      first: vi.fn().mockImplementation(async () => {
        const scopedLocation = conditions
          .map(([condition]) => (
            condition !== null && typeof condition === 'object'
              ? Object.entries(condition as Record<string, unknown>)
                .find(([field]) => field === 'location_id' || field.endsWith('.location_id'))?.[1]
              : undefined
          ))
          .find((value) => value !== undefined);
        if (referenceLocationId === null || (
          typeof scopedLocation === 'string' && scopedLocation !== referenceLocationId
        )) return undefined;
        return { location_id: referenceLocationId };
      }),
    };
    return builder;
  });
  return { database, joins, conditions };
}

function makeStaffReferenceDatabase(
  staffLocationId: string | null,
  membershipLocationId: string | null,
) {
  const queries: Array<{ table: string; conditions: unknown[]; joins: unknown[][] }> = [];
  const database = vi.fn((table: string) => {
    const query = { table, conditions: [] as unknown[], joins: [] as unknown[][] };
    queries.push(query);
    const builder: any = {
      join: vi.fn((...args: unknown[]) => {
        query.joins.push(args);
        return builder;
      }),
      where: vi.fn((...args: unknown[]) => {
        query.conditions.push(args[0]);
        return builder;
      }),
      first: vi.fn().mockImplementation(async () => {
        const conditions = Object.assign({}, ...query.conditions.filter(
          (condition): condition is Record<string, unknown> => (
            condition !== null && typeof condition === 'object' && !Array.isArray(condition)
          ),
        ));
        if (table === 'staff') {
          return conditions.location_id === staffLocationId ? { id: farmId } : undefined;
        }
        if (table === 'farm_staff_member as member_ref') {
          return conditions['farm_ref.location_id'] === membershipLocationId
            ? { staff_id: farmId }
            : undefined;
        }
        return undefined;
      }),
    };
    return builder;
  });
  return { database, queries };
}

describe('tenant reference validation', () => {
  it('rejects malformed scopes as a Directus 400 payload error', async () => {
    const database = vi.fn();

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: 'not-a-uuid',
    })).rejects.toMatchObject({
      code: 'INVALID_PAYLOAD',
      message: 'Invalid location_id',
      status: 400,
    });
    expect(database).not.toHaveBeenCalled();
  });

  it('rejects a reference belonging to another location', async () => {
    const { database, conditions } = makeReferenceDatabase(otherLocationId);

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: locationId,
      plot_id: plotId,
    })).rejects.toThrow('plot_id is unavailable for this location');
    expect(conditions).toEqual([[
      { 'plot_ref.id': plotId, 'farm_ref.location_id': locationId },
    ]]);
  });

  it('accepts references in the same location', async () => {
    const { database, joins, conditions } = makeReferenceDatabase(locationId);

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: locationId,
      plot_id: plotId,
    })).resolves.toEqual({ location_id: locationId, plot_id: plotId });
    expect(database).toHaveBeenCalledWith('plot as plot_ref');
    expect(joins).toEqual([['farm as farm_ref', 'plot_ref.farm_id', 'farm_ref.id']]);
    expect(conditions).toEqual([[
      { 'plot_ref.id': plotId, 'farm_ref.location_id': locationId },
    ]]);
  });

  it('validates the writable stakeholder farm reference through farm.location_id', async () => {
    const { database, conditions } = makeReferenceDatabase(locationId);
    const payload = { location_id: locationId, farm_id: farmId };

    await expect(validateTenantReferences(
      database,
      'stakeholder_feedback',
      payload,
    )).resolves.toBe(payload);
    expect(conditions).toEqual([[
      { id: farmId, location_id: locationId },
    ]]);

    await expect(validateTenantReferences(
      makeReferenceDatabase(otherLocationId).database,
      'stakeholder_feedback',
      payload,
    )).rejects.toThrow('farm_id is unavailable for this location');
  });

  it.each([
    { field: 'retirement_id', table: 'credit_retirement' },
    { field: 'credit_id', table: 'carbon_credit' },
    { field: 'credit_batch_id', table: 'credit_batch' },
  ])('validates retirement certificate $field against its location', async ({ field, table }) => {
    const reference = makeReferenceDatabase(locationId);
    const payload = { location_id: locationId, [field]: plotId };

    await expect(validateTenantReferences(
      reference.database,
      'retirement_certificate',
      payload,
    )).resolves.toBe(payload);
    expect(reference.database).toHaveBeenCalledWith(table);
    expect(reference.conditions).toEqual([[
      { id: plotId, location_id: locationId },
    ]]);

    await expect(validateTenantReferences(
      makeReferenceDatabase(otherLocationId).database,
      'retirement_certificate',
      payload,
    )).rejects.toThrow(`${field} is unavailable for this location`);
  });

  it('keeps retirement certificate-only references scoped and shared credit classes global', async () => {
    const database = vi.fn();
    const creditId = { credit_id: plotId };
    const creditClassId = { location_id: locationId, credit_class_id: plotId };

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: locationId,
      ...creditId,
    })).resolves.toEqual({ location_id: locationId, ...creditId });
    await expect(validateTenantReferences(database, 'retirement_certificate', creditClassId))
      .resolves.toBe(creditClassId);
    expect(database).not.toHaveBeenCalled();
  });

  it('validates retirement certificate references against each target row on update', async () => {
    const payload = { credit_batch_id: plotId };
    const sameLocation = makeReferenceDatabase(locationId);

    await expect(validateTenantReferencesForRows(
      sameLocation.database,
      'retirement_certificate',
      payload,
      [{ location_id: locationId }],
    )).resolves.toBe(payload);
    expect(sameLocation.database).toHaveBeenCalledWith('credit_batch');

    await expect(validateTenantReferencesForRows(
      makeReferenceDatabase(otherLocationId).database,
      'retirement_certificate',
      payload,
      [{ location_id: locationId }],
    )).rejects.toThrow('credit_batch_id is unavailable for this location');
  });

  it.each([
    { field: 'crop_cycle_id', table: 'crop_cycle' },
    { field: 'harvest_id', table: 'harvest_event' },
  ])('scopes $field lookup to the requested location', async ({ field, table }) => {
    const { database, conditions } = makeReferenceDatabase(locationId);
    const payload = { location_id: locationId, [field]: plotId };

    await expect(validateTenantReferences(database, 'farm_activity', payload))
      .resolves.toBe(payload);

    expect(database).toHaveBeenCalledWith(table);
    expect(conditions).toEqual([[
      { id: plotId, location_id: locationId },
    ]]);
  });

  it('accepts staff directly assigned to the same location', async () => {
    const { database } = makeStaffReferenceDatabase(locationId, null);
    const payload = { location_id: locationId, staff_id: farmId };

    await expect(validateTenantReferences(
      database,
      'labor_event',
      payload,
    )).resolves.toBe(payload);
  });

  it('accepts same-location farm membership and rejects unrelated staff', async () => {
    const { database, queries } = makeStaffReferenceDatabase(otherLocationId, locationId);
    const payload = { location_id: locationId, reviewed_by: farmId };

    await expect(validateTenantReferences(
      database,
      'metric_proposal',
      payload,
    )).resolves.toBe(payload);
    expect(queries[1].joins).toEqual([['farm as farm_ref', 'member_ref.farm_id', 'farm_ref.id']]);

    await expect(validateTenantReferences(
      makeStaffReferenceDatabase(otherLocationId, otherLocationId).database,
      'labor_event',
      { location_id: locationId, staff_id: farmId },
    )).rejects.toThrow('staff_id is unavailable for this location');
  });

  it('validates a feedback reviewer against the parent feedback location', async () => {
    const { database } = makeStaffReferenceDatabase(locationId, null);
    const payload = { location_id: locationId, reviewer_id: farmId };

    await expect(validateTenantReferences(
      database,
      'stakeholder_feedback',
      payload,
    )).resolves.toBe(payload);
  });

  it('validates scenario parents and infrastructure assets against the same location', async () => {
    const scenario = makeReferenceDatabase(locationId);
    const scenarioPayload = { location_id: locationId, parent_scenario_id: plotId };
    await expect(validateTenantReferences(
      scenario.database,
      'forecast_scenario',
      scenarioPayload,
    )).resolves.toBe(scenarioPayload);
    expect(scenario.database).toHaveBeenCalledWith('forecast_scenario');
    expect(scenario.conditions).toEqual([[
      { id: plotId, location_id: locationId },
    ]]);

    await expect(validateTenantReferences(
      makeReferenceDatabase(otherLocationId).database,
      'forecast_scenario',
      scenarioPayload,
    )).rejects.toThrow('parent_scenario_id is unavailable for this location');

    const asset = makeReferenceDatabase(locationId);
    const maintenancePayload = { location_id: locationId, infrastructure_asset_id: farmId };
    await expect(validateTenantReferences(
      asset.database,
      'maintenance_event',
      maintenancePayload,
    )).resolves.toBe(maintenancePayload);
    expect(asset.database).toHaveBeenCalledWith('infrastructure_asset');
    expect(asset.conditions).toEqual([[
      { id: farmId, location_id: locationId },
    ]]);

    await expect(validateTenantReferences(
      makeReferenceDatabase(otherLocationId).database,
      'maintenance_event',
      maintenancePayload,
    )).rejects.toThrow('infrastructure_asset_id is unavailable for this location');
  });

  it.each([
    {
      field: 'sensor_device_id',
      table: 'sensor_device',
      joins: [],
      where: { id: plotId, location_id: locationId },
    },
    {
      field: 'sensor_alert_id',
      table: 'sensor_alert as alert_ref',
      joins: [['sensor_device as device_ref', 'alert_ref.sensor_device_id', 'device_ref.id']],
      where: { 'alert_ref.id': plotId, 'device_ref.location_id': locationId },
    },
  ])('validates $field against the MRV claim location', async ({ field, table, joins, where }) => {
    const reference = makeReferenceDatabase(locationId);
    const payload = { location_id: locationId, [field]: plotId };

    await expect(validateTenantReferences(
      reference.database,
      'mrv_claim',
      payload,
    )).resolves.toBe(payload);
    expect(reference.database).toHaveBeenCalledWith(table);
    expect(reference.joins).toEqual(joins);
    expect(reference.conditions).toEqual([[where]]);

    await expect(validateTenantReferences(
      makeReferenceDatabase(otherLocationId).database,
      'mrv_claim',
      payload,
    )).rejects.toThrow(`${field} is unavailable for this location`);
  });

  it('rejects cross-location references on update when the payload omits location_id', async () => {
    const { database } = makeReferenceDatabase(otherLocationId);

    await expect(validateTenantReferencesForRows(
      database,
      'farm_activity',
      { plot_id: plotId },
      [{ location_id: locationId }],
    )).rejects.toMatchObject({
      code: 'INVALID_PAYLOAD',
      status: 400,
      message: 'plot_id is unavailable for this location',
    });
  });

  it('validates update references against every authorized row location', async () => {
    const { database } = makeReferenceDatabase(locationId);
    const payload = { crop_cycle_id: plotId };

    await expect(validateTenantReferencesForRows(
      database,
      'expense_event',
      payload,
      [{ location_id: locationId }],
    )).resolves.toBe(payload);

    await expect(validateTenantReferencesForRows(
      database,
      'expense_event',
      payload,
      [{ location_id: locationId }, { location_id: '33333333-3333-4333-8333-333333333333' }],
    )).rejects.toThrow('is unavailable for this location');
  });

  it('does not distinguish a missing reference from a foreign-location reference', async () => {
    const payload = { location_id: locationId, plot_id: plotId };
    const foreign = await validateTenantReferences(
      makeReferenceDatabase(otherLocationId).database,
      'farm_activity',
      payload,
    ).catch((error: Error) => error.message);
    const missing = await validateTenantReferences(
      makeReferenceDatabase(null).database,
      'farm_activity',
      payload,
    ).catch((error: Error) => error.message);

    expect(foreign).toBe('plot_id is unavailable for this location');
    expect(missing).toBe(foreign);
  });

  it('rejects malformed update references before querying them', async () => {
    const database = vi.fn();
    await expect(validateTenantReferencesForRows(
      database,
      'expense_event',
      { crop_cycle_id: 'malformed' },
      [{ location_id: locationId }],
    )).rejects.toMatchObject({
      code: 'INVALID_PAYLOAD',
      message: 'Invalid crop_cycle_id',
      status: 400,
    });
    expect(database).not.toHaveBeenCalled();
  });
});
