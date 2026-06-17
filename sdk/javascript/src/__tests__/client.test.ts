import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KokonutClient } from './client.js';

// Mock the @directus/sdk
vi.mock('@directus/sdk', () => {
  const mockRequest = vi.fn();
  const mockReadItems = vi.fn(() => ({}));
  const mockReadItem = vi.fn(() => ({}));
  const mockCreateItem = vi.fn(() => ({}));
  const mockCreateItems = vi.fn(() => ({}));
  const mockUpdateItem = vi.fn(() => ({}));
  const mockDeleteItem = vi.fn(() => ({}));
  const mockSetToken = vi.fn();
  const mockLogin = vi.fn(() => ({ access_token: 'test-token', refresh_token: 'test-refresh' }));
  const mockLogout = vi.fn();

  const mockDirectus = {
    request: mockRequest,
    readItems: mockReadItems,
    readItem: mockReadItem,
    createItem: mockCreateItem,
    createItems: mockCreateItems,
    updateItem: mockUpdateItem,
    deleteItem: mockDeleteItem,
    setToken: mockSetToken,
    login: mockLogin,
    logout: mockLogout,
  };

  return {
    createDirectus: vi.fn(() => mockDirectus),
    rest: vi.fn(() => ({})),
    authentication: vi.fn(() => ({})),
  };
});

describe('KokonutClient', () => {
  let client: KokonutClient;

  beforeEach(() => {
    vi.clearAllMocks();
    client = new KokonutClient('http://localhost:8055', { token: 'test-token' });
  });

  it('should instantiate with all method groups', () => {
    expect(client.locations).toBeDefined();
    expect(client.farms).toBeDefined();
    expect(client.plots).toBeDefined();
    expect(client.cropCycles).toBeDefined();
    expect(client.harvestEvents).toBeDefined();
    expect(client.salesEvents).toBeDefined();
    expect(client.expenseEvents).toBeDefined();
    expect(client.sensorReadings).toBeDefined();
    expect(client.walletProfiles).toBeDefined();
    expect(client.attestations).toBeDefined();
    expect(client.reports).toBeDefined();
    expect(client.exports).toBeDefined();
    expect(client.noi).toBeDefined();
  });

  it('should have list methods on all groups', () => {
    expect(typeof client.locations.list).toBe('function');
    expect(typeof client.farms.list).toBe('function');
    expect(typeof client.plots.list).toBe('function');
    expect(typeof client.cropCycles.list).toBe('function');
    expect(typeof client.harvestEvents.list).toBe('function');
    expect(typeof client.salesEvents.list).toBe('function');
    expect(typeof client.expenseEvents.list).toBe('function');
    expect(typeof client.sensorReadings.list).toBe('function');
    expect(typeof client.walletProfiles.list).toBe('function');
    expect(typeof client.attestations.list).toBe('function');
    expect(typeof client.reports.list).toBe('function');
    expect(typeof client.noi.list).toBe('function');
  });

  it('should have domain-specific methods', () => {
    expect(typeof client.farms.listByLocation).toBe('function');
    expect(typeof client.plots.listByFarm).toBe('function');
    expect(typeof client.cropCycles.listByPlot).toBe('function');
    expect(typeof client.cropCycles.listActive).toBe('function');
    expect(typeof client.harvestEvents.listByCropCycle).toBe('function');
    expect(typeof client.salesEvents.listByCropCycle).toBe('function');
    expect(typeof client.salesEvents.listUnpaid).toBe('function');
    expect(typeof client.expenseEvents.listByCropCycle).toBe('function');
    expect(typeof client.expenseEvents.listPendingApproval).toBe('function');
    expect(typeof client.sensorReadings.listByDevice).toBe('function');
    expect(typeof client.sensorReadings.listByPlot).toBe('function');
    expect(typeof client.sensorReadings.listAnomalies).toBe('function');
    expect(typeof client.walletProfiles.findByAddress).toBe('function');
    expect(typeof client.attestations.listPending).toBe('function');
    expect(typeof client.attestations.listByEntity).toBe('function');
    expect(typeof client.reports.listByType).toBe('function');
    expect(typeof client.noi.listByCropCycle).toBe('function');
  });
});
