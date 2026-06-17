import type {
  Location,
  Farm,
  Plot,
  CropCycle,
  HarvestEvent,
  SalesEvent,
  ExpenseEvent,
  SensorReading,
  WalletProfile,
  AttestationRecord,
  ReportSnapshot,
  ExportLog,
  NoiSnapshot,
  ListOptions,
} from './types.js';

export interface GenericMethods {
  list(options?: ListOptions): Promise<any[]>;
  get(id: string, fields?: string[]): Promise<any>;
  create(data: Record<string, any>): Promise<any>;
  createMany(data: Record<string, any>[]): Promise<any[]>;
  update(id: string, data: Record<string, any>): Promise<any>;
  delete(id: string): Promise<void>;
}

function createGenericMethods(client: any, collection: string): GenericMethods {
  return {
    list: (options?: ListOptions) => client.listItems(collection, options),
    get: (id: string, fields?: string[]) => client.getItem(collection, id, fields),
    create: (data: Record<string, any>) => client.createItem(collection, data),
    createMany: (data: Record<string, any>[]) => client.createItems(collection, data),
    update: (id: string, data: Record<string, any>) => client.updateItem(collection, id, data),
    delete: (id: string) => client.deleteItem(collection, id),
  };
}

export interface LocationMethods extends GenericMethods {
  list(options?: ListOptions): Promise<Location[]>;
  get(id: string, fields?: string[]): Promise<Location>;
  create(data: Partial<Location>): Promise<Location>;
  createMany(data: Partial<Location>[]): Promise<Location[]>;
  update(id: string, data: Partial<Location>): Promise<Location>;
}

export interface FarmMethods extends GenericMethods {
  list(options?: ListOptions): Promise<Farm[]>;
  get(id: string, fields?: string[]): Promise<Farm>;
  create(data: Partial<Farm>): Promise<Farm>;
  createMany(data: Partial<Farm>[]): Promise<Farm[]>;
  update(id: string, data: Partial<Farm>): Promise<Farm>;
  listByLocation(locationId: string, options?: ListOptions): Promise<Farm[]>;
}

export interface PlotMethods extends GenericMethods {
  list(options?: ListOptions): Promise<Plot[]>;
  get(id: string, fields?: string[]): Promise<Plot>;
  create(data: Partial<Plot>): Promise<Plot>;
  createMany(data: Partial<Plot>[]): Promise<Plot[]>;
  update(id: string, data: Partial<Plot>): Promise<Plot>;
  listByFarm(farmId: string, options?: ListOptions): Promise<Plot[]>;
}

export interface CropCycleMethods extends GenericMethods {
  list(options?: ListOptions): Promise<CropCycle[]>;
  get(id: string, fields?: string[]): Promise<CropCycle>;
  create(data: Partial<CropCycle>): Promise<CropCycle>;
  createMany(data: Partial<CropCycle>[]): Promise<CropCycle[]>;
  update(id: string, data: Partial<CropCycle>): Promise<CropCycle>;
  listByPlot(plotId: string, options?: ListOptions): Promise<CropCycle[]>;
  listActive(options?: ListOptions): Promise<CropCycle[]>;
}

export interface HarvestEventMethods extends GenericMethods {
  list(options?: ListOptions): Promise<HarvestEvent[]>;
  get(id: string, fields?: string[]): Promise<HarvestEvent>;
  create(data: Partial<HarvestEvent>): Promise<HarvestEvent>;
  createMany(data: Partial<HarvestEvent>[]): Promise<HarvestEvent[]>;
  update(id: string, data: Partial<HarvestEvent>): Promise<HarvestEvent>;
  listByCropCycle(cropCycleId: string, options?: ListOptions): Promise<HarvestEvent[]>;
}

export interface SalesEventMethods extends GenericMethods {
  list(options?: ListOptions): Promise<SalesEvent[]>;
  get(id: string, fields?: string[]): Promise<SalesEvent>;
  create(data: Partial<SalesEvent>): Promise<SalesEvent>;
  createMany(data: Partial<SalesEvent>[]): Promise<SalesEvent[]>;
  update(id: string, data: Partial<SalesEvent>): Promise<SalesEvent>;
  listByCropCycle(cropCycleId: string, options?: ListOptions): Promise<SalesEvent[]>;
  listUnpaid(options?: ListOptions): Promise<SalesEvent[]>;
}

export interface ExpenseEventMethods extends GenericMethods {
  list(options?: ListOptions): Promise<ExpenseEvent[]>;
  get(id: string, fields?: string[]): Promise<ExpenseEvent>;
  create(data: Partial<ExpenseEvent>): Promise<ExpenseEvent>;
  createMany(data: Partial<ExpenseEvent>[]): Promise<ExpenseEvent[]>;
  update(id: string, data: Partial<ExpenseEvent>): Promise<ExpenseEvent>;
  listByCropCycle(cropCycleId: string, options?: ListOptions): Promise<ExpenseEvent[]>;
  listPendingApproval(options?: ListOptions): Promise<ExpenseEvent[]>;
}

export interface SensorReadingMethods extends GenericMethods {
  list(options?: ListOptions): Promise<SensorReading[]>;
  get(id: string, fields?: string[]): Promise<SensorReading>;
  create(data: Partial<SensorReading>): Promise<SensorReading>;
  createMany(data: Partial<SensorReading>[]): Promise<SensorReading[]>;
  update(id: string, data: Partial<SensorReading>): Promise<SensorReading>;
  listByDevice(deviceId: string, options?: ListOptions): Promise<SensorReading[]>;
  listByPlot(plotId: string, options?: ListOptions): Promise<SensorReading[]>;
  listAnomalies(options?: ListOptions): Promise<SensorReading[]>;
}

export interface WalletProfileMethods extends GenericMethods {
  list(options?: ListOptions): Promise<WalletProfile[]>;
  get(id: string, fields?: string[]): Promise<WalletProfile>;
  create(data: Partial<WalletProfile>): Promise<WalletProfile>;
  createMany(data: Partial<WalletProfile>[]): Promise<WalletProfile[]>;
  update(id: string, data: Partial<WalletProfile>): Promise<WalletProfile>;
  findByAddress(address: string): Promise<WalletProfile | null>;
}

export interface AttestationMethods extends GenericMethods {
  list(options?: ListOptions): Promise<AttestationRecord[]>;
  get(id: string, fields?: string[]): Promise<AttestationRecord>;
  create(data: Partial<AttestationRecord>): Promise<AttestationRecord>;
  createMany(data: Partial<AttestationRecord>[]): Promise<AttestationRecord[]>;
  update(id: string, data: Partial<AttestationRecord>): Promise<AttestationRecord>;
  listPending(options?: ListOptions): Promise<AttestationRecord[]>;
  listByEntity(entityType: string, entityId: string): Promise<AttestationRecord[]>;
}

export interface ReportMethods extends GenericMethods {
  list(options?: ListOptions): Promise<ReportSnapshot[]>;
  get(id: string, fields?: string[]): Promise<ReportSnapshot>;
  create(data: Partial<ReportSnapshot>): Promise<ReportSnapshot>;
  createMany(data: Partial<ReportSnapshot>[]): Promise<ReportSnapshot[]>;
  update(id: string, data: Partial<ReportSnapshot>): Promise<ReportSnapshot>;
  listByType(reportType: string, options?: ListOptions): Promise<ReportSnapshot[]>;
}

export interface ExportMethods {
  list(options?: ListOptions): Promise<ExportLog[]>;
  get(id: string): Promise<ExportLog>;
  create(params: {
    export_type: string;
    format: ExportLog['format'];
    entity_type?: string;
    entity_ids?: string[];
    filters?: Record<string, any>;
  }): Promise<ExportLog>;
}

export function buildLocationMethods(client: any): LocationMethods {
  const base = createGenericMethods(client, 'location');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('location', options) as Promise<Location[]>,
    get: (id: string, fields?: string[]) => client.getItem('location', id, fields) as Promise<Location>,
    create: (data: Partial<Location>) => client.createItem('location', data) as Promise<Location>,
    createMany: (data: Partial<Location>[]) => client.createItems('location', data) as Promise<Location[]>,
    update: (id: string, data: Partial<Location>) => client.updateItem('location', id, data) as Promise<Location>,
  };
}

export function buildFarmMethods(client: any): FarmMethods {
  const base = createGenericMethods(client, 'farm');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('farm', options) as Promise<Farm[]>,
    get: (id: string, fields?: string[]) => client.getItem('farm', id, fields) as Promise<Farm>,
    create: (data: Partial<Farm>) => client.createItem('farm', data) as Promise<Farm>,
    createMany: (data: Partial<Farm>[]) => client.createItems('farm', data) as Promise<Farm[]>,
    update: (id: string, data: Partial<Farm>) => client.updateItem('farm', id, data) as Promise<Farm>,
    listByLocation: (locationId: string, options?: ListOptions) =>
      client.listItems('farm', {
        ...options,
        filter: { ...options?.filter, location_id: locationId },
      }) as Promise<Farm[]>,
  };
}

export function buildPlotMethods(client: any): PlotMethods {
  const base = createGenericMethods(client, 'plot');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('plot', options) as Promise<Plot[]>,
    get: (id: string, fields?: string[]) => client.getItem('plot', id, fields) as Promise<Plot>,
    create: (data: Partial<Plot>) => client.createItem('plot', data) as Promise<Plot>,
    createMany: (data: Partial<Plot>[]) => client.createItems('plot', data) as Promise<Plot[]>,
    update: (id: string, data: Partial<Plot>) => client.updateItem('plot', id, data) as Promise<Plot>,
    listByFarm: (farmId: string, options?: ListOptions) =>
      client.listItems('plot', {
        ...options,
        filter: { ...options?.filter, farm_id: farmId },
      }) as Promise<Plot[]>,
  };
}

export function buildCropCycleMethods(client: any): CropCycleMethods {
  const base = createGenericMethods(client, 'crop_cycle');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('crop_cycle', options) as Promise<CropCycle[]>,
    get: (id: string, fields?: string[]) => client.getItem('crop_cycle', id, fields) as Promise<CropCycle>,
    create: (data: Partial<CropCycle>) => client.createItem('crop_cycle', data) as Promise<CropCycle>,
    createMany: (data: Partial<CropCycle>[]) => client.createItems('crop_cycle', data) as Promise<CropCycle[]>,
    update: (id: string, data: Partial<CropCycle>) => client.updateItem('crop_cycle', id, data) as Promise<CropCycle>,
    listByPlot: (plotId: string, options?: ListOptions) =>
      client.listItems('crop_cycle', {
        ...options,
        filter: { ...options?.filter, plot_id: plotId },
      }) as Promise<CropCycle[]>,
    listActive: (options?: ListOptions) =>
      client.listItems('crop_cycle', {
        ...options,
        filter: { ...options?.filter, status: { _in: ['planted', 'growing'] } },
      }) as Promise<CropCycle[]>,
  };
}

export function buildHarvestEventMethods(client: any): HarvestEventMethods {
  const base = createGenericMethods(client, 'harvest_event');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('harvest_event', options) as Promise<HarvestEvent[]>,
    get: (id: string, fields?: string[]) => client.getItem('harvest_event', id, fields) as Promise<HarvestEvent>,
    create: (data: Partial<HarvestEvent>) => client.createItem('harvest_event', data) as Promise<HarvestEvent>,
    createMany: (data: Partial<HarvestEvent>[]) => client.createItems('harvest_event', data) as Promise<HarvestEvent[]>,
    update: (id: string, data: Partial<HarvestEvent>) => client.updateItem('harvest_event', id, data) as Promise<HarvestEvent>,
    listByCropCycle: (cropCycleId: string, options?: ListOptions) =>
      client.listItems('harvest_event', {
        ...options,
        filter: { ...options?.filter, crop_cycle_id: cropCycleId },
      }) as Promise<HarvestEvent[]>,
  };
}

export function buildSalesEventMethods(client: any): SalesEventMethods {
  const base = createGenericMethods(client, 'sales_event');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('sales_event', options) as Promise<SalesEvent[]>,
    get: (id: string, fields?: string[]) => client.getItem('sales_event', id, fields) as Promise<SalesEvent>,
    create: (data: Partial<SalesEvent>) => client.createItem('sales_event', data) as Promise<SalesEvent>,
    createMany: (data: Partial<SalesEvent>[]) => client.createItems('sales_event', data) as Promise<SalesEvent[]>,
    update: (id: string, data: Partial<SalesEvent>) => client.updateItem('sales_event', id, data) as Promise<SalesEvent>,
    listByCropCycle: (cropCycleId: string, options?: ListOptions) =>
      client.listItems('sales_event', {
        ...options,
        filter: { ...options?.filter, crop_cycle_id: cropCycleId },
      }) as Promise<SalesEvent[]>,
    listUnpaid: (options?: ListOptions) =>
      client.listItems('sales_event', {
        ...options,
        filter: { ...options?.filter, payment_status: { _in: ['pending', 'partial'] } },
      }) as Promise<SalesEvent[]>,
  };
}

export function buildExpenseEventMethods(client: any): ExpenseEventMethods {
  const base = createGenericMethods(client, 'expense_event');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('expense_event', options) as Promise<ExpenseEvent[]>,
    get: (id: string, fields?: string[]) => client.getItem('expense_event', id, fields) as Promise<ExpenseEvent>,
    create: (data: Partial<ExpenseEvent>) => client.createItem('expense_event', data) as Promise<ExpenseEvent>,
    createMany: (data: Partial<ExpenseEvent>[]) => client.createItems('expense_event', data) as Promise<ExpenseEvent[]>,
    update: (id: string, data: Partial<ExpenseEvent>) => client.updateItem('expense_event', id, data) as Promise<ExpenseEvent>,
    listByCropCycle: (cropCycleId: string, options?: ListOptions) =>
      client.listItems('expense_event', {
        ...options,
        filter: { ...options?.filter, crop_cycle_id: cropCycleId },
      }) as Promise<ExpenseEvent[]>,
    listPendingApproval: (options?: ListOptions) =>
      client.listItems('expense_event', {
        ...options,
        filter: { ...options?.filter, status: { _eq: 'submitted' } },
      }) as Promise<ExpenseEvent[]>,
  };
}

export function buildSensorReadingMethods(client: any): SensorReadingMethods {
  const base = createGenericMethods(client, 'sensor_reading');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('sensor_reading', options) as Promise<SensorReading[]>,
    get: (id: string, fields?: string[]) => client.getItem('sensor_reading', id, fields) as Promise<SensorReading>,
    create: (data: Partial<SensorReading>) => client.createItem('sensor_reading', data) as Promise<SensorReading>,
    createMany: (data: Partial<SensorReading>[]) => client.createItems('sensor_reading', data) as Promise<SensorReading[]>,
    update: (id: string, data: Partial<SensorReading>) => client.updateItem('sensor_reading', id, data) as Promise<SensorReading>,
    listByDevice: (deviceId: string, options?: ListOptions) =>
      client.listItems('sensor_reading', {
        ...options,
        filter: { ...options?.filter, sensor_id: deviceId },
      }) as Promise<SensorReading[]>,
    listByPlot: (plotId: string, options?: ListOptions) =>
      client.listItems('sensor_reading', {
        ...options,
        filter: { ...options?.filter, plot_id: plotId },
      }) as Promise<SensorReading[]>,
    listAnomalies: (options?: ListOptions) =>
      client.listItems('sensor_reading', {
        ...options,
        filter: { ...options?.filter, anomaly_flag: true },
      }) as Promise<SensorReading[]>,
  };
}

export function buildWalletProfileMethods(client: any): WalletProfileMethods {
  const base = createGenericMethods(client, 'wallet_profile');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('wallet_profile', options) as Promise<WalletProfile[]>,
    get: (id: string, fields?: string[]) => client.getItem('wallet_profile', id, fields) as Promise<WalletProfile>,
    create: (data: Partial<WalletProfile>) => client.createItem('wallet_profile', data) as Promise<WalletProfile>,
    createMany: (data: Partial<WalletProfile>[]) => client.createItems('wallet_profile', data) as Promise<WalletProfile[]>,
    update: (id: string, data: Partial<WalletProfile>) => client.updateItem('wallet_profile', id, data) as Promise<WalletProfile>,
    findByAddress: async (address: string): Promise<WalletProfile | null> => {
      const results = await client.listItems('wallet_profile', {
        filter: { address: { _eq: address } },
        limit: 1,
      });
      return results.length > 0 ? results[0] : null;
    },
  };
}

export function buildAttestationMethods(client: any): AttestationMethods {
  const base = createGenericMethods(client, 'attestation_record');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('attestation_record', options) as Promise<AttestationRecord[]>,
    get: (id: string, fields?: string[]) => client.getItem('attestation_record', id, fields) as Promise<AttestationRecord>,
    create: (data: Partial<AttestationRecord>) => client.createItem('attestation_record', data) as Promise<AttestationRecord>,
    createMany: (data: Partial<AttestationRecord>[]) => client.createItems('attestation_record', data) as Promise<AttestationRecord[]>,
    update: (id: string, data: Partial<AttestationRecord>) => client.updateItem('attestation_record', id, data) as Promise<AttestationRecord>,
    listPending: (options?: ListOptions) =>
      client.listItems('attestation_record', {
        ...options,
        filter: { ...options?.filter, status: { _in: ['draft', 'submitted'] } },
      }) as Promise<AttestationRecord[]>,
    listByEntity: (entityType: string, entityId: string) =>
      client.listItems('attestation_record', {
        filter: { entity_type: entityType, entity_id: entityId },
      }) as Promise<AttestationRecord[]>,
  };
}

export function buildReportMethods(client: any): ReportMethods {
  const base = createGenericMethods(client, 'report_snapshot');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('report_snapshot', options) as Promise<ReportSnapshot[]>,
    get: (id: string, fields?: string[]) => client.getItem('report_snapshot', id, fields) as Promise<ReportSnapshot>,
    create: (data: Partial<ReportSnapshot>) => client.createItem('report_snapshot', data) as Promise<ReportSnapshot>,
    createMany: (data: Partial<ReportSnapshot>[]) => client.createItems('report_snapshot', data) as Promise<ReportSnapshot[]>,
    update: (id: string, data: Partial<ReportSnapshot>) => client.updateItem('report_snapshot', id, data) as Promise<ReportSnapshot>,
    listByType: (reportType: string, options?: ListOptions) =>
      client.listItems('report_snapshot', {
        ...options,
        filter: { ...options?.filter, report_type: reportType },
      }) as Promise<ReportSnapshot[]>,
  };
}

export function buildExportMethods(client: any): ExportMethods {
  return {
    list: (options?: ListOptions) => client.listItems('export_log', options) as Promise<ExportLog[]>,
    get: (id: string) => client.getItem('export_log', id) as Promise<ExportLog>,
    create: async (params: {
      export_type: string;
      format: ExportLog['format'];
      entity_type?: string;
      entity_ids?: string[];
      filters?: Record<string, any>;
    }) => {
      return client.createItem('export_log', {
        ...params,
        status: 'pending',
        requested_by: 'sdk',
      }) as Promise<ExportLog>;
    },
  };
}

export interface NoiMethods extends GenericMethods {
  list(options?: ListOptions): Promise<NoiSnapshot[]>;
  get(id: string, fields?: string[]): Promise<NoiSnapshot>;
  create(data: Partial<NoiSnapshot>): Promise<NoiSnapshot>;
  createMany(data: Partial<NoiSnapshot>[]): Promise<NoiSnapshot[]>;
  update(id: string, data: Partial<NoiSnapshot>): Promise<NoiSnapshot>;
  listByCropCycle(cropCycleId: string, options?: ListOptions): Promise<NoiSnapshot[]>;
}

export function buildNoiMethods(client: any): NoiMethods {
  const base = createGenericMethods(client, 'noi_snapshot');
  return {
    ...base,
    list: (options?: ListOptions) => client.listItems('noi_snapshot', options) as Promise<NoiSnapshot[]>,
    get: (id: string, fields?: string[]) => client.getItem('noi_snapshot', id, fields) as Promise<NoiSnapshot>,
    create: (data: Partial<NoiSnapshot>) => client.createItem('noi_snapshot', data) as Promise<NoiSnapshot>,
    createMany: (data: Partial<NoiSnapshot>[]) => client.createItems('noi_snapshot', data) as Promise<NoiSnapshot[]>,
    update: (id: string, data: Partial<NoiSnapshot>) => client.updateItem('noi_snapshot', id, data) as Promise<NoiSnapshot>,
    listByCropCycle: (cropCycleId: string, options?: ListOptions) =>
      client.listItems('noi_snapshot', {
        ...options,
        filter: { ...options?.filter, crop_cycle_id: cropCycleId },
      }) as Promise<NoiSnapshot[]>,
  };
}
