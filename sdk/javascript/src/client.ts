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
  AssessmentDimension,
  AssessmentSignal,
  AttestationSchema,
  CrispCarbonYieldRisk,
  CrispClimateRisk,
  CrispFinancialRisk,
  CrispImplementationRisk,
  CrispPolicyRisk,
  CrispRiskAssessment,
  BufferZone,
  HarvestHandlingRecord,
  OrganicCertificationRecord,
  OrganicComplianceChecklist,
  OrganicInputAudit,
  OrganicReadinessAssessment,
  OrganicTransitionPlan,
  ProhibitedSubstanceRecord,
  CausalLink,
  CausalLoop,
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
  FarmTask,
  ForecastAccuracy,
  GeostatCVResult,
  GeostatRealization,
  GeostatRealizationPoint,
  ForecastOutput,
  ForecastScenario,
  Crop,
  EnvironmentalBaseline,
  InfrastructureAsset,
  KrigingPoint,
  KrigingPrediction,
  LeverageAssessment,
  MarketSizeEstimate,
  MetricValue,
  MrvClaim,
  OodaCycleLog,
  PriceObservation,
  ProductionMarketMatch,
  Protocol,
  RemoteSensingObservation,
  SeasonalDecomposition,
  SensorType,
  SensorDevice,
  SensorAlert,
  SituationAssessment,
  SensorNetworkDesign,
  StockFlowModel,
  StockFlowRun,
  StructuralAssumption,
  SystemArchetype,
  SystemVariable,
  SpatialAutocorrelation,
  TimeDelay,
  SoilCarbonMeasurement,
  SoilSample,
  SpeciesObservation,
  TimeSeriesForecast,
  TrendDashboardMetric,
  TrendEstimate,
  TrendSmoothing,
  ValueFlowEvent,
  VariogramModel,
  WeatherObservation,
} from './types.js';

function encodeDirectusPathSegment(value: string, name: string): string {
  if (typeof value !== 'string') {
    throw new TypeError(`${name} must be a string`);
  }
  if (value.length === 0 || value === '.' || value === '..') {
    throw new TypeError(`${name} must be a non-empty path segment`);
  }
  return encodeURIComponent(value);
}
import {
  buildLocationReadMethods,
  buildReferenceReadMethods,
  buildCausalLinkReadMethods,
  buildAssessmentChildReadMethods,
  buildAssessmentLocationReadMethods,
  buildForecastAccuracyReadMethods,
  buildKrigingPointReadMethods,
  buildGeostatRealizationPointReadMethods,
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
  ReferenceReadMethods,
  CausalLinkReadMethods,
  AssessmentChildReadMethods,
  AssessmentLocationReadMethods,
  ForecastAccuracyReadMethods,
  KrigingPointReadMethods,
  GeostatRealizationPointReadMethods,
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
  sensorDevices: LocationReadMethods<SensorDevice>;
  sensorAlerts: LocationReadMethods<SensorAlert>;
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
  forecastAccuracies: ForecastAccuracyReadMethods<ForecastAccuracy>;
  variogramModels: LocationReadMethods<VariogramModel>;
  krigingPredictions: LocationReadMethods<KrigingPrediction>;
  krigingPoints: KrigingPointReadMethods<KrigingPoint>;
  geostatRealizations: LocationReadMethods<GeostatRealization>;
  geostatRealizationPoints: GeostatRealizationPointReadMethods<GeostatRealizationPoint>;
  spatialAutocorrelations: LocationReadMethods<SpatialAutocorrelation>;
  geostatCvResults: LocationReadMethods<GeostatCVResult>;
  sensorNetworkDesigns: LocationReadMethods<SensorNetworkDesign>;
  causalLoops: ReferenceReadMethods<CausalLoop>;
  causalLinks: CausalLinkReadMethods<CausalLink>;
  situationAssessments: LocationReadMethods<SituationAssessment>;
  assessmentSignals: AssessmentChildReadMethods<AssessmentSignal>;
  assessmentDimensions: AssessmentChildReadMethods<AssessmentDimension>;
  oodaCycleLogs: LocationReadMethods<OodaCycleLog>;
  crispRiskAssessments: LocationReadMethods<CrispRiskAssessment>;
  crispCarbonYieldRisks: AssessmentLocationReadMethods<CrispCarbonYieldRisk>;
  crispClimateRisks: AssessmentLocationReadMethods<CrispClimateRisk>;
  crispPolicyRisks: AssessmentLocationReadMethods<CrispPolicyRisk>;
  crispFinancialRisks: AssessmentLocationReadMethods<CrispFinancialRisk>;
  crispImplementationRisks: AssessmentLocationReadMethods<CrispImplementationRisk>;
  organicCertificationRecords: LocationReadMethods<OrganicCertificationRecord>;
  organicTransitionPlans: LocationReadMethods<OrganicTransitionPlan>;
  prohibitedSubstanceRecords: LocationReadMethods<ProhibitedSubstanceRecord>;
  bufferZones: LocationReadMethods<BufferZone>;
  organicInputAudits: LocationReadMethods<OrganicInputAudit>;
  harvestHandlingRecords: LocationReadMethods<HarvestHandlingRecord>;
  organicComplianceChecklists: LocationReadMethods<OrganicComplianceChecklist>;
  organicReadinessAssessments: LocationReadMethods<OrganicReadinessAssessment>;
  systemVariables: LocationReadMethods<SystemVariable>;
  stockFlowModels: ReferenceReadMethods<StockFlowModel>;
  stockFlowRuns: LocationReadMethods<StockFlowRun>;
  systemArchetypes: LocationReadMethods<SystemArchetype>;
  leverageAssessments: LocationReadMethods<LeverageAssessment>;
  timeDelays: ReferenceReadMethods<TimeDelay>;
  structuralAssumptions: LocationReadMethods<StructuralAssumption>;
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
  infrastructureAssets: LocationReadMethods<InfrastructureAsset>;
  farmTasks: LocationReadMethods<FarmTask>;
  crops: ReferenceReadMethods<Crop>;
  protocols: ReferenceReadMethods<Protocol>;
  sensorTypes: ReferenceReadMethods<SensorType>;
  attestationSchemas: ReferenceReadMethods<AttestationSchema>;

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
    this.sensorDevices = buildLocationReadMethods<SensorDevice>(this, 'sensor_device');
    this.sensorAlerts = buildLocationReadMethods<SensorAlert>(this, 'sensor_alert');
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
    this.forecastAccuracies = buildForecastAccuracyReadMethods<ForecastAccuracy>(this);
    this.variogramModels = buildLocationReadMethods<VariogramModel>(this, 'variogram_model');
    this.krigingPredictions = buildLocationReadMethods<KrigingPrediction>(this, 'kriging_prediction');
    this.krigingPoints = buildKrigingPointReadMethods<KrigingPoint>(this);
    this.geostatRealizations = buildLocationReadMethods<GeostatRealization>(this, 'geostat_realization');
    this.geostatRealizationPoints = buildGeostatRealizationPointReadMethods<GeostatRealizationPoint>(this);
    this.spatialAutocorrelations = buildLocationReadMethods<SpatialAutocorrelation>(this, 'spatial_autocorrelation');
    this.geostatCvResults = buildLocationReadMethods<GeostatCVResult>(this, 'geostat_cv_result');
    this.sensorNetworkDesigns = buildLocationReadMethods<SensorNetworkDesign>(this, 'sensor_network_design');
    this.causalLoops = buildReferenceReadMethods<CausalLoop>(this, 'causal_loop');
    this.causalLinks = buildCausalLinkReadMethods<CausalLink>(this);
    this.systemVariables = buildLocationReadMethods<SystemVariable>(this, 'system_variable');
    this.stockFlowModels = buildReferenceReadMethods<StockFlowModel>(this, 'stock_flow_model');
    this.stockFlowRuns = buildLocationReadMethods<StockFlowRun>(this, 'stock_flow_run');
    this.systemArchetypes = buildLocationReadMethods<SystemArchetype>(this, 'system_archetype');
    this.leverageAssessments = buildLocationReadMethods<LeverageAssessment>(this, 'leverage_assessment');
    this.timeDelays = buildReferenceReadMethods<TimeDelay>(this, 'time_delay');
    this.structuralAssumptions = buildLocationReadMethods<StructuralAssumption>(this, 'structural_assumption');
    this.situationAssessments = buildLocationReadMethods<SituationAssessment>(this, 'situation_assessment');
    this.assessmentSignals = buildAssessmentChildReadMethods<AssessmentSignal>(this, 'assessment_signal');
    this.assessmentDimensions = buildAssessmentChildReadMethods<AssessmentDimension>(this, 'assessment_dimension');
    this.oodaCycleLogs = buildLocationReadMethods<OodaCycleLog>(this, 'ooda_cycle_log');
    this.crispRiskAssessments = buildLocationReadMethods<CrispRiskAssessment>(this, 'crisp_risk_assessment');
    this.crispCarbonYieldRisks = buildAssessmentLocationReadMethods<CrispCarbonYieldRisk>(this, 'crisp_carbon_yield_risk');
    this.crispClimateRisks = buildAssessmentLocationReadMethods<CrispClimateRisk>(this, 'crisp_climate_risk');
    this.crispPolicyRisks = buildAssessmentLocationReadMethods<CrispPolicyRisk>(this, 'crisp_policy_risk');
    this.crispFinancialRisks = buildAssessmentLocationReadMethods<CrispFinancialRisk>(this, 'crisp_financial_risk');
    this.crispImplementationRisks = buildAssessmentLocationReadMethods<CrispImplementationRisk>(this, 'crisp_implementation_risk');
    this.organicCertificationRecords = buildLocationReadMethods<OrganicCertificationRecord>(this, 'organic_certification_record');
    this.organicTransitionPlans = buildLocationReadMethods<OrganicTransitionPlan>(this, 'organic_transition_plan');
    this.prohibitedSubstanceRecords = buildLocationReadMethods<ProhibitedSubstanceRecord>(this, 'prohibited_substance_record');
    this.bufferZones = buildLocationReadMethods<BufferZone>(this, 'buffer_zone');
    this.organicInputAudits = buildLocationReadMethods<OrganicInputAudit>(this, 'organic_input_audit');
    this.harvestHandlingRecords = buildLocationReadMethods<HarvestHandlingRecord>(this, 'harvest_handling_record');
    this.organicComplianceChecklists = buildLocationReadMethods<OrganicComplianceChecklist>(this, 'organic_compliance_checklist');
    this.organicReadinessAssessments = buildLocationReadMethods<OrganicReadinessAssessment>(this, 'organic_readiness_assessment');
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
    this.infrastructureAssets = buildLocationReadMethods<InfrastructureAsset>(this, 'infrastructure_asset');
    this.farmTasks = buildLocationReadMethods<FarmTask>(this, 'farm_task');
    this.crops = buildReferenceReadMethods<Crop>(this, 'crop');
    this.protocols = buildReferenceReadMethods<Protocol>(this, 'protocol');
    this.sensorTypes = buildReferenceReadMethods<SensorType>(this, 'sensor_type');
    this.attestationSchemas = buildReferenceReadMethods<AttestationSchema>(this, 'attestation_schema');
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

    return this.execute(() =>
      this.directus.request(readItems(encodeDirectusPathSegment(collection, 'collection'), query)),
    );
  }

  async getItem(collection: string, id: string, fields?: string[]): Promise<any> {
    const query: Record<string, any> = {};
    if (fields) query.fields = fields;

    return this.execute(() =>
      this.directus.request(
        readItem(
          encodeDirectusPathSegment(collection, 'collection'),
          encodeDirectusPathSegment(id, 'id'),
          query,
        ),
      ),
    );
  }

  async createItem(collection: string, data: Record<string, any>): Promise<any> {
    return this.execute(() =>
      this.directus.request(createItem(encodeDirectusPathSegment(collection, 'collection'), data)),
    );
  }

  async createItems(collection: string, data: Record<string, any>[]): Promise<any[]> {
    return this.execute(() =>
      this.directus.request(createItems(encodeDirectusPathSegment(collection, 'collection'), data)),
    );
  }

  async updateItem(collection: string, id: string, data: Record<string, any>): Promise<any> {
    return this.execute(() =>
      this.directus.request(
        updateItem(
          encodeDirectusPathSegment(collection, 'collection'),
          encodeDirectusPathSegment(id, 'id'),
          data,
        ),
      ),
    );
  }

  async deleteItem(collection: string, id: string): Promise<void> {
    await this.execute(() =>
      this.directus.request(
        deleteItem(
          encodeDirectusPathSegment(collection, 'collection'),
          encodeDirectusPathSegment(id, 'id'),
        ),
      ),
    );
  }

  async aggregate(collection: string, options: KokonutAggregationOptions): Promise<any[]> {
    return this.execute(() =>
      this.directus.request(
        aggregateItems(encodeDirectusPathSegment(collection, 'collection'), options),
      ),
    );
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
