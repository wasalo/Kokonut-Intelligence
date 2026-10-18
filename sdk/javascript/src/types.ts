export type JSONScalar = string | number | boolean | null;
export type JSONValue = JSONScalar | JSONValue[] | { [key: string]: JSONValue };
export type JSONObject = { [key: string]: JSONValue };
export type LifecycleStatus = 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
export type EntityStatus = 'active' | 'inactive' | 'archived';
export type EntityStatusExtended = 'active' | 'inactive' | 'maintenance' | 'decommissioned';
export type PaymentStatus = 'pending' | 'partial' | 'paid' | 'overdue' | 'cancelled';
export type SensorSeverity = 'info' | 'warning' | 'critical';
export type AlertLifecycle = 'open' | 'acknowledged' | 'resolved' | 'false_positive';
export type ExportStatus = 'pending' | 'generating' | 'completed' | 'failed';
export type OrganizationType = 'cooperative' | 'nonprofit' | 'dao' | 'enterprise' | 'collective' | 'other';
export type OrganizationStatus = 'active' | 'inactive' | 'dissolved';
export type OrganizationMembershipType = 'owned' | 'affiliated' | 'sponsored' | 'partner';
export type OrganizationMemberRole = 'primary' | 'satellite' | 'partner' | 'incubated';
export type OrganizationMemberStatus = 'active' | 'inactive' | 'suspended';
export type ActuatorType = 'irrigation' | 'pest_control' | 'fertilization' | 'notification' | 'custom';
export type ActuationStatus = 'pending' | 'sent' | 'acknowledged' | 'executed' | 'failed' | 'requires_approval';
export type AttestationVerdict = 'pending' | 'approved' | 'rejected' | 'needs_info';
export type TimeSeriesForecastModelType = 'arima' | 'exponential_smoothing' | 'prophet' | 'naive' | 'seasonal_naive';
export type TimeSeriesForecastStatus = 'active' | 'superseded' | 'expired';
export type DemandForecastType = 'time_series' | 'buyer_pipeline' | 'seasonal_decomposition' | 'hybrid';
export type DemandForecastStatus = 'draft' | 'submitted' | 'verified' | 'published';
export type MarketScope = 'local' | 'regional' | 'national' | 'international';
export type MarketSizeEstimateStatus = 'draft' | 'submitted' | 'verified' | 'published';
export type DemandTrendAnalysisType = 'seasonal_pattern' | 'price_elasticity' | 'moving_average' | 'trend_decomposition';
export type DemandTrendStatus = 'draft' | 'submitted' | 'verified' | 'published';
export type BuyerSignalType = 'verbal_intent' | 'written_order' | 'purchase_order' | 'forecast_request' | 'recurring_order';
export type BuyerType = 'processor' | 'direct' | 'market' | 'restaurant' | 'retailer' | 'export' | 'cooperative' | 'other';
export type BuyerCommitmentLevel = 'firm' | 'probable' | 'possible' | 'exploratory';
export type BuyerSignalStatus = 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
export type BuyerSegmentType = 'value_based' | 'behavior_based' | 'need_based' | 'tier_based';
export type BuyerSegmentValue = 'high_value' | 'medium_value' | 'low_value' | 'potential' | 'at_risk' | 'churned';
export type TrendDirection = 'improving' | 'stable' | 'declining' | 'insufficient_data';
export type TrendConfidenceLevel = 'high' | 'moderate' | 'low' | 'insufficient_data';
export type TrendSmoothingType = 'moving_average' | 'weighted_moving_average' | 'exponential' | 'holt_linear';
export type ChangePointDetectionMethod = 'cusum' | 'pelt' | 'binary_segmentation' | 'window_slider';
export type ChangePointDirection = 'increase' | 'decrease' | 'variance_change';
export type ChangePointStatus = 'detected' | 'confirmed' | 'dismissed';
export type SeasonalDecompositionMethod = 'classical' | 'stl' | 'x11';

export type GeoJSONPosition = [longitude: number, latitude: number, altitude?: number];

export interface GeoJSONPoint {
  type: 'Point';
  coordinates: GeoJSONPosition;
}

export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: GeoJSONPosition[][];
}

export interface Location {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  project_url?: string | null;
  project_start_date?: string | null;
  project_end_date?: string | null;
  boundary?: GeoJSONPolygon | null;
  center?: GeoJSONPoint | null;
  country?: string | null;
  region?: string | null;
  sub_region?: string | null;
  timezone?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  baseline_revenue?: number | null;
  baseline_asset_value?: number | null;
  baseline_cash_flow?: number | null;
  baseline_cost?: number | null;
  baseline_assumptions?: JSONObject | null;
  baseline_source?: string | null;
  baseline_date?: string | null;
  baseline_recorded_at?: string | null;
  bioregion?: string[] | null;
  biome_type?: string[] | null;
  watershed?: string | null;
  sub_watershed?: string | null;
  organization_id?: string | null;
  schema_version?: string | null;
  status?: EntityStatus | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Organization record; membership rows do not grant tenant access. */
export interface Organization {
  id: string;
  org_key: string;
  name: string;
  org_type: OrganizationType;
  description?: string | null;
  logo_url?: string | null;
  website?: string | null;
  contact_email?: string | null;
  legal_entity_name?: string | null;
  jurisdiction?: string | null;
  governance_model?: string | null;
  status: OrganizationStatus;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Descriptive organization/location link; it does not grant tenant access. */
export interface OrganizationMember {
  id: string;
  organization_id: string;
  location_id: string;
  team_id?: string | null;
  farm_id?: string | null;
  membership_type: OrganizationMembershipType;
  join_date: string;
  role: OrganizationMemberRole;
  status: OrganizationMemberStatus;
  metadata?: JSONObject | null;
  created_at: string;
  updated_at: string;
}

export interface Farm {
  id: string;
  location_id: string;
  name: string;
  slug: string;
  description?: string | null;
  boundary?: GeoJSONPolygon | null;
  center?: GeoJSONPoint | null;
  logo_url?: string | null;
  logo_file_id?: string | null;
  property_id?: string | null;
  traditional_name?: string | null;
  languages?: string[] | null;
  global_standard_certifications?: string[] | null;
  economic_sectors?: string[] | null;
  credits_registries?: string[] | null;
  data_privacy_status?: string | null;
  data_privacy_standard?: string | null;
  data_privacy_criteria?: JSONObject | null;
  farm_type?: string | null;
  total_area?: number | null;
  area_unit?: string | null;
  status?: EntityStatus | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  schema_version?: string | null;
}

export interface Plot {
  id: string;
  farm_id: string;
  name: string;
  slug: string;
  description?: string | null;
  area?: number | null;
  area_unit?: string | null;
  boundary?: GeoJSONPolygon | null;
  center?: GeoJSONPoint | null;
  soil_type?: string | null;
  water_source?: string | null;
  elevation_m?: number | null;
  bed_count?: number | null;
  bed_area_sqm?: number | null;
  slope_pct?: number | null;
  aspect?: string | null;
  status?: EntityStatus | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  schema_version?: string | null;
}

export interface CropCycle {
  id: string;
  plot_id: string;
  crop_id: string;
  location_id: string;
  cycle_name?: string | null;
  season?: string | null;
  planting_date?: string | null;
  expected_harvest_date?: string | null;
  actual_harvest_date?: string | null;
  expected_yield?: number | null;
  expected_yield_unit?: string | null;
  actual_yield?: number | null;
  actual_yield_unit?: string | null;
  expected_price_per_unit?: number | null;
  expected_revenue?: number | null;
  actual_revenue?: number | null;
  planting_density?: number | null;
  planting_density_unit?: string | null;
  area_planted?: number | null;
  area_unit?: string | null;
  status?: string | null;
  failure_reason?: string | null;
  metadata?: JSONObject | null;
  schema_version?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface HarvestEvent {
  id: string;
  crop_cycle_id: string;
  plot_id: string;
  location_id: string;
  harvest_date: string;
  quantity: number;
  unit: string;
  quality_grade?: string | null;
  destination?: string | null;
  loss_amount?: number | null;
  loss_unit?: string | null;
  loss_reason?: string | null;
  loss_estimated_value?: number | null;
  evidence_urls?: string[] | null;
  evidence_hashes?: string[] | null;
  notes?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  submitted_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface SalesEvent {
  id: string;
  location_id: string;
  sale_date: string;
  quantity: number;
  unit: string;
  total_amount: number;
  harvest_id?: string | null;
  crop_cycle_id?: string | null;
  partner_id?: string | null;
  buyer?: string | null;
  buyer_type?: string | null;
  price_per_unit?: number | null;
  currency?: string | null;
  payment_status?: PaymentStatus | null;
  payment_date?: string | null;
  payment_method?: string | null;
  invoice_number?: string | null;
  return_amount?: number | null;
  discount_amount?: number | null;
  net_amount?: number | null;
  evidence_urls?: string[] | null;
  evidence_hashes?: string[] | null;
  notes?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  submitted_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface ExpenseEvent {
  id: string;
  location_id: string;
  expense_date: string;
  category: string;
  amount: number;
  plot_id?: string | null;
  crop_cycle_id?: string | null;
  farm_id?: string | null;
  farm_task_id?: string | null;
  weekly_plan_id?: string | null;
  subcategory?: string | null;
  description?: string | null;
  vendor?: string | null;
  vendor_id?: string | null;
  currency?: string | null;
  payment_status?: string | null;
  people_impacted_count?: number | null;
  weekly_plan_scope_exception?: boolean | null;
  weekly_plan_scope_exception_reason?: string | null;
  is_capex?: boolean | null;
  allocation_method?: string | null;
  allocation_weight?: number | null;
  evidence_urls?: string[] | null;
  receipt_hash?: string | null;
  invoice_number?: string | null;
  notes?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  submitted_at?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  rejection_reason?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface LossEvent {
  id: string;
  location_id: string;
  loss_date: string;
  loss_type: string;
  crop_cycle_id?: string | null;
  harvest_id?: string | null;
  plot_id?: string | null;
  quantity?: number | null;
  unit?: string | null;
  estimated_value?: number | null;
  cause?: string | null;
  impact_description?: string | null;
  mitigation?: string | null;
  severity?: string | null;
  evidence_urls?: string[] | null;
  evidence_hashes?: string[] | null;
  notes?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  submitted_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  created_by?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface LaborEvent {
  id: string;
  location_id: string;
  work_date: string;
  hours_worked: number;
  plot_id?: string | null;
  crop_cycle_id?: string | null;
  staff_id?: string | null;
  worker_name?: string | null;
  hourly_rate?: number | null;
  total_cost?: number | null;
  role?: string | null;
  activity_description?: string | null;
  notes?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  submitted_at?: string | null;
  rejection_reason?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  created_by?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface FieldNote {
  id: string;
  location_id: string;
  note_date: string;
  plot_id?: string | null;
  crop_cycle_id?: string | null;
  note_type?: string | null;
  title?: string | null;
  content?: string | null;
  images?: string[] | null;
  tags?: string[] | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  submitted_at?: string | null;
  rejection_reason?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  created_by?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface SensorReading {
  id: string;
  sensor_id: string;
  location_id: string;
  plot_id?: string | null;
  sensor_type?: string | null;
  reading_date: string;
  reading_time?: string | null;
  value: number;
  unit: string;
  quality?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  schema_version?: string | null;
}

export interface SensorType {
  id: string;
  name: string;
  unit: string;
  min_value?: number | null;
  max_value?: number | null;
  description?: string | null;
  created_at?: string | null;
}

export interface SensorDevice {
  id: string;
  name: string;
  slug: string;
  sensor_type_id: string;
  location_id: string;
  plot_id?: string | null;
  manufacturer?: string | null;
  model?: string | null;
  serial_number?: string | null;
  protocol?: string | null;
  endpoint_url?: string | null;
  status?: EntityStatusExtended | null;
  calibration_date?: string | null;
  calibration_interval_days?: number | null;
  installation_date?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  elevation_m?: number | null;
  point_geometry?: GeoJSONPoint | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface AlertRule {
  id: string;
  name: string;
  sensor_type_id: string;
  metric: 'value' | 'rate_of_change' | 'gap' | 'min' | 'max';
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'eq' | 'neq' | 'outside_range';
  threshold_value: number;
  threshold_value_max?: number | null;
  severity?: 'info' | 'warning' | 'critical' | null;
  cooldown_minutes?: number | null;
  enabled?: boolean | null;
  auto_create_claim?: boolean | null;
  claim_type?: string | null;
  actuator_enabled?: boolean | null;
  actuator_type?: ActuatorType | null;
  actuator_command?: string | null;
  actuator_topic?: string | null;
  human_approval_required?: boolean | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Descriptive entry in the shared expense taxonomy. */
export interface ExpenseCategory {
  id: string;
  name: string;
  code?: string | null;
  parent_id?: string | null;
  description?: string | null;
  is_direct?: boolean | null;
  allocation_default?: string | null;
  sort_order?: number | null;
  active?: boolean | null;
  created_at?: string | null;
  schema_version?: string | null;
}

/** Descriptive record of a funding source and its declared terms. */
export interface CapitalSource {
  id: string;
  name: string;
  source_type: string;
  description?: string | null;
  amount?: number | null;
  currency?: string | null;
  terms?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  status?: EntityStatus | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  schema_version?: string | null;
}

/** Recorded financial fact; this model does not initiate payments. */
export interface FinancialTransaction {
  id: string;
  location_id: string;
  transaction_date: string;
  transaction_type: string;
  amount: number;
  capital_source_id?: string | null;
  category?: string | null;
  subcategory?: string | null;
  currency?: string | null;
  exchange_rate?: number | null;
  amount_usd?: number | null;
  description?: string | null;
  reference?: string | null;
  counterparty?: string | null;
  payment_method?: string | null;
  reconciled?: boolean | null;
  reconciled_at?: string | null;
  bank_reference?: string | null;
  evidence_urls?: string[] | null;
  notes?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  created_by?: string | null;
}

/** Descriptive value-flow record; it does not perform verification or attest. */
export interface ValueFlowEvent {
  id: string;
  flow_date: string;
  flow_type: string;
  amount: number;
  location_id?: string | null;
  from_entity?: string | null;
  to_entity?: string | null;
  currency?: string | null;
  token?: string | null;
  chain?: string | null;
  tx_hash?: string | null;
  description?: string | null;
  verified?: boolean | null;
  verified_by?: string | null;
  verified_at?: string | null;
  attestation_uid?: string | null;
  is_excluded?: boolean | null;
  exclusion_reason?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  created_at?: string | null;
  created_by?: string | null;
}

/** Record of an excluded value-flow amount; it does not mutate the flow. */
export interface ExcludedValueEvent {
  id: string;
  exclusion_type: string;
  reason: string;
  value_flow_id?: string | null;
  amount?: number | null;
  currency?: string | null;
  excluded_by?: string | null;
  excluded_at?: string | null;
  created_at?: string | null;
}

/** Recorded cost-to-cycle allocation; it does not calculate or transfer funds. */
export interface CropCostAllocation {
  id: string;
  crop_cycle_id: string;
  expense_id: string;
  allocation_method: string;
  allocated_amount: number;
  allocation_ratio?: number | null;
  notes?: string | null;
  created_at?: string | null;
}

/** Governed metric metadata; this type does not compute or verify values. */
export interface MetricDefinition {
  id: string;
  metric_key: string;
  display_name: string;
  description?: string | null;
  formula?: string | null;
  source_tables?: string[] | null;
  inclusion_rules?: string | null;
  exclusion_rules?: string | null;
  unit?: string | null;
  data_type?: string | null;
  owner?: string | null;
  version?: number | null;
  update_frequency?: string | null;
  active?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
  validation_tests?: JSONObject[] | null;
  report_usage?: string[] | null;
  deprecation_policy?: string | null;
  definition_state?: string | null;
  category?: string | null;
  for_stakeholder_group?: string | null;
  participatory?: boolean | null;
}

/** Metric definition version history record. */
export interface MetricVersion {
  id: string;
  metric_id: string;
  version: number;
  formula?: string | null;
  changes?: string | null;
  change_reason?: string | null;
  created_at?: string | null;
  created_by?: string | null;
}

/** Stored metric result; computing it does not verify it. */
export interface MetricValue {
  id: string;
  metric_id: string;
  location_id?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  value?: number | null;
  unit?: string | null;
  computation_method?: string | null;
  source_record_ids?: string[] | null;
  computed_at?: string | null;
  verified?: boolean | null;
  verified_by?: string | null;
  verified_at?: string | null;
  verification_notes?: string | null;
  metadata?: JSONObject | null;
}

/** Scenario definition and assumptions; does not run the forecast engine. */
export interface ForecastScenario {
  id: string;
  name: string;
  assumptions: JSONObject;
  description?: string | null;
  scenario_type?: string | null;
  location_id?: string | null;
  price_assumptions?: JSONObject | null;
  yield_assumptions?: JSONObject | null;
  cost_assumptions?: JSONObject | null;
  growth_assumptions?: JSONObject | null;
  version?: number | null;
  parent_scenario_id?: string | null;
  status?: LifecycleStatus | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored forecast result; it does not establish verification. */
export interface ForecastOutput {
  id: string;
  scenario_id: string;
  metric_name: string;
  location_id?: string | null;
  crop_cycle_id?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  value?: number | null;
  unit?: string | null;
  confidence_low?: number | null;
  confidence_high?: number | null;
  confidence_level?: number | null;
  calculation_version?: string | null;
  calculated_at?: string | null;
  inputs?: JSONObject | null;
  created_by?: string | null;
}

/** Stored dashboard dataset definition; query text is not executed here. */
export interface DashboardDataset {
  id: string;
  name: string;
  description?: string | null;
  dataset_type?: string | null;
  location_id?: string | null;
  query_sql?: string | null;
  refresh_interval_minutes?: number | null;
  last_refreshed_at?: string | null;
  status?: LifecycleStatus | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}

/** Stored forecast series and model inputs; this record does not compute forecasts. */
export interface TimeSeriesForecast {
  id: string;
  metric_key: string;
  location_id: string;
  model_type: TimeSeriesForecastModelType;
  model_params: JSONObject;
  forecast_values: JSONValue[];
  prediction_intervals: JSONObject;
  forecast_horizon: number;
  time_unit: string;
  training_points: number;
  forecast_at: string;
  status: TimeSeriesForecastStatus;
  metadata?: JSONObject | null;
  created_at: string;
}

/** Stored forecast-versus-observation measurements; does not compute accuracy. */
export interface ForecastAccuracy {
  id: string;
  forecast_id: string;
  actual_timestamp: string;
  predicted_value: number;
  actual_value: number;
  error_abs: number;
  error_squared: number;
  error_pct?: number | null;
  is_within_ci?: boolean | null;
  computed_at: string;
  created_at: string;
}

/** Stored demand projection; creating this value does not calculate a forecast. */
export interface DemandForecast {
  id: string;
  location_id: string;
  forecast_type: DemandForecastType;
  forecast_period_start: string;
  forecast_period_end: string;
  predicted_quantity: number;
  unit: string;
  status: DemandForecastStatus;
  created_at: string;
  updated_at: string;
  crop_id?: string | null;
  predicted_revenue_usd?: number | null;
  confidence_low?: number | null;
  confidence_high?: number | null;
  confidence_level?: number | null;
  seasonal_index?: number | null;
  trend_slope?: number | null;
  model_name?: string | null;
  model_version?: string | null;
  training_data_points?: number | null;
  mape_pct?: number | null;
  inputs?: JSONObject | null;
  verified_by?: string | null;
  verified_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored TAM/SAM/SOM estimate with market scope and source fields. */
export interface MarketSizeEstimate {
  id: string;
  location_id: string;
  market_scope: MarketScope;
  status: MarketSizeEstimateStatus;
  created_at: string;
  updated_at: string;
  crop_id?: string | null;
  market_name?: string | null;
  tam_value?: number | null;
  tam_unit?: string | null;
  tam_source?: string | null;
  sam_value?: number | null;
  sam_unit?: string | null;
  sam_source?: string | null;
  som_value?: number | null;
  som_unit?: string | null;
  som_source?: string | null;
  market_penetration_pct?: number | null;
  market_share_pct?: number | null;
  annual_growth_rate_pct?: number | null;
  growth_source?: string | null;
  estimation_method?: string | null;
  confidence_level?: string | null;
  assessment_date?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  notes?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  metadata?: JSONObject | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored demand trend analysis and inputs; does not rerun its calculation. */
export interface DemandTrend {
  id: string;
  location_id: string;
  analysis_type: DemandTrendAnalysisType;
  period_start: string;
  period_end: string;
  status: DemandTrendStatus;
  created_at: string;
  updated_at: string;
  crop_id?: string | null;
  month_of_year?: number | null;
  seasonal_index?: number | null;
  seasonal_amplitude?: number | null;
  price_elasticity?: number | null;
  cross_price_elasticity?: number | null;
  reference_crop_id?: string | null;
  trend_direction?: string | null;
  trend_slope?: number | null;
  trend_r_squared?: number | null;
  moving_avg_3m?: number | null;
  moving_avg_6m?: number | null;
  moving_avg_12m?: number | null;
  avg_monthly_demand?: number | null;
  peak_month?: number | null;
  trough_month?: number | null;
  coefficient_of_variation?: number | null;
  model_name?: string | null;
  data_points?: number | null;
  calculation_version?: string | null;
  inputs?: JSONObject | null;
  verified_by?: string | null;
  verified_at?: string | null;
  created_by?: string | null;
}

/** Stored buyer intent/order signal; this record does not confirm fulfillment. */
export interface BuyerDemandSignal {
  id: string;
  location_id: string;
  signal_type: BuyerSignalType;
  signal_date: string;
  currency: string;
  recurring: boolean;
  status: BuyerSignalStatus;
  created_at: string;
  updated_at: string;
  partner_id?: string | null;
  crop_id?: string | null;
  buyer_name?: string | null;
  buyer_type?: BuyerType | null;
  expected_delivery_start?: string | null;
  expected_delivery_end?: string | null;
  quantity_requested?: number | null;
  unit?: string | null;
  price_offered?: number | null;
  recurrence_pattern?: string | null;
  reliability_score?: number | null;
  commitment_level?: BuyerCommitmentLevel | null;
  notes?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  rejection_reason?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  metadata?: JSONObject | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored production/demand comparison; does not calculate a supply gap. */
export interface ProductionMarketMatch {
  id: string;
  location_id: string;
  period_start: string;
  period_end: string;
  status: DemandForecastStatus;
  created_at: string;
  updated_at: string;
  crop_id?: string | null;
  projected_production_tonnes?: number | null;
  confirmed_supply_tonnes?: number | null;
  supply_source?: string | null;
  confirmed_demand_tonnes?: number | null;
  pipeline_demand_tonnes?: number | null;
  total_demand_tonnes?: number | null;
  demand_source?: string | null;
  supply_demand_gap_tonnes?: number | null;
  gap_pct?: number | null;
  demand_coverage_pct?: number | null;
  unallocated_tonnes?: number | null;
  unfulfilled_demand_tonnes?: number | null;
  estimated_revenue_at_fill?: number | null;
  revenue_gap_usd?: number | null;
  calculation_version?: string | null;
  inputs?: JSONObject | null;
  verified_by?: string | null;
  verified_at?: string | null;
  created_by?: string | null;
}

/** Stored buyer segment and measures; this type does not classify buyers. */
export interface BuyerSegment {
  id: string;
  location_id: string;
  segment_name: string;
  segment_type: BuyerSegmentType;
  criteria: JSONObject;
  status: DemandForecastStatus;
  created_at: string;
  updated_at: string;
  description?: string | null;
  buyer_count?: number | null;
  total_revenue_usd?: number | null;
  avg_order_value?: number | null;
  avg_payment_days?: number | null;
  repeat_purchase_rate?: number | null;
  growth_rate_pct?: number | null;
  segment_value?: BuyerSegmentValue | null;
  trend_direction?: string | null;
  assessment_date?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  notes?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  created_by?: string | null;
}

/** Stored trend fit and confidence metadata; this type does not fit a trend. */
export interface TrendEstimate {
  id: string;
  metric_key: string;
  location_id: string;
  period_start: string;
  period_end: string;
  data_points: number;
  slope: number;
  intercept: number;
  r_squared: number;
  standard_error: number;
  direction: TrendDirection;
  confidence_level: TrendConfidenceLevel;
  time_unit: string;
  computed_at: string;
  computed_by: string;
  created_at: string;
  slope_p_value?: number | null;
  slope_ci_lower?: number | null;
  slope_ci_upper?: number | null;
  metadata?: JSONObject | null;
}

/** Stored smoothed series value; this type does not perform smoothing. */
export interface TrendSmoothing {
  id: string;
  metric_key: string;
  location_id: string;
  smoothing_type: TrendSmoothingType;
  original_value: number;
  smoothed_value: number;
  timestamp: string;
  computed_at: string;
  created_at: string;
  window_size?: number | null;
  alpha?: number | null;
  beta?: number | null;
}

/** Stored detected regime change and its evidence fields. */
export interface ChangePoint {
  id: string;
  metric_key: string;
  location_id: string;
  detection_method: ChangePointDetectionMethod;
  change_point_index: number;
  magnitude: number;
  direction: ChangePointDirection;
  confidence: number;
  segment_count: number;
  status: ChangePointStatus;
  detected_at: string;
  created_at: string;
  change_point_timestamp?: string | null;
  pre_mean?: number | null;
  post_mean?: number | null;
  pre_std?: number | null;
  post_std?: number | null;
  classification?: string | null;
  metadata?: JSONObject | null;
}

/** Stored seasonal/trend/residual components; does not run decomposition. */
export interface SeasonalDecomposition {
  id: string;
  metric_key: string;
  location_id: string;
  period: number;
  trend_component: JSONValue[];
  seasonal_component: JSONValue[];
  residual_component: JSONValue[];
  data_points: number;
  computed_at: string;
  created_at: string;
  decomposition_method: SeasonalDecompositionMethod;
  seasonal_strength?: number | null;
  trend_strength?: number | null;
  residual_variance?: number | null;
  metadata?: JSONObject | null;
}

/** Stored summary metrics for trend dashboards; does not aggregate data. */
export interface TrendDashboardMetric {
  id: string;
  metric_key: string;
  location_id: string;
  computed_at: string;
  created_at: string;
  current_value?: number | null;
  trend_slope?: number | null;
  trend_direction?: string | null;
  trend_r_squared?: number | null;
  trend_significance?: string | null;
  seasonal_strength?: number | null;
  noise_level?: number | null;
  change_point_count?: number | null;
  last_change_point_at?: string | null;
  forecast_next_value?: number | null;
  forecast_accuracy_mae?: number | null;
}

export interface SensorAlert {
  id: string;
  sensor_device_id: string;
  alert_rule_id: string;
  reading_id?: string | null;
  severity: SensorSeverity;
  status?: AlertLifecycle | null;
  message: string;
  reading_value?: number | null;
  threshold_value?: number | null;
  triggered_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  resolved_at?: string | null;
  claim_id?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  actuation_sent?: boolean | null;
  actuation_response?: JSONObject | null;
  actuation_status?: ActuationStatus | null;
}

export interface WalletProfile {
  id: string;
  address: string;
  chain: string;
  chain_id?: number | null;
  role?: string | null;
  owner_type?: string | null;
  owner_id?: string | null;
  label?: string | null;
  is_active?: boolean | null;
  first_seen_date?: string | null;
  last_active_date?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AttestationRecord {
  id: string;
  schema_id: string;
  claim_data: JSONObject;
  attestation_uid?: string | null;
  claim_type?: string | null;
  subject_id?: string | null;
  subject_type?: string | null;
  evidence_hash?: string | null;
  evidence_cids?: string[] | null;
  evidence_urls?: string[] | null;
  status?: LifecycleStatus | null;
  reviewer_id?: string | null;
  review_notes?: string | null;
  reviewed_at?: string | null;
  chain?: string | null;
  tx_hash?: string | null;
  attested_at?: string | null;
  expiration_date?: string | null;
  revocation_date?: string | null;
  schema_version?: string | null;
  created_at?: string | null;
  created_by?: string | null;
  updated_at?: string | null;
  private_payload_hash?: string | null;
  payload_cid?: string | null;
  verdict?: AttestationVerdict | null;
  rationale?: string | null;
  evidence_reviewed?: string[] | null;
  graph_iri?: string | null;
  expires_at?: string | null;
  evaluator_id?: string | null;
}

export interface ReportSnapshot {
  id: string;
  report_name: string;
  report_data: JSONObject;
  report_type?: string | null;
  location_id?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  snapshot_hash?: string | null;
  file_url?: string | null;
  status?: LifecycleStatus | null;
  created_at?: string | null;
  created_by?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  generated_by?: string | null;
  frozen?: boolean | null;
  frozen_at?: string | null;
  frozen_by?: string | null;
  public_interest_summary?: string | null;
  uncertainty_notes?: string | null;
  negative_findings?: JSONObject[] | null;
  affected_community_voice?: string | null;
  expires_at?: string | null;
}

/** Stored agent narrative with source lineage and human review state. */
export interface AiSummary {
  id: string;
  subject_type: string;
  subject_id: string;
  content: string;
  summary_type?: string | null;
  source_record_ids?: string[] | null;
  source_tables?: string[] | null;
  model_version?: string | null;
  confidence?: number | null;
  status?: LifecycleStatus | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  created_by?: string | null;
}

export type ExportFormat = 'csv' | 'json' | 'xlsx' | 'pdf' | 'parquet';

export interface ExportLog {
  id: string;
  export_type: string;
  user_id?: string | null;
  target_table?: string | null;
  filters?: JSONObject | null;
  row_count?: number | null;
  file_size_bytes?: number | null;
  file_url?: string | null;
  status?: ExportStatus | null;
  created_at?: string | null;
  format?: ExportFormat | null;
  entity_type?: string | null;
  entity_ids?: string[] | null;
  file_path?: string | null;
  file_size?: number | null;
  requested_by?: string | null;
  error_message?: string | null;
  completed_at?: string | null;
}

export interface ListOptions {
  filter?: Record<string, any>;
  sort?: string[];
  fields?: string[];
  limit?: number;
  offset?: number;
  page?: number;
  meta?: 'total_count' | 'filter_count';
}

export interface WorkflowState {
  entity_type: string;
  entity_id: string;
  from_state: string;
  to_state: string;
  changed_by: string;
  notes?: string;
}

export interface NoiSnapshot {
  id: string;
  crop_cycle_id: string;
  location_id: string;
  period_start: string;
  period_end: string;
  gross_revenue?: number | null;
  returns_and_discounts?: number | null;
  net_revenue?: number | null;
  direct_crop_costs?: number | null;
  allocated_shared_costs?: number | null;
  total_costs?: number | null;
  noi?: number | null;
  operating_margin_pct?: number | null;
  loss_rate_pct?: number | null;
  calculation_version?: string | null;
  calculated_at?: string | null;
  inputs?: JSONObject | null;
  created_by?: string | null;
}
