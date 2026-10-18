import {
  createDirectus,
  rest,
  authentication,
  readItems,
  readItem,
  createItem,
  createItems,
  updateItem,
  deleteItem,
  aggregate as aggregateItems,
} from '@directus/sdk';
import type { AuthenticationData } from '@directus/sdk';
import { normalizeDirectusError } from './errors.js';
import type {
  BuyerDemandSignal,
  BuyerSegment,
  ChangePoint,
  ListOptions,
  CarbonCredit,
  CreditAdjustment,
  CreditRetirement,
  CreditTransfer,
  CashFlowSnapshot,
  FinancialTransaction,
  DemandTrend,
  DemandForecast,
  ForecastOutput,
  ForecastScenario,
  EnvironmentalBaseline,
  MarketSizeEstimate,
  MetricValue,
  MrvClaim,
  PriceObservation,
  ProductionMarketMatch,
  RemoteSensingObservation,
  SeasonalDecomposition,
  SoilCarbonMeasurement,
  SoilSample,
  SpeciesObservation,
  TimeSeriesForecast,
  TrendDashboardMetric,
  TrendEstimate,
  TrendSmoothing,
  ValueFlowEvent,
  WeatherObservation,
} from './types.js';
import {
  buildLocationReadMethods,
  buildLocationMethods,
  buildFarmMethods,
  buildPlotMethods,
  buildCropCycleMethods,
  buildHarvestEventMethods,
  buildSalesEventMethods,
  buildExpenseEventMethods,
  buildLossEventMethods,
  buildLaborEventMethods,
  buildFieldNoteMethods,
  buildSensorReadingMethods,
  buildWalletProfileMethods,
  buildAttestationMethods,
  buildReportMethods,
  buildExportMethods,
  buildNoiMethods,
} from './methods.js';
import type {
  LocationReadMethods,
  LocationMethods,
  FarmMethods,
  PlotMethods,
  CropCycleMethods,
  HarvestEventMethods,
  SalesEventMethods,
  ExpenseEventMethods,
  LossEventMethods,
  LaborEventMethods,
  FieldNoteMethods,
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

export type KokonutLoginResult = AuthenticationData & {
  token: string;
  refreshToken: string;
};

export type KokonutAggregationOptions = {
  aggregate: Record<string, any>;
  groupBy?: string[];
  query?: Record<string, any>;
};

export class KokonutClient {
  private directus;
  private ready: Promise<void>;

  locations: LocationMethods;
  farms: FarmMethods;
  plots: PlotMethods;
  cropCycles: CropCycleMethods;
  harvestEvents: HarvestEventMethods;
  salesEvents: SalesEventMethods;
  expenseEvents: ExpenseEventMethods;
  lossEvents: LossEventMethods;
  laborEvents: LaborEventMethods;
  fieldNotes: FieldNoteMethods;
  sensorReadings: SensorReadingMethods;
  walletProfiles: WalletProfileMethods;
  attestations: AttestationMethods;
  reports: ReportMethods;
  exports: ExportMethods;
  noi: NoiMethods;
  carbonCredits: LocationReadMethods<CarbonCredit>;
  creditAdjustments: LocationReadMethods<CreditAdjustment>;
  creditRetirements: LocationReadMethods<CreditRetirement>;
  creditTransfers: LocationReadMethods<CreditTransfer>;
  financialTransactions: LocationReadMethods<FinancialTransaction>;
  cashFlowSnapshots: LocationReadMethods<CashFlowSnapshot>;
  weatherObservations: LocationReadMethods<WeatherObservation>;
  soilSamples: LocationReadMethods<SoilSample>;
  soilCarbonMeasurements: LocationReadMethods<SoilCarbonMeasurement>;
  environmentalBaselines: LocationReadMethods<EnvironmentalBaseline>;
  speciesObservations: LocationReadMethods<SpeciesObservation>;
  remoteSensingObservations: LocationReadMethods<RemoteSensingObservation>;
  mrvClaims: LocationReadMethods<MrvClaim>;
  metricValues: LocationReadMethods<MetricValue>;
  forecastScenarios: LocationReadMethods<ForecastScenario>;
  forecastOutputs: LocationReadMethods<ForecastOutput>;
  timeSeriesForecasts: LocationReadMethods<TimeSeriesForecast>;
  demandForecasts: LocationReadMethods<DemandForecast>;
  marketSizeEstimates: LocationReadMethods<MarketSizeEstimate>;
  priceObservations: LocationReadMethods<PriceObservation>;
  demandTrends: LocationReadMethods<DemandTrend>;
  buyerDemandSignals: LocationReadMethods<BuyerDemandSignal>;
  productionMarketMatches: LocationReadMethods<ProductionMarketMatch>;
  buyerSegments: LocationReadMethods<BuyerSegment>;
  valueFlowEvents: LocationReadMethods<ValueFlowEvent>;
  trendEstimates: LocationReadMethods<TrendEstimate>;
  trendSmoothing: LocationReadMethods<TrendSmoothing>;
  changePoints: LocationReadMethods<ChangePoint>;
  seasonalDecompositions: LocationReadMethods<SeasonalDecomposition>;
  trendDashboardMetrics: LocationReadMethods<TrendDashboardMetric>;

  constructor(baseUrl: string, options?: KokonutClientOptions) {
    this.directus = createDirectus(baseUrl).with(rest()).with(authentication());
    this.ready = options?.token
      ? this.directus.setToken(options.token).then(() => undefined)
      : Promise.resolve();

    this.locations = buildLocationMethods(this);
    this.farms = buildFarmMethods(this);
    this.plots = buildPlotMethods(this);
    this.cropCycles = buildCropCycleMethods(this);
    this.harvestEvents = buildHarvestEventMethods(this);
    this.salesEvents = buildSalesEventMethods(this);
    this.expenseEvents = buildExpenseEventMethods(this);
    this.lossEvents = buildLossEventMethods(this);
    this.laborEvents = buildLaborEventMethods(this);
    this.fieldNotes = buildFieldNoteMethods(this);
    this.sensorReadings = buildSensorReadingMethods(this);
    this.walletProfiles = buildWalletProfileMethods(this);
    this.attestations = buildAttestationMethods(this);
    this.reports = buildReportMethods(this);
    this.exports = buildExportMethods(this);
    this.noi = buildNoiMethods(this);
    this.carbonCredits = buildLocationReadMethods<CarbonCredit>(this, 'carbon_credit');
    this.creditAdjustments = buildLocationReadMethods<CreditAdjustment>(this, 'credit_adjustment');
    this.creditRetirements = buildLocationReadMethods<CreditRetirement>(this, 'credit_retirement');
    this.creditTransfers = buildLocationReadMethods<CreditTransfer>(this, 'credit_transfer');
    this.financialTransactions = buildLocationReadMethods<FinancialTransaction>(this, 'financial_transaction');
    this.cashFlowSnapshots = buildLocationReadMethods<CashFlowSnapshot>(this, 'cash_flow_snapshot');
    this.weatherObservations = buildLocationReadMethods<WeatherObservation>(this, 'weather_observation');
    this.soilSamples = buildLocationReadMethods<SoilSample>(this, 'soil_sample');
    this.soilCarbonMeasurements = buildLocationReadMethods<SoilCarbonMeasurement>(this, 'soil_carbon_measurement');
    this.environmentalBaselines = buildLocationReadMethods<EnvironmentalBaseline>(this, 'environmental_baseline');
    this.speciesObservations = buildLocationReadMethods<SpeciesObservation>(this, 'species_observation');
    this.remoteSensingObservations = buildLocationReadMethods<RemoteSensingObservation>(this, 'remote_sensing_observation');
    this.mrvClaims = buildLocationReadMethods<MrvClaim>(this, 'mrv_claim');
    this.metricValues = buildLocationReadMethods<MetricValue>(this, 'metric_value');
    this.forecastScenarios = buildLocationReadMethods<ForecastScenario>(this, 'forecast_scenario');
    this.forecastOutputs = buildLocationReadMethods<ForecastOutput>(this, 'forecast_output');
    this.timeSeriesForecasts = buildLocationReadMethods<TimeSeriesForecast>(this, 'time_series_forecast');
    this.demandForecasts = buildLocationReadMethods<DemandForecast>(this, 'demand_forecast');
    this.marketSizeEstimates = buildLocationReadMethods<MarketSizeEstimate>(this, 'market_size_estimate');
    this.priceObservations = buildLocationReadMethods<PriceObservation>(this, 'price_observation');
    this.demandTrends = buildLocationReadMethods<DemandTrend>(this, 'demand_trend');
    this.buyerDemandSignals = buildLocationReadMethods<BuyerDemandSignal>(this, 'buyer_demand_signal');
    this.productionMarketMatches = buildLocationReadMethods<ProductionMarketMatch>(this, 'production_market_match');
    this.buyerSegments = buildLocationReadMethods<BuyerSegment>(this, 'buyer_segment');
    this.valueFlowEvents = buildLocationReadMethods<ValueFlowEvent>(this, 'value_flow_event');
    this.trendEstimates = buildLocationReadMethods<TrendEstimate>(this, 'trend_estimate');
    this.trendSmoothing = buildLocationReadMethods<TrendSmoothing>(this, 'trend_smoothing');
    this.changePoints = buildLocationReadMethods<ChangePoint>(this, 'change_point');
    this.seasonalDecompositions = buildLocationReadMethods<SeasonalDecomposition>(this, 'seasonal_decomposition');
    this.trendDashboardMetrics = buildLocationReadMethods<TrendDashboardMetric>(this, 'trend_dashboard_metric');
  }

  async login(email: string, password: string): Promise<KokonutLoginResult> {
    await this.ready;
    const result = await this.run(() => this.directus.login(email, password));
    const token = result.access_token ?? '';
    const refreshToken = result.refresh_token ?? '';
    await this.directus.setToken(token);
    return { ...result, token, refreshToken };
  }

  async logout(): Promise<void> {
    await this.ready;
    try {
      await this.directus.logout();
    } catch {
      // Local logout must still clear credentials when the server is unreachable.
    } finally {
      await this.directus.setToken(null);
    }
  }

  async listItems(collection: string, options?: ListOptions): Promise<any[]> {
    const query: Record<string, any> = { ...(options ?? {}) };

    for (const key of ['filter', 'sort', 'fields', 'limit', 'offset', 'page', 'meta']) {
      delete query[key];
    }

    if (options?.filter) query.filter = options.filter;
    if (options?.sort) query.sort = options.sort;
    if (options?.fields) query.fields = options.fields;
    if (options?.limit !== undefined) query.limit = options.limit;
    if (options?.offset !== undefined && options.limit !== undefined) {
      if (options.limit === 0) {
        throw new RangeError('offset pagination requires a non-zero limit');
      }
      query.offset = options.offset;
    } else if (options?.page !== undefined) {
      query.page = options.page;
    }
    if (options?.meta !== undefined) query.meta = options.meta;

    return this.execute(() => this.directus.request(readItems(collection, query)));
  }

  async getItem(collection: string, id: string, fields?: string[]): Promise<any> {
    const query: Record<string, any> = {};
    if (fields) query.fields = fields;

    return this.execute(() => this.directus.request(readItem(collection, id, query)));
  }

  async createItem(collection: string, data: Record<string, any>): Promise<any> {
    return this.execute(() => this.directus.request(createItem(collection, data)));
  }

  async createItems(collection: string, data: Record<string, any>[]): Promise<any[]> {
    return this.execute(() => this.directus.request(createItems(collection, data)));
  }

  async updateItem(collection: string, id: string, data: Record<string, any>): Promise<any> {
    return this.execute(() => this.directus.request(updateItem(collection, id, data)));
  }

  async deleteItem(collection: string, id: string): Promise<void> {
    await this.execute(() => this.directus.request(deleteItem(collection, id)));
  }

  async aggregate(collection: string, options: KokonutAggregationOptions): Promise<any[]> {
    return this.execute(() => this.directus.request(aggregateItems(collection, options)));
  }

  private async execute<T>(operation: () => Promise<T>): Promise<T> {
    await this.ready;
    return this.run(operation);
  }

  private async run<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      throw normalizeDirectusError(error);
    }
  }
}
