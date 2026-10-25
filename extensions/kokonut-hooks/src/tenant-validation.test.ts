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
