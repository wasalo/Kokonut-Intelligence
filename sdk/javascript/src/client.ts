import { createDirectus, rest, authentication } from '@directus/sdk';
import type {
  ListOptions,
} from './types.js';
import {
  buildLocationMethods,
  buildFarmMethods,
  buildPlotMethods,
  buildCropCycleMethods,
  buildHarvestEventMethods,
  buildSalesEventMethods,
  buildExpenseEventMethods,
  buildSensorReadingMethods,
  buildWalletProfileMethods,
  buildAttestationMethods,
  buildReportMethods,
  buildExportMethods,
  buildNoiMethods,
} from './methods.js';
import type {
  LocationMethods,
  FarmMethods,
  PlotMethods,
  CropCycleMethods,
  HarvestEventMethods,
  SalesEventMethods,
  ExpenseEventMethods,
  SensorReadingMethods,
  WalletProfileMethods,
  AttestationMethods,
  ReportMethods,
  ExportMethods,
  NoiMethods,
} from './methods.js';

export interface KokonutClientOptions {
  token?: string;
}

export class KokonutClient {
  private directus;
  private _auth;

  locations: LocationMethods;
  farms: FarmMethods;
  plots: PlotMethods;
  cropCycles: CropCycleMethods;
  harvestEvents: HarvestEventMethods;
  salesEvents: SalesEventMethods;
  expenseEvents: ExpenseEventMethods;
  sensorReadings: SensorReadingMethods;
  walletProfiles: WalletProfileMethods;
  attestations: AttestationMethods;
  reports: ReportMethods;
  exports: ExportMethods;
  noi: NoiMethods;

  constructor(baseUrl: string, options?: KokonutClientOptions) {
    this.directus = createDirectus(baseUrl).with(rest());
    this._auth = createDirectus(baseUrl).with(rest()).with(authentication());

    if (options?.token) {
      this.directus.setToken(options.token);
      this._auth.setToken(options.token);
    }

    this.locations = buildLocationMethods(this);
    this.farms = buildFarmMethods(this);
    this.plots = buildPlotMethods(this);
    this.cropCycles = buildCropCycleMethods(this);
    this.harvestEvents = buildHarvestEventMethods(this);
    this.salesEvents = buildSalesEventMethods(this);
    this.expenseEvents = buildExpenseEventMethods(this);
    this.sensorReadings = buildSensorReadingMethods(this);
    this.walletProfiles = buildWalletProfileMethods(this);
    this.attestations = buildAttestationMethods(this);
    this.reports = buildReportMethods(this);
    this.exports = buildExportMethods(this);
    this.noi = buildNoiMethods(this);
  }

  async login(email: string, password: string): Promise<{ token: string; refreshToken: string }> {
    const result = await this._auth.login(email, password);
    const token = result.access_token ?? result.token ?? '';
    const refreshToken = result.refresh_token ?? '';
    this.directus.setToken(token);
    return { token, refreshToken };
  }

  async logout(): Promise<void> {
    await this._auth.logout();
    this.directus.setToken(null);
  }

  async listItems(collection: string, options?: ListOptions): Promise<any[]> {
    const query: Record<string, any> = {};

    if (options?.filter) query.filter = options.filter;
    if (options?.sort) query.sort = options.sort;
    if (options?.fields) query.fields = options.fields;
    if (options?.limit) query.limit = options.limit;
    if (options?.offset) query.page = Math.floor((options.offset ?? 0) / (options.limit ?? 100)) + 1;
    if (options?.page) query.page = options.page;
    if (options?.meta) query.meta = options.meta;

    return this.directus.request(this.directus.readItems(collection, query));
  }

  async getItem(collection: string, id: string, fields?: string[]): Promise<any> {
    const query: Record<string, any> = {};
    if (fields) query.fields = fields;

    return this.directus.request(this.directus.readItem(collection, id, query));
  }

  async createItem(collection: string, data: Record<string, any>): Promise<any> {
    return this.directus.request(this.directus.createItem(collection, data));
  }

  async createItems(collection: string, data: Record<string, any>[]): Promise<any[]> {
    return this.directus.request(this.directus.createItems(collection, data));
  }

  async updateItem(collection: string, id: string, data: Record<string, any>): Promise<any> {
    return this.directus.request(this.directus.updateItem(collection, id, data));
  }

  async deleteItem(collection: string, id: string): Promise<void> {
    await this.directus.request(this.directus.deleteItem(collection, id));
  }
}
