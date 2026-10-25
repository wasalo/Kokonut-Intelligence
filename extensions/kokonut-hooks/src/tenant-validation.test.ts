import { describe, expect, it, vi } from 'vitest';
import {
  validateTenantReferences,
  validateTenantReferencesForRows,
} from './tenant-validation.js';

const locationId = '11111111-1111-4111-8111-111111111111';
const plotId = '22222222-2222-4222-8222-222222222222';

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
    const database = vi.fn(() => ({
      where: () => ({ first: vi.fn().mockResolvedValue({
        location_id: '33333333-3333-4333-8333-333333333333',
      }) }),
    }));

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: locationId,
      plot_id: plotId,
    })).rejects.toThrow('different location');
  });

  it('accepts references in the same location', async () => {
    const database = vi.fn(() => ({
      where: () => ({ first: vi.fn().mockResolvedValue({ location_id: locationId }) }),
    }));

    await expect(validateTenantReferences(database, 'farm_activity', {
      location_id: locationId,
      plot_id: plotId,
    })).resolves.toEqual({ location_id: locationId, plot_id: plotId });
  });

  it('rejects cross-location references on update when the payload omits location_id', async () => {
    const database = vi.fn(() => ({
      where: () => ({ first: vi.fn().mockResolvedValue({
        location_id: '33333333-3333-4333-8333-333333333333',
      }) }),
    }));

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
    const database = vi.fn(() => ({
      where: () => ({ first: vi.fn().mockResolvedValue({ location_id: locationId }) }),
    }));
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
