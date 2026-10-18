import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KokonutClient } from '../client.js';
import type {
  CropCycle,
  ExpenseEvent,
  ExportLog,
  FieldNote,
  Farm,
  HarvestEvent,
  LaborEvent,
  Location,
  LossEvent,
  NoiSnapshot,
  Plot,
  SalesEvent,
  AlertRule,
  AttestationRecord,
  SensorAlert,
  SensorDevice,
  SensorReading,
  SensorType,
  ReportSnapshot,
  WalletProfile,
} from '../types.js';

// Mock the @directus/sdk
vi.mock('@directus/sdk', () => {
  const mockRequest = vi.fn();
  const mockReadItems = vi.fn((collection: string, query: Record<string, any>) => ({ collection, query }));
  const mockReadItem = vi.fn(() => ({}));
  const mockCreateItem = vi.fn(() => ({}));
  const mockCreateItems = vi.fn(() => ({}));
  const mockUpdateItem = vi.fn(() => ({}));
  const mockDeleteItem = vi.fn(() => ({}));
  const mockSetToken = vi.fn(() => Promise.resolve());
  const mockLogin = vi.fn(() => ({ access_token: 'test-token', refresh_token: 'test-refresh' }));
  const mockLogout = vi.fn();

  const mockDirectus = {
    with: vi.fn(() => mockDirectus),
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
    readItems: mockReadItems,
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
    expect(client.lossEvents).toBeDefined();
    expect(client.laborEvents).toBeDefined();
    expect(client.fieldNotes).toBeDefined();
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
    expect(typeof client.lossEvents.list).toBe('function');
    expect(typeof client.laborEvents.list).toBe('function');
    expect(typeof client.fieldNotes.list).toBe('function');
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
    expect(typeof client.exports.createExport).toBe('function');
    expect(typeof client.lossEvents.listByLocation).toBe('function');
    expect(typeof client.laborEvents.listByLocation).toBe('function');
    expect(typeof client.fieldNotes.listByLocation).toBe('function');
  });

  it('clears local authentication state when the remote logout request fails', async () => {
    const directus = (client as any).directus as {
      logout: () => Promise<void>;
      setToken: (token: string | null) => Promise<void>;
    };
    vi.spyOn(directus, 'logout').mockRejectedValue(new TypeError('network unavailable'));
    const setToken = vi.spyOn(directus, 'setToken');

    await expect(client.logout()).resolves.toBeUndefined();

    expect(setToken).toHaveBeenLastCalledWith(null);
  });

  it('provides typed, location-scoped methods for loss, labor and field-note records', async () => {
    const loss: LossEvent = {
      id: 'loss-1',
      location_id: 'location-1',
      loss_date: '2026-10-17',
      loss_type: 'weather',
      evidence_hashes: ['sha256:loss'],
    };
    const labor: LaborEvent = {
      id: 'labor-1',
      location_id: 'location-1',
      work_date: '2026-10-17',
      hours_worked: 6,
      total_cost: 48,
    };
    const note: FieldNote = {
      id: 'note-1',
      location_id: 'location-1',
      note_date: '2026-10-17',
      content: 'Synthetic fixture',
      tags: ['test'],
    };
    const listItems = vi.spyOn(client, 'listItems').mockResolvedValue([]);

    await client.lossEvents.listByLocation('location-1', {
      limit: 10,
      filter: { location_id: { _eq: 'other-location' }, status: { _eq: 'verified' } },
    });
    expect(listItems).toHaveBeenLastCalledWith('loss_event', {
      limit: 10,
      filter: { location_id: { _eq: 'location-1' }, status: { _eq: 'verified' } },
    });
    await client.laborEvents.listByLocation('location-1');
    expect(listItems).toHaveBeenLastCalledWith('labor_event', {
      filter: { location_id: { _eq: 'location-1' } },
    });
    await client.fieldNotes.listByLocation('location-1');
    expect(listItems).toHaveBeenLastCalledWith('field_note', {
      filter: { location_id: { _eq: 'location-1' } },
    });
    expect(loss.evidence_hashes).toEqual(['sha256:loss']);
    expect(labor.total_cost).toBe(48);
    expect(note.tags).toEqual(['test']);
  });

  it('preserves exact non-page-aligned offsets for Directus', async () => {
    await client.listItems('farm', { limit: 25, offset: 10 });

    const request = (client as any).directus.request;
    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0][0]).toEqual({
      collection: 'farm',
      query: { limit: 25, offset: 10 },
    });
  });

  it('types crop-cycle yield fields and location scope to the canonical schema', () => {
    const cycle: CropCycle = {
      id: 'cycle-1',
      plot_id: 'plot-1',
      crop_id: 'crop-1',
      location_id: 'location-1',
      expected_yield: 250,
      expected_yield_unit: 'kg',
      actual_yield: 215,
      actual_yield_unit: 'kg',
    };

    expect(cycle.actual_yield).toBe(215);
    expect(cycle.location_id).toBe('location-1');
  });

  it('types location, farm and plot spatial/audit fields from the canonical schema', () => {
    const location: Location = {
      id: 'location-1',
      name: 'Test Location',
      slug: 'test-location',
      country: 'DO',
      center: { type: 'Point', coordinates: [-69.9, 18.5] },
      metadata: { source: 'fixture' },
      created_by: 'operator-1',
    };
    const farm: Farm = {
      id: 'farm-1',
      location_id: location.id,
      name: 'Test Farm',
      slug: 'test-farm',
      boundary: { type: 'Polygon', coordinates: [] },
      metadata: { source: 'fixture' },
      updated_by: 'operator-1',
    };
    const plot: Plot = {
      id: 'plot-1',
      farm_id: farm.id,
      name: 'North Plot',
      slug: 'north-plot',
      center: { type: 'Point', coordinates: [-69.9, 18.5] },
      elevation_m: 42,
      metadata: { source: 'fixture' },
    };

    expect(location.center?.type).toBe('Point');
    expect(farm.boundary?.type).toBe('Polygon');
    expect(plot.elevation_m).toBe(42);
  });

  it('requires sensor reading location scope and accepts canonical quality values', () => {
    const reading: SensorReading = {
      id: 'reading-1',
      sensor_id: 'sensor-1',
      location_id: 'location-1',
      reading_date: '2026-10-17',
      value: 8.5,
      unit: 'percent',
      quality: 'bad',
      metadata: { source: 'synthetic-fixture' },
    };

    expect(reading.location_id).toBe('location-1');
    expect(reading.quality).toBe('bad');
  });

  it('types sensor registry and alert records with canonical nullable fields', () => {
    const type: SensorType = { id: 'type-1', name: 'soil_moisture', unit: '%' };
    const device: SensorDevice = {
      id: 'device-1',
      name: 'North Probe',
      slug: 'north-probe',
      sensor_type_id: type.id,
      location_id: 'location-1',
      status: null,
      calibration_interval_days: null,
    };
    const rule: AlertRule = {
      id: 'rule-1',
      name: 'Dry soil',
      sensor_type_id: type.id,
      metric: 'value',
      operator: 'lt',
      threshold_value: 20,
      threshold_value_max: null,
      enabled: null,
    };
    const alert: SensorAlert = {
      id: 'alert-1',
      sensor_device_id: device.id,
      alert_rule_id: rule.id,
      severity: 'warning',
      message: 'Soil moisture below threshold',
      triggered_at: '2026-10-17T12:00:00Z',
      status: null,
      reading_id: null,
    };

    expect(device.location_id).toBe('location-1');
    expect(rule.threshold_value).toBe(20);
    expect(alert.triggered_at).toBe('2026-10-17T12:00:00Z');
  });

  it('types wallet profile metadata and schema-defined role values', () => {
    const wallet: WalletProfile = {
      id: 'wallet-1',
      address: '0x0000000000000000000000000000000000000001',
      chain: 'gnosis',
      chain_id: 100,
      role: 'operations',
      label: 'Kokonut Operations',
      first_seen_date: '2026-10-17',
      last_active_date: '2026-10-18',
      metadata: { source: 'fixture' },
    };

    expect(wallet.role).toBe('operations');
    expect(wallet.chain_id).toBe(100);
    expect(wallet.metadata).toEqual({ source: 'fixture' });
  });

  it('types ExportLog columns from the canonical export table', () => {
    const exportLog: ExportLog = {
      id: 'export-1',
      export_type: 'farm_data',
      user_id: 'user-1',
      target_table: 'harvest_event',
      filters: { status: 'published' },
      row_count: 42,
      file_size_bytes: 2048,
      file_url: 'private://exports/export-1.csv',
      status: 'generating',
    };

    expect(exportLog.user_id).toBe('user-1');
    expect(exportLog.row_count).toBe(42);
    expect(exportLog.status).toBe('generating');
  });

  it('types nullable NOI snapshot fields from the canonical finance table', () => {
    const snapshot: NoiSnapshot = {
      id: 'snapshot-1',
      crop_cycle_id: 'cycle-1',
      location_id: 'location-1',
      period_start: '2026-01-01',
      period_end: '2026-03-31',
      gross_revenue: 1200,
      returns_and_discounts: null,
      noi: 430,
      inputs: { sales_event_ids: ['sale-1'] },
    };

    expect(snapshot.returns_and_discounts).toBeNull();
    expect(snapshot.inputs).toEqual({ sales_event_ids: ['sale-1'] });
  });

  it('types attestation evidence and additive schema fields', () => {
    const attestation: AttestationRecord = {
      id: 'attestation-1',
      schema_id: 'schema-1',
      claim_data: { outcome: 'verified' },
      evidence_cids: ['bafy-test'],
      evidence_urls: ['private://evidence/1'],
      schema_version: '1.0',
      private_payload_hash: 'sha256:private',
      verdict: 'accepted',
      evidence_reviewed: ['photo-1'],
      evaluator_id: 'reviewer-1',
    };

    expect(attestation.schema_id).toBe('schema-1');
    expect(attestation.evidence_cids).toEqual(['bafy-test']);
  });

  it('types report location, creator and frozen public-interest fields', () => {
    const report: ReportSnapshot = {
      id: 'report-1',
      report_name: 'Quarterly farm report',
      report_data: { summary: 'fixture' },
      location_id: 'location-1',
      created_by: 'operator-1',
      frozen: true,
      public_interest_summary: 'Public summary',
      negative_findings: [{ finding: 'finding-1' }],
      expires_at: '2027-10-17T00:00:00Z',
    };

    expect(report.report_name).toBe('Quarterly farm report');
    expect(report.frozen).toBe(true);
    expect(report.negative_findings).toEqual([{ finding: 'finding-1' }]);
  });

  it('types harvest evidence and source lineage from the canonical schema', () => {
    const event: HarvestEvent = {
      id: 'harvest-1',
      crop_cycle_id: 'cycle-1',
      plot_id: 'plot-1',
      location_id: 'location-1',
      harvest_date: '2026-10-17',
      quantity: 120,
      unit: 'kg',
      evidence_urls: ['private://harvest/photo-1'],
      evidence_hashes: ['sha256:abc123'],
      schema_version: '1.0',
      source_system: 'field_collector',
      source_id: 'device-note-1',
      source_raw: { form_version: '1.2.0' },
      created_by: 'operator-1',
      updated_by: 'operator-1',
    };

    expect(event.evidence_hashes).toEqual(['sha256:abc123']);
    expect(event.source_raw).toEqual({ form_version: '1.2.0' });
  });

  it('types sales evidence, payment and source lineage from the canonical schema', () => {
    const event: SalesEvent = {
      id: 'sale-1',
      location_id: 'location-1',
      sale_date: '2026-10-17',
      quantity: 80,
      unit: 'kg',
      total_amount: 160,
      payment_date: '2026-10-18',
      payment_method: 'bank_transfer',
      evidence_urls: ['private://sales/invoice-1'],
      evidence_hashes: ['sha256:def456'],
      source_raw: { batch_id: 'import-1' },
      updated_at: '2026-10-18T12:00:00Z',
    };

    expect(event.payment_method).toBe('bank_transfer');
    expect(event.evidence_hashes).toEqual(['sha256:def456']);
  });

  it('types expense approval, allocation and source lineage from the canonical schema', () => {
    const event: ExpenseEvent = {
      id: 'expense-1',
      location_id: 'location-1',
      expense_date: '2026-10-17',
      category: 'labor',
      amount: 75,
      vendor_id: 'partner-1',
      allocation_weight: 0.5,
      evidence_urls: ['private://expenses/receipt-1'],
      receipt_hash: 'sha256:ghi789',
      approved_by: 'reviewer-1',
      approved_at: '2026-10-18T12:00:00Z',
      rejection_reason: null,
      schema_version: '1.0',
      source_raw: { batch_id: 'import-2' },
    };

    expect(event.allocation_weight).toBe(0.5);
    expect(event.approved_by).toBe('reviewer-1');
  });

  it('preserves Python SDK export inputs through createExport()', async () => {
    const createItem = vi.spyOn(client, 'createItem').mockResolvedValue({ id: 'export-1' });
    const request = {
      export_type: 'farm_data',
      target_table: 'harvest_event',
      entity_type: 'location',
      entity_ids: ['location-1'],
      filters: { status: 'published' },
    };

    await client.exports.createExport(request);

    expect(createItem).toHaveBeenNthCalledWith(1, 'export_log', {
      ...request,
      format: null,
      status: 'pending',
      requested_by: 'sdk',
    });
  });

  it('supports Python-style export type plus optional request fields', async () => {
    const createItem = vi.spyOn(client, 'createItem').mockResolvedValue({ id: 'export-2' });

    await client.exports.createExport('farm_data', {
      entity_type: 'location',
      entity_ids: ['location-1'],
      target_table: 'harvest_event',
      filters: { status: 'published' },
    });

    expect(createItem).toHaveBeenCalledWith('export_log', {
      export_type: 'farm_data',
      format: null,
      entity_type: 'location',
      entity_ids: ['location-1'],
      target_table: 'harvest_event',
      filters: { status: 'published' },
      status: 'pending',
      requested_by: 'sdk',
    });
  });

  it('supports the Python export positional parameter contract', async () => {
    const createItem = vi.spyOn(client, 'createItem').mockResolvedValue({ id: 'export-3' });

    await client.exports.createExport(
      'farm_data',
      'csv',
      'location',
      ['location-1'],
      'harvest_event',
      { status: 'published' },
    );

    expect(createItem).toHaveBeenCalledWith('export_log', {
      export_type: 'farm_data',
      format: 'csv',
      entity_type: 'location',
      entity_ids: ['location-1'],
      target_table: 'harvest_event',
      filters: { status: 'published' },
      status: 'pending',
      requested_by: 'sdk',
    });
  });

  it('forwards export field projections like the Python SDK', async () => {
    const getItem = vi.spyOn(client, 'getItem').mockResolvedValue({
      id: 'export-1',
      status: 'completed',
    });

    const result = await client.exports.get('export-1', ['id', 'status']);

    expect(result).toEqual({ id: 'export-1', status: 'completed' });
    expect(getItem).toHaveBeenCalledWith('export_log', 'export-1', ['id', 'status']);
  });

  it('keeps the existing create() payload behavior', async () => {
    const createItem = vi.spyOn(client, 'createItem').mockResolvedValue({ id: 'export-2' });

    await client.exports.create({ export_type: 'farm_data', format: 'csv' });

    expect(createItem).toHaveBeenCalledWith('export_log', {
      export_type: 'farm_data',
      format: 'csv',
      status: 'pending',
      requested_by: 'sdk',
    });
  });

  it('supports export createMany with the same raw batch semantics as Python', async () => {
    const createItems = vi.spyOn(client, 'createItems').mockResolvedValue([
      { id: 'export-1' },
      { id: 'export-2' },
    ]);
    const requests = [
      { export_type: 'farm_data', status: 'pending' },
      { export_type: 'metric_data', status: 'pending' },
    ];

    const result = await client.exports.createMany(requests);

    expect(result).toEqual([{ id: 'export-1' }, { id: 'export-2' }]);
    expect(createItems).toHaveBeenCalledWith('export_log', requests);
  });

  it('keeps required convenience filters authoritative and forwards list options', async () => {
    const listItems = vi.spyOn(client, 'listItems').mockResolvedValue([]);

    await client.farms.listByLocation('location-1', {
      filter: { location_id: { _eq: 'location-2' }, status: { _eq: 'active' } },
      sort: ['name'],
      fields: ['id'],
      limit: 25,
      offset: 50,
      page: 3,
      meta: 'total_count',
    });

    expect(listItems).toHaveBeenCalledWith('farm', {
      filter: { location_id: { _eq: 'location-1' }, status: { _eq: 'active' } },
      sort: ['name'],
      fields: ['id'],
      limit: 25,
      offset: 50,
      page: 3,
      meta: 'total_count',
    });
  });

  it('uses the same explicit Directus equality filters as the Python SDK', async () => {
    const listItems = vi.spyOn(client, 'listItems').mockResolvedValue([]);
    const keep = { status: { _eq: 'verified' } };
    const cases: Array<{
      collection: string;
      run: () => Promise<unknown>;
      filter: Record<string, unknown>;
    }> = [
      {
        collection: 'farm',
        run: () => client.farms.listByLocation('location-1', { filter: { ...keep, location_id: { _eq: 'other' } } }),
        filter: { ...keep, location_id: { _eq: 'location-1' } },
      },
      {
        collection: 'plot',
        run: () => client.plots.listByFarm('farm-1', { filter: { ...keep, farm_id: { _eq: 'other' } } }),
        filter: { ...keep, farm_id: { _eq: 'farm-1' } },
      },
      {
        collection: 'crop_cycle',
        run: () => client.cropCycles.listByPlot('plot-1', { filter: { ...keep, plot_id: { _eq: 'other' } } }),
        filter: { ...keep, plot_id: { _eq: 'plot-1' } },
      },
      {
        collection: 'crop_cycle',
        run: () => client.cropCycles.listActive({ filter: { ...keep, status: { _eq: 'archived' } } }),
        filter: { ...keep, status: { _in: ['planted', 'growing'] } },
      },
      {
        collection: 'harvest_event',
        run: () => client.harvestEvents.listByCropCycle('cycle-1', { filter: { ...keep, crop_cycle_id: { _eq: 'other' } } }),
        filter: { ...keep, crop_cycle_id: { _eq: 'cycle-1' } },
      },
      {
        collection: 'sales_event',
        run: () => client.salesEvents.listByCropCycle('cycle-1', { filter: { ...keep, crop_cycle_id: { _eq: 'other' } } }),
        filter: { ...keep, crop_cycle_id: { _eq: 'cycle-1' } },
      },
      {
        collection: 'sales_event',
        run: () => client.salesEvents.listUnpaid({ filter: { ...keep, payment_status: { _eq: 'paid' } } }),
        filter: { ...keep, payment_status: { _in: ['pending', 'partial'] } },
      },
      {
        collection: 'expense_event',
        run: () => client.expenseEvents.listByCropCycle('cycle-1', { filter: { ...keep, crop_cycle_id: { _eq: 'other' } } }),
        filter: { ...keep, crop_cycle_id: { _eq: 'cycle-1' } },
      },
      {
        collection: 'expense_event',
        run: () => client.expenseEvents.listPendingApproval({ filter: { ...keep, status: { _eq: 'draft' } } }),
        filter: { ...keep, status: { _eq: 'submitted' } },
      },
      {
        collection: 'loss_event',
        run: () => client.lossEvents.listByLocation('location-1', { filter: { ...keep, location_id: { _eq: 'other' } } }),
        filter: { ...keep, location_id: { _eq: 'location-1' } },
      },
      {
        collection: 'labor_event',
        run: () => client.laborEvents.listByLocation('location-1', { filter: { ...keep, location_id: { _eq: 'other' } } }),
        filter: { ...keep, location_id: { _eq: 'location-1' } },
      },
      {
        collection: 'field_note',
        run: () => client.fieldNotes.listByLocation('location-1', { filter: { ...keep, location_id: { _eq: 'other' } } }),
        filter: { ...keep, location_id: { _eq: 'location-1' } },
      },
      {
        collection: 'sensor_reading',
        run: () => client.sensorReadings.listByDevice('device-1', { filter: { ...keep, sensor_id: { _eq: 'other' } } }),
        filter: { ...keep, sensor_id: { _eq: 'device-1' } },
      },
      {
        collection: 'sensor_reading',
        run: () => client.sensorReadings.listByPlot('plot-1', { filter: { ...keep, plot_id: { _eq: 'other' } } }),
        filter: { ...keep, plot_id: { _eq: 'plot-1' } },
      },
      {
        collection: 'sensor_reading',
        run: () => client.sensorReadings.listAnomalies({ filter: { ...keep, quality: { _eq: 'good' } } }),
        filter: { ...keep, quality: { _eq: 'suspect' } },
      },
      {
        collection: 'attestation_record',
        run: () => client.attestations.listPending({ filter: { ...keep, status: { _eq: 'published' } } }),
        filter: { ...keep, status: { _in: ['draft', 'submitted'] } },
      },
      {
        collection: 'report_snapshot',
        run: () => client.reports.listByType('impact', { filter: { ...keep, report_type: { _eq: 'other' } } }),
        filter: { ...keep, report_type: { _eq: 'impact' } },
      },
      {
        collection: 'noi_snapshot',
        run: () => client.noi.listByCropCycle('cycle-1', { filter: { ...keep, crop_cycle_id: { _eq: 'other' } } }),
        filter: { ...keep, crop_cycle_id: { _eq: 'cycle-1' } },
      },
      {
        collection: 'attestation_record',
        run: () => client.attestations.listByEntity('location', 'location-1'),
        filter: { subject_type: { _eq: 'location' }, subject_id: { _eq: 'location-1' } },
      },
    ];

    for (const scenario of cases) {
      await scenario.run();
      expect(listItems).toHaveBeenLastCalledWith(scenario.collection, { filter: scenario.filter });
    }

    await client.walletProfiles.findByAddress('0xwallet');
    expect(listItems).toHaveBeenLastCalledWith('wallet_profile', {
      filter: { address: { _eq: '0xwallet' } },
      limit: 1,
    });
  });
});
