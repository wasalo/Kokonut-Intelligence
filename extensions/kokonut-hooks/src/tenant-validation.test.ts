import { describe, expect, it, vi } from 'vitest';
import { validateTenantReferences } from './tenant-validation.js';

const locationId = '11111111-1111-4111-8111-111111111111';
const plotId = '22222222-2222-4222-8222-222222222222';

describe('tenant reference validation', () => {
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
});
