import { describe, expect, it, vi } from 'vitest';
import {
  validateTenantReferences,
  validateTenantReferencesForRows,
} from './tenant-validation.js';

const locationId = '11111111-1111-4111-8111-111111111111';
const otherLocationId = '33333333-3333-4333-8333-333333333333';
const plotId = '22222222-2222-4222-8222-222222222222';
const farmId = '44444444-4444-4444-8444-444444444444';

function makeReferenceDatabase(referenceLocationId: string) {
  const joins: unknown[][] = [];
  const database = vi.fn((table: string) => {
    const builder: any = {
      join: vi.fn((...args: unknown[]) => {
        joins.push(args);
        return builder;
      }),
      where: vi.fn(() => builder),
      first: vi.fn().mockResolvedValue({ location_id: referenceLocationId }),
    };
    return builder;
  });
  return { database, joins };
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
    const { database } = makeReferenceDatabase(otherLocationId);

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: locationId,
      plot_id: plotId,
    })).rejects.toThrow('different location');
  });

  it('accepts references in the same location', async () => {
    const { database, joins } = makeReferenceDatabase(locationId);

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: locationId,
      plot_id: plotId,
    })).resolves.toEqual({ location_id: locationId, plot_id: plotId });
    expect(database).toHaveBeenCalledWith('plot as plot_ref');
    expect(joins).toEqual([['farm as farm_ref', 'plot_ref.farm_id', 'farm_ref.id']]);
  });

  it('validates the writable stakeholder farm reference through farm.location_id', async () => {
    const { database } = makeReferenceDatabase(locationId);
    const payload = { location_id: locationId, farm_id: farmId };

    await expect(validateTenantReferences(
      database,
      'stakeholder_feedback',
      payload,
    )).resolves.toBe(payload);

    await expect(validateTenantReferences(
      makeReferenceDatabase(otherLocationId).database,
      'stakeholder_feedback',
      payload,
    )).rejects.toThrow('different location');
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
    )).rejects.toThrow('Unknown staff_id');
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
      message: 'plot_id belongs to a different location',
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
    )).rejects.toThrow('different location');
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
