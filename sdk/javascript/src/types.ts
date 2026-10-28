export type JSONScalar = string | number | boolean | null;
export type JSONValue = JSONScalar | JSONValue[] | { [key: string]: JSONValue };
export type JSONObject = { [key: string]: JSONValue };
export type LifecycleStatus = 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
export type EntityStatus = 'active' | 'inactive' | 'archived';
export type EntityStatusExtended = 'active' | 'inactive' | 'maintenance' | 'decommissioned';
export type PaymentStatus = 'pending' | 'partial' | 'paid' | 'overdue' | 'cancelled';
export type SensorSeverity = 'info' | 'warning' | 'critical';
export type SensorAnomalyEffectOutcome = 'no_match' | 'cooldown' | 'alert_created';
export type AlertLifecycle = 'open' | 'acknowledged' | 'resolved' | 'false_positive';
export type ExportStatus = 'pending' | 'generating' | 'completed' | 'failed';
export type OrganizationType = 'cooperative' | 'nonprofit' | 'dao' | 'enterprise' | 'collective' | 'other';
export type OrganizationStatus = 'active' | 'inactive' | 'dissolved';
export type OrganizationMembershipType = 'owned' | 'affiliated' | 'sponsored' | 'partner';
export type OrganizationMemberRole = 'primary' | 'satellite' | 'partner' | 'incubated';
export type OrganizationMemberStatus = 'active' | 'inactive' | 'suspended';
export type ActuatorType = 'irrigation' | 'pest_control' | 'fertilization' | 'notification' | 'custom';
export type ActuationLogStatus = 'pending' | 'requires_approval' | 'approved' | 'sent' | 'acknowledged' | 'executed' | 'failed' | 'cancelled';
export type ActuationStatus = 'pending' | 'sent' | 'acknowledged' | 'executed' | 'failed' | 'requires_approval';
export type AttestationVerdict = 'pending' | 'approved' | 'rejected' | 'needs_info';
export type TimeSeriesForecastModelType = 'arima' | 'exponential_smoothing' | 'prophet' | 'naive' | 'seasonal_naive';
export type TimeSeriesForecastStatus = 'active' | 'superseded' | 'expired';
export type VariogramModelType = 'spherical' | 'exponential' | 'gaussian' | 'matern';
export type KrigingMethod = 'ordinary' | 'simple' | 'indicator';
export type GeostatSimulationMethod = 'sgs' | 'sis' | 'turning_bands';
export type SpatialAutocorrelationMetric = 'morans_i' | 'gearys_c' | 'join_count';
export type SpatialWeightsType = 'queen' | 'rook' | 'distance' | 'knn';
export type GeostatCVStrategy = 'spatial_block' | 'leave_one_out' | 'k_fold';
export type CausalLoopType = 'reinforcing' | 'balancing' | 'archetype';
export type SystemsDomain = 'farm' | 'ecological' | 'financial' | 'social' | 'governance';
export type CausalLinkPolarity = '+' | '-';
export type SystemVariableType = 'stock' | 'flow' | 'auxiliary' | 'constant';
export type StockFlowRunStatus = 'pending' | 'running' | 'completed' | 'failed';
export type SystemArchetypeStatus = 'active' | 'resolved' | 'dismissed';
export type StructuralAssumptionStatus = 'active' | 'challenged' | 'validated' | 'deprecated';
export type SituationAssessmentType = 'full' | 'quick' | 'deep' | 'reassessment';
export type SituationGrade = 'critical' | 'warning' | 'stable' | 'flourishing';
export type SituationConfidence = 'high' | 'moderate' | 'low' | 'insufficient_evidence';
export type SituationAssessmentStatus = 'draft' | 'verified' | 'superseded';
export type AssessmentSignalType =
  | 'crisp_dimension'
  | 'metric_trend'
  | 'anomaly_cluster'
  | 'analytics_output'
  | 'external_event'
  | 'user_input';
export type AssessmentSignalDirection = 'positive' | 'negative' | 'neutral' | 'mixed';
export type AssessmentDimensionTrend = 'improving' | 'stable' | 'declining' | 'volatile';
export type OodaCycleType = 'automated' | 'manual' | 'hybrid' | 'simulated';
export type OodaCycleStatus = 'in_progress' | 'completed' | 'failed' | 'timeout' | 'abandoned';
export type OodaFailurePhase = 'observe' | 'orient' | 'decide' | 'act';
export type OodaOutcomeType =
  | 'effective'
  | 'partially_effective'
  | 'ineffective'
  | 'no_effect'
  | 'counterproductive'
  | 'unknown';
export type OrganicCertificationType = 'initial' | 'renewal' | 'extension';
export type OrganicCertificationStatus = 'planned' | 'preparing' | 'submitted' | 'inspected' | 'certified' | 'suspended' | 'revoked' | 'expired';
export type OrganicCertificationScope = 'full' | 'partial' | 'transitioning';
export type BufferOperationalStatus = 'active' | 'inactive' | 'maintenance_needed';
export type OrganicTransitionStatus = 'planned' | 'active' | 'paused' | 'completed' | 'failed';
export type ProhibitedSubstanceCategory = 'synthetic_pesticide' | 'synthetic_fertilizer' | 'gmo_seed' | 'sewage_sludge' | 'ionizing_radiation' | 'prohibited_additive' | 'other';
export type ProhibitedSubstanceComplianceStatus = 'cleared' | 'violation' | 'pending_remediation' | 'under_review';
export type BufferType = 'physical_fence' | 'vegetative_barrier' | 'uncultivated_strip' | 'water_barrier' | 'road' | 'hedgerow' | 'other';
export type BufferAdjacentUse = 'conventional_farm' | 'road' | 'industrial' | 'urban' | 'water_body' | 'wildland' | 'other';
export type BufferConditionStatus = 'adequate' | 'needs_repair' | 'non_compliant';
export type OrganicInputCategory = 'fertilizer' | 'pesticide' | 'fungicide' | 'herbicide' | 'seed_treatment' | 'soil_amendment' | 'mulch' | 'other';
export type OrganicInputSource = 'on_farm' | 'purchased' | 'traded';
export type HarvestHandlingType = 'cleaning' | 'sorting' | 'grading' | 'drying' | 'processing' | 'packaging' | 'storage' | 'transport';
export type HarvestContaminationRisk = 'low' | 'medium' | 'high';
export type OrganicInspectionType = 'initial' | 'renewal' | 'follow_up' | 'unannounced';
export type OrganicChecklistResult = 'pass' | 'conditional' | 'fail' | 'pending';
export type CrispRating = 'AAA' | 'AA' | 'A' | 'B' | 'C' | 'D';
export type CrispConfidenceLevel = 'high' | 'moderate' | 'low' | 'insufficient_evidence';
export type CrispSSPScenario = 'SSP1' | 'SSP2' | 'SSP5';
export type DemandForecastType = 'time_series' | 'buyer_pipeline' | 'seasonal_decomposition' | 'hybrid';
export type DemandForecastStatus = 'draft' | 'submitted' | 'verified' | 'published';
export type MarketScope = 'local' | 'regional' | 'national' | 'international';
export type PriceAggregationMethod = 'single' | 'median_consensus' | 'weighted_average' | 'on_chain_attested';
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
export type TrophicLevel =
  | 'producer'
  | 'primary_consumer'
  | 'secondary_consumer'
  | 'decomposer'
  | 'omnivore';
export type ConservationStatus =
  | 'critically_endangered'
  | 'endangered'
  | 'vulnerable'
  | 'near_threatened'
  | 'least_concern'
  | 'data_deficient'
  | 'not_evaluated';
export type FarmTaskCategory =
  | 'planting'
  | 'weeding'
  | 'irrigation'
  | 'spraying'
  | 'harvesting'
  | 'maintenance'
  | 'training'
  | 'reporting'
  | 'other';
export type FarmTaskPriority = 'low' | 'medium' | 'high' | 'critical';
export type FarmTaskStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';
export type CarbonCreditStatus = 'draft' | 'submitted' | 'verified' | 'published' | 'retired' | 'revoked' | 'rejected';
export type CreditAdjustmentStatus = 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
export type CreditAdjustmentType = 'measurement_update' | 'methodology_change' | 'reversal' | 'correction';
export type CreditAdjustmentTriggerSource =
  | 'tree_inventory'
  | 'soil_carbon_measurement'
  | 'ghg_emissions_inventory'
  | 'climate_impact_summary'
  | 'remote_sensing'
  | 'manual_override';
export type CreditRetirementStatus = 'draft' | 'submitted' | 'verified' | 'published' | 'rejected' | 'cancelled';
export type CreditTransferStatus = 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
export type CreditTransferType = 'allocation' | 'sale' | 'grant' | 'internal_rebalance';

export type GeoJSONPosition = [longitude: number, latitude: number, altitude?: number];

export interface GeoJSONPoint {
  type: 'Point';
  coordinates: GeoJSONPosition;
}

export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: GeoJSONPosition[][];
}

/** Preserved source option metadata; it does not select the canonical activity type. */
export interface ActivityTypeSourceOption {
  option_id: number;
  label: string;
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

/** Stored farm infrastructure inventory; this record does not assess condition. */
export interface InfrastructureAsset {
  id: string;
  location_id: string;
  name: string;
  asset_type: string;
  plot_id?: string | null;
  description?: string | null;
  install_date?: string | null;
  capacity?: number | null;
  capacity_unit?: string | null;
  condition_status?: string | null;
  last_inspection_date?: string | null;
  replacement_cost?: number | null;
  metadata?: JSONObject | null;
  status?: EntityStatusExtended | null;
  created_at?: string | null;
  updated_at?: string | null;
  schema_version?: string | null;
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

/** Stored crop reference; this record does not estimate or verify yields. */
export interface Crop {
  id: string;
  name: string;
  scientific_name?: string | null;
  variety?: string | null;
  crop_category?: string | null;
  growing_season_days?: number | null;
  expected_yield_per_ha?: number | null;
  expected_yield_unit?: string | null;
  water_needs?: string | null;
  climate_zone?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
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

/** Stored farm operation record; this model does not advance its review lifecycle. */
export interface FarmActivity {
  id: string;
  location_id: string;
  activity_type: string;
  activity_date: string;
  plot_id?: string | null;
  crop_cycle_id?: string | null;
  description?: string | null;
  labor_hours?: number | null;
  labor_cost?: number | null;
  materials_used?: JSONValue | null;
  evidence_urls?: string[] | null;
  evidence_hashes?: string[] | null;
  notes?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  rejection_reason?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  submitted_at?: string | null;
  farm_id?: string | null;
  farm_task_id?: string | null;
  duration_minutes?: number | null;
  activity_end_date?: string | null;
  activity_type_source_options?: ActivityTypeSourceOption[] | null;
}

/** Stored farm-task plan; this record does not assign or complete work. */
export interface FarmTask {
  id: string;
  location_id: string;
  task_name: string;
  category: FarmTaskCategory;
  priority: FarmTaskPriority;
  status: FarmTaskStatus;
  farm_id?: string | null;
  plot_id?: string | null;
  crop_cycle_id?: string | null;
  assignee_id?: string | null;
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number | null;
  estimated_cost_usd?: number | null;
  actual_cost_usd?: number | null;
  notes?: string | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Directed prerequisite edge; this record does not evaluate task readiness. */
export interface FarmTaskDependency {
  task_id: string;
  prerequisite_task_id: string;
  source_system?: string | null;
  source_database_id?: number | null;
  source_table_id?: number | null;
  source_field_id?: number | null;
  source_row_id?: number | null;
  source_related_table_id?: number | null;
  source_related_row_id?: number | null;
  created_at?: string | null;
}

/** Task-to-framework-step association record. */
export interface FarmTaskFrameworkStep {
  task_id: string;
  framework_step_id: string;
  source_system?: string | null;
  source_database_id?: number | null;
  source_table_id?: number | null;
  source_field_id?: number | null;
  source_row_id?: number | null;
  source_related_table_id?: number | null;
  source_related_row_id?: number | null;
  created_at?: string | null;
}

/** Task-to-weekly-plan association record. */
export interface FarmTaskWeeklyPlan {
  task_id: string;
  weekly_plan_id: string;
  source_system?: string | null;
  source_database_id?: number | null;
  source_table_id?: number | null;
  source_field_id?: number | null;
  source_row_id?: number | null;
  source_related_table_id?: number | null;
  source_related_row_id?: number | null;
  created_at?: string | null;
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

/** Stored weather observation; this record does not fetch or validate provider data. */
export interface WeatherObservation {
  id: string;
  location_id: string;
  observation_date: string;
  observation_time?: string | null;
  source?: string | null;
  temperature_c?: number | null;
  temp_min_c?: number | null;
  temp_max_c?: number | null;
  precipitation_mm?: number | null;
  rainfall_mm?: number | null;
  humidity_pct?: number | null;
  wind_speed_kmh?: number | null;
  wind_direction_deg?: number | null;
  solar_radiation_wm2?: number | null;
  sunshine_hours?: number | null;
  cloud_cover_pct?: number | null;
  pressure_hpa?: number | null;
  visibility_km?: number | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  schema_version?: string | null;
  created_at?: string | null;
}

/** Stored soil laboratory/field sample; it does not validate the recorded results. */
export interface SoilSample {
  id: string;
  plot_id: string;
  location_id: string;
  sample_date: string;
  sample_id?: string | null;
  depth_cm?: number | null;
  depth_layer?: string | null;
  ph?: number | null;
  organic_matter_pct?: number | null;
  organic_carbon_pct?: number | null;
  nitrogen_ppm?: number | null;
  phosphorus_ppm?: number | null;
  potassium_ppm?: number | null;
  calcium_ppm?: number | null;
  magnesium_ppm?: number | null;
  sulfur_ppm?: number | null;
  cec?: number | null;
  texture?: string | null;
  moisture_pct?: number | null;
  lab_name?: string | null;
  lab_report_url?: string | null;
  evidence_hash?: string | null;
  notes?: string | null;
  created_at?: string | null;
  created_by?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  schema_version?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  evidence_maturity?: number | null;
  lab_accredited?: boolean | null;
  analytical_method?: string | null;
  protocol_id?: string | null;
  composite_count?: number | null;
  sub_sample_count?: number | null;
  gps_latitude?: number | null;
  gps_longitude?: number | null;
  collector_name?: string | null;
  collector_id?: string | null;
  chain_of_custody?: string | null;
  container_type?: string | null;
  preservative?: string | null;
  sample_mass_g?: number | null;
  moisture_conditions?: string | null;
  point_geometry?: GeoJSONPoint | null;
}

/** Stored soil-carbon measurement; it is not calculated or verified here. */
export interface SoilCarbonMeasurement {
  id: string;
  plot_id: string;
  location_id: string;
  measurement_date: string;
  carbon_pct?: number | null;
  carbon_tonnes_per_ha?: number | null;
  organic_carbon_stock?: number | null;
  measurement_method?: string | null;
  depth_cm?: number | null;
  is_baseline?: boolean | null;
  baseline_id?: string | null;
  evidence_urls?: string[] | null;
  evidence_hash?: string | null;
  notes?: string | null;
  created_at?: string | null;
  created_by?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  schema_version?: string | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  evidence_maturity?: number | null;
  lab_accredited?: boolean | null;
  analytical_method?: string | null;
  protocol_id?: string | null;
}

/** Stored environmental baseline; this record does not calculate the reference value. */
export interface EnvironmentalBaseline {
  id: string;
  location_id: string;
  metric_name: string;
  plot_id?: string | null;
  baseline_value?: number | null;
  unit?: string | null;
  measurement_date?: string | null;
  measurement_method?: string | null;
  source?: string | null;
  evidence_urls?: string[] | null;
  notes?: string | null;
  created_at?: string | null;
  created_by?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  schema_version?: string | null;
}

/** Stored biodiversity observation; it does not verify species claims. */
export interface SpeciesObservation {
  id: string;
  location_id: string;
  observation_date: string;
  plot_id?: string | null;
  species_name?: string | null;
  species_common_name?: string | null;
  species_category?: string | null;
  taxonomic_family?: string | null;
  count?: number | null;
  abundance?: string | null;
  observer?: string | null;
  observer_id?: string | null;
  method?: string | null;
  habitat_type?: string | null;
  evidence_urls?: string[] | null;
  evidence_hashes?: string[] | null;
  notes?: string | null;
  created_at?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  schema_version?: string | null;
  trophic_level?: TrophicLevel | null;
  population_density_per_m2?: number | null;
  conservation_status?: ConservationStatus | null;
  status?: LifecycleStatus | null;
  verified_by?: string | null;
  verified_at?: string | null;
  evidence_maturity?: number | null;
}

/** Stored satellite/drone observation; it does not fetch imagery or compute indices. */
export interface RemoteSensingObservation {
  id: string;
  location_id: string;
  observation_date: string;
  plot_id?: string | null;
  source?: string | null;
  ndvi?: number | null;
  ndre?: number | null;
  evi?: number | null;
  savi?: number | null;
  canopy_cover_pct?: number | null;
  canopy_height_m?: number | null;
  ndwi?: number | null;
  bbox?: GeoJSONPolygon | null;
  centroid?: GeoJSONPoint | null;
  cloud_cover_pct?: number | null;
  image_url?: string | null;
  thumbnail_url?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  schema_version?: string | null;
  msavi?: number | null;
  satvi?: number | null;
  bsi?: number | null;
  nbr2?: number | null;
  ndti?: number | null;
  lswi?: number | null;
  brightness_index?: number | null;
  tc_brightness?: number | null;
  tc_greenness?: number | null;
  tc_wetness?: number | null;
  band_blue?: number | null;
  band_green?: number | null;
  band_red?: number | null;
  band_nir?: number | null;
  band_swir1?: number | null;
  band_swir2?: number | null;
}

/** Stored MRV claim and evidence links; it does not verify or attest the claim. */
export interface MrvClaim {
  id: string;
  location_id: string;
  claim_type: string;
  claim_date: string;
  claim_data: JSONObject;
  created_at?: string | null;
  plot_id?: string | null;
  source_record_ids?: string[] | null;
  evidence_urls?: string[] | null;
  evidence_hashes?: string[] | null;
  status?: LifecycleStatus | null;
  reviewer_id?: string | null;
  review_notes?: string | null;
  reviewed_at?: string | null;
  attestation_uid?: string | null;
  attested_at?: string | null;
  schema_version?: string | null;
  created_by?: string | null;
  sensor_device_id?: string | null;
  sensor_alert_id?: string | null;
  source_readings?: string[] | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  evidence_maturity?: number | null;
  external_verifier?: string | null;
  methodology_ref?: string | null;
  public_claim?: boolean | null;
  source_sensor_reading_event_id?: string | null;
}

/** Stored human verification review; recording it does not transition the claim. */
export interface VerificationReview {
  id: string;
  claim_id: string;
  reviewer_id: string;
  review_date: string;
  result: string;
  method?: string | null;
  notes?: string | null;
  evidence_urls?: string[] | null;
  created_at?: string | null;
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

/** Stored dashboard dataset definition. Refresh uses the registered query ID. */
export interface DashboardDataset {
  id: string;
  name: string;
  description?: string | null;
  dataset_type?: string | null;
  location_id?: string | null;
  query_id?: string | null;
  /** @deprecated Older Directus servers may return this archived field; current hooks redact it and the Kernel never executes it. */
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

/** Stored fitted variogram parameters; this record does not fit a model. */
export interface VariogramModel {
  id: string;
  location_id?: string | null;
  property_key: string;
  model_type: VariogramModelType;
  sill: number;
  range: number;
  nugget: number;
  partial_sill?: number | null;
  lag_distance?: number | null;
  lag_tolerance?: number | null;
  bandwidth?: number | null;
  n_pairs?: number | null;
  r_squared?: number | null;
  fitted_at: string;
  metadata?: JSONObject | null;
  created_at: string;
}

/** Stored kriging run metadata; this record does not interpolate points. */
export interface KrigingPrediction {
  id: string;
  location_id?: string | null;
  variogram_model_id: string;
  property_key: string;
  grid_resolution_m?: number | null;
  n_points: number;
  method: KrigingMethod;
  threshold_value?: number | null;
  created_at: string;
  metadata?: JSONObject | null;
}

/** Stored prediction point; this record does not calculate interpolation. */
export interface KrigingPoint {
  id: string;
  prediction_id: string;
  point_geometry: GeoJSONPoint;
  predicted_value: number;
  prediction_variance?: number | null;
  prediction_std?: number | null;
  search_radius_m?: number | null;
  n_neighbors?: number | null;
  weight_sum?: number | null;
}

/** Stored simulation metadata; this record does not generate realizations. */
export interface GeostatRealization {
  id: string;
  location_id?: string | null;
  variogram_model_id: string;
  property_key: string;
  realization_number: number;
  grid_resolution_m?: number | null;
  n_points: number;
  method: GeostatSimulationMethod;
  seed?: number | null;
  created_at: string;
  metadata?: JSONObject | null;
}

/** Stored simulation point; this record does not generate realizations. */
export interface GeostatRealizationPoint {
  id: string;
  realization_id: string;
  point_geometry: GeoJSONPoint;
  simulated_value: number;
}

/** Stored spatial autocorrelation result; this record does not analyze data. */
export interface SpatialAutocorrelation {
  id: string;
  location_id?: string | null;
  property_key: string;
  metric: SpatialAutocorrelationMetric;
  statistic_value: number;
  expected_value?: number | null;
  p_value?: number | null;
  z_score?: number | null;
  n_samples: number;
  spatial_weights_type?: SpatialWeightsType | null;
  distance_threshold?: number | null;
  k_neighbors?: number | null;
  interpretation?: string | null;
  computed_at: string;
  metadata?: JSONObject | null;
  created_at: string;
}

/** Stored spatial validation metrics; this record does not validate. */
export interface GeostatCVResult {
  id: string;
  location_id?: string | null;
  property_key: string;
  variogram_model_id?: string | null;
  cv_strategy: GeostatCVStrategy;
  n_folds: number;
  block_size_m?: number | null;
  mean_error?: number | null;
  mean_squared_error?: number | null;
  root_mean_squared_error?: number | null;
  mean_absolute_error?: number | null;
  r_squared?: number | null;
  fold_results?: JSONObject[] | null;
  soc_model_id?: string | null;
  computed_at: string;
  metadata?: JSONObject | null;
  created_at: string;
}

/** Stored sensor spacing recommendation; this record does not optimize design. */
export interface SensorNetworkDesign {
  id: string;
  location_id?: string | null;
  property_key: string;
  variogram_model_id?: string | null;
  optimal_spacing_m?: number | null;
  coverage_radius_m?: number | null;
  recommended_n_sensors?: number | null;
  current_n_sensors?: number | null;
  coverage_gap_pct?: number | null;
  confidence_level?: number | null;
  notes?: string | null;
  computed_at: string;
  metadata?: JSONObject | null;
  created_at: string;
}

/** Shared causal-loop definition; this record does not evaluate a loop. */
export interface CausalLoop {
  id: string;
  loop_name: string;
  loop_type: CausalLoopType;
  archetype?: string | null;
  description: string;
  domain: SystemsDomain;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** Stored causal relationship scoped to its parent loop. */
export interface CausalLink {
  id: string;
  loop_id: string;
  source_variable: string;
  target_variable: string;
  polarity: CausalLinkPolarity;
  strength: number;
  description?: string | null;
  delay_hours?: number | null;
  data_source?: string | null;
  created_at: string;
}

/** Stored system variable and latest observation; no value is recalculated. */
export interface SystemVariable {
  id: string;
  variable_name: string;
  variable_type: SystemVariableType;
  unit?: string | null;
  current_value?: number | null;
  min_value?: number | null;
  max_value?: number | null;
  location_id?: string | null;
  source_table?: string | null;
  source_column?: string | null;
  last_observed_at?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

/** Shared stock-and-flow model definition; this record does not simulate. */
export interface StockFlowModel {
  id: string;
  model_name: string;
  description: string;
  equations: JSONObject;
  initial_conditions: JSONObject;
  parameters: JSONObject;
  time_unit: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** Persisted simulation result; the SDK does not execute the model. */
export interface StockFlowRun {
  id: string;
  model_id: string;
  location_id: string;
  scenario_name: string;
  parameters: JSONObject;
  start_date: string;
  end_date: string;
  time_step_days: number;
  results: JSONObject;
  trajectory: JSONValue[];
  status: StockFlowRunStatus;
  error_message?: string | null;
  run_at: string;
  run_by: string;
}

/** Stored location-level archetype detection and evidence. */
export interface SystemArchetype {
  id: string;
  archetype_name: string;
  location_id: string;
  detected_at: string;
  confidence: number;
  evidence: JSONObject;
  active_variables: JSONValue[];
  suggested_intervention?: string | null;
  status: SystemArchetypeStatus;
  resolved_at?: string | null;
  metadata?: JSONObject | null;
  created_at: string;
}

/** Stored leverage-point assessment; suggestions remain advisory. */
export interface LeverageAssessment {
  id: string;
  location_id: string;
  leverage_point: number;
  point_name: string;
  current_state?: string | null;
  impact_score: number;
  intervention_suggestion?: string | null;
  data_sources: JSONValue[];
  assessed_at: string;
  assessed_by: string;
  metadata?: JSONObject | null;
  created_at: string;
}

/** Shared action-to-effect delay configuration; no delay is inferred. */
export interface TimeDelay {
  id: string;
  action_type: string;
  effect_type: string;
  expected_delay_hours: number;
  min_delay_hours?: number | null;
  max_delay_hours?: number | null;
  domain: string;
  description?: string | null;
  is_enabled: boolean;
  created_at: string;
}

/** Stored location assumption and challenge history. */
export interface StructuralAssumption {
  id: string;
  assumption_text: string;
  location_id?: string | null;
  domain: string;
  status: StructuralAssumptionStatus;
  challenge_evidence?: string | null;
  challenged_at?: string | null;
  challenged_by?: string | null;
  original_source?: string | null;
  created_at: string;
  updated_at: string;
}

/** Stored advisory situation assessment and evidence summaries. */
export interface SituationAssessment {
  id: string;
  location_id: string;
  assessment_type: SituationAssessmentType;
  situation_grade: SituationGrade;
  composite_score: number;
  confidence_level: SituationConfidence;
  evidence_maturity: number;
  crisp_rating?: string | null;
  crisp_composite_score?: number | null;
  anomaly_count: number;
  critical_anomaly_count: number;
  metric_trend_summary: JSONObject;
  dimension_summaries: JSONObject;
  recommendations: JSONValue[];
  period_start: string;
  period_end: string;
  assessed_at: string;
  assessed_by: string;
  methodology_version: string;
  status: SituationAssessmentStatus;
  metadata?: JSONObject | null;
  created_at: string;
  updated_at: string;
}

/** Stored signal that contributes to a situation assessment. */
export interface AssessmentSignal {
  id: string;
  assessment_id: string;
  signal_type: AssessmentSignalType;
  signal_key: string;
  signal_value?: number | null;
  signal_text?: string | null;
  signal_direction: AssessmentSignalDirection;
  weight: number;
  source_table?: string | null;
  source_id?: string | null;
  created_at: string;
}

/** Stored assessment dimension score, trend, and evidence summary. */
export interface AssessmentDimension {
  id: string;
  assessment_id: string;
  dimension_key: string;
  dimension_name: string;
  risk_score: number;
  trend: AssessmentDimensionTrend;
  trend_delta?: number | null;
  signal_count: number;
  confidence_level: SituationConfidence;
  evidence_summary?: string | null;
  created_at: string;
}

/** Persisted OODA phase timing and outcome metadata; no action is executed. */
export interface OodaCycleLog {
  id: string;
  correlation_id: string;
  location_id: string;
  cycle_type: OodaCycleType;
  decision_type: string;
  trigger_event_type?: string | null;
  trigger_event_id?: string | null;
  observe_started_at?: string | null;
  observe_completed_at?: string | null;
  observe_duration_ms?: number | null;
  observe_sources: JSONValue[];
  orient_started_at?: string | null;
  orient_completed_at?: string | null;
  orient_duration_ms?: number | null;
  orient_frameworks_used: JSONValue[];
  orient_assessment_id?: string | null;
  decide_started_at?: string | null;
  decide_completed_at?: string | null;
  decide_duration_ms?: number | null;
  decide_policy_id?: string | null;
  decide_decision_id?: string | null;
  act_started_at?: string | null;
  act_completed_at?: string | null;
  act_duration_ms?: number | null;
  act_outcome_id?: string | null;
  act_action_type?: string | null;
  total_cycle_time_ms?: number | null;
  status: OodaCycleStatus;
  failure_phase?: OodaFailurePhase | null;
  error_message?: string | null;
  outcome_type?: OodaOutcomeType | null;
  metadata?: JSONObject | null;
  created_at: string;
  updated_at: string;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface OrganicCertificationRecord {
  id: string;
  location_id: string;
  standard: string;
  certification_type: OrganicCertificationType;
  status: OrganicCertificationStatus;
  created_at: string;
  updated_at: string;
  certification_body?: string | null;
  application_date?: string | null;
  inspection_date?: string | null;
  certification_date?: string | null;
  expiration_date?: string | null;
  certificate_number?: string | null;
  certificate_url?: string | null;
  scope?: OrganicCertificationScope | null;
  scope_areas?: JSONValue[] | null;
  annual_fee_usd?: number | null;
  notes?: string | null;
  evidence_urls?: JSONValue[] | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface OrganicTransitionPlan {
  id: string;
  location_id: string;
  standard: string;
  transition_start_date: string;
  current_year: number;
  total_years_required: number;
  status: OrganicTransitionStatus;
  created_at: string;
  updated_at: string;
  plot_id?: string | null;
  expected_certification_date?: string | null;
  prohibited_substance_free_date?: string | null;
  buffer_zone_established_date?: string | null;
  record_keeping_ready_date?: string | null;
  training_completed_date?: string | null;
  organic_management_plan_date?: string | null;
  readiness_score?: number | null;
  barriers?: JSONValue[] | null;
  notes?: string | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface ProhibitedSubstanceRecord {
  id: string;
  location_id: string;
  substance_name: string;
  substance_category: ProhibitedSubstanceCategory;
  date_used: string;
  compliance_status: ProhibitedSubstanceComplianceStatus;
  created_at: string;
  updated_at: string;
  plot_id?: string | null;
  cas_number?: string | null;
  quantity?: number | null;
  unit?: string | null;
  reason_for_use?: string | null;
  remediation_action?: string | null;
  remediation_date?: string | null;
  withdrawal_period_days?: number | null;
  withdrawal_end_date?: string | null;
  notes?: string | null;
  evidence_urls?: JSONValue[] | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface BufferZone {
  id: string;
  location_id: string;
  buffer_name: string;
  buffer_type: BufferType;
  width_m: number;
  condition_status: BufferConditionStatus;
  status?: BufferOperationalStatus | null;
  created_at: string;
  updated_at: string;
  plot_id?: string | null;
  length_m?: number | null;
  area_m2?: number | null;
  adjacent_use?: BufferAdjacentUse | null;
  boundary_geometry?: JSONValue | null;
  establishment_date?: string | null;
  last_inspection_date?: string | null;
  photos_urls?: JSONValue[] | null;
  notes?: string | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface OrganicInputAudit {
  id: string;
  location_id: string;
  application_date: string;
  input_category: OrganicInputCategory;
  input_name: string;
  input_source: OrganicInputSource;
  organic_certified: boolean;
  quantity: number;
  unit: string;
  is_prohibited: boolean;
  created_at: string;
  updated_at: string;
  plot_id?: string | null;
  crop_cycle_id?: string | null;
  supplier_name?: string | null;
  supplier_organic_cert_url?: string | null;
  application_method?: string | null;
  target_pest_or_nutrient?: string | null;
  pre_harvest_interval_days?: number | null;
  reentry_interval_hours?: number | null;
  prohibition_standard?: string | null;
  notes?: string | null;
  evidence_urls?: JSONValue[] | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface HarvestHandlingRecord {
  id: string;
  location_id: string;
  harvest_event_id: string;
  handling_date: string;
  handling_type: HarvestHandlingType;
  organic_segregated: boolean;
  equipment_cleaned: boolean;
  contamination_risk: HarvestContaminationRisk;
  temperature_controlled: boolean;
  buyer_requirements_met: boolean;
  created_at: string;
  updated_at: string;
  storage_conditions?: string | null;
  transport_conditions?: string | null;
  organic_lot_number?: string | null;
  notes?: string | null;
  evidence_urls?: JSONValue[] | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface OrganicComplianceChecklist {
  id: string;
  location_id: string;
  inspection_date: string;
  inspection_type: OrganicInspectionType;
  checklist_items: JSONValue[];
  overall_result: OrganicChecklistResult;
  created_at: string;
  updated_at: string;
  certification_record_id?: string | null;
  inspector_name?: string | null;
  inspector_organization?: string | null;
  findings?: string | null;
  non_conformances?: JSONValue[] | null;
  corrective_actions_required?: JSONValue[] | null;
  follow_up_date?: string | null;
  notes?: string | null;
  evidence_urls?: JSONValue[] | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Stored organic compliance record; read access does not compute or mutate it. */
export interface OrganicReadinessAssessment {
  id: string;
  location_id: string;
  assessment_date: string;
  standard: string;
  overall_score: number;
  created_at: string;
  updated_at: string;
  transition_progress_pct?: number | null;
  soil_health_score?: number | null;
  input_compliance_pct?: number | null;
  pest_management_score?: number | null;
  biodiversity_score?: number | null;
  buffer_zone_score?: number | null;
  record_completeness_pct?: number | null;
  training_completion_pct?: number | null;
  harvest_segregation_score?: number | null;
  barriers?: JSONValue[] | null;
  recommendations?: JSONValue[] | null;
  assessor?: string | null;
  notes?: string | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Persisted CRISP assessment; reading it does not recompute its scores. */
export interface CrispRiskAssessment {
  id: string;
  location_id: string;
  period_start: string;
  period_end: string;
  methodology_version: string;
  created_at?: string | null;
  updated_at?: string | null;
  farm_id?: string | null;
  carbon_yield_score?: number | null;
  climate_score?: number | null;
  policy_score?: number | null;
  financial_score?: number | null;
  implementation_score?: number | null;
  composite_score?: number | null;
  rating?: CrispRating | null;
  confidence_level?: CrispConfidenceLevel | null;
  score_computed_at?: string | null;
  evidence_maturity_level?: number | null;
  status?: LifecycleStatus | null;
  reviewer_notes?: string | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_by?: string | null;
  updated_by?: string | null;
}

/** Persisted CRISP carbon-yield dimension detail. */
export interface CrispCarbonYieldRisk {
  id: string;
  assessment_id: string;
  location_id: string;
  created_at?: string | null;
  updated_at?: string | null;
  tree_inventory_snapshot?: JSONObject | null;
  soil_carbon_snapshot?: JSONObject | null;
  harvest_snapshot?: JSONObject | null;
  allometric_source?: string | null;
  growth_model_reference?: string | null;
  planting_density_per_ha?: number | null;
  mortality_rate_pct?: number | null;
  ndvi_pre_project?: number | null;
  scenario_minimum?: number | null;
  scenario_realistic?: number | null;
  scenario_optimistic?: number | null;
  ex_ante_estimate?: number | null;
  yield_unit?: string | null;
  yield_likelihood?: number | null;
  risk_score?: number | null;
  uncertainty_pct?: number | null;
  carbon_pool_breakdown?: JSONObject | null;
  evidence_maturity_level?: number | null;
  metadata?: JSONObject | null;
}

/** Persisted CRISP climate dimension detail. */
export interface CrispClimateRisk {
  id: string;
  assessment_id: string;
  location_id: string;
  created_at?: string | null;
  updated_at?: string | null;
  drought_risk_score?: number | null;
  flood_risk_score?: number | null;
  heatwave_risk_score?: number | null;
  fire_risk_score?: number | null;
  storm_risk_score?: number | null;
  water_stress_score?: number | null;
  natural_risk_rating?: number | null;
  mitigation_factor?: number | null;
  climate_catastrophe_factor?: number | null;
  ssp_scenario?: CrispSSPScenario | null;
  risk_score?: number | null;
  historical_events?: JSONValue[] | null;
  climate_projections_source?: string | null;
  evidence_maturity_level?: number | null;
  metadata?: JSONObject | null;
}

/** Persisted CRISP policy and legal dimension detail. */
export interface CrispPolicyRisk {
  id: string;
  assessment_id: string;
  location_id: string;
  created_at?: string | null;
  updated_at?: string | null;
  national_policy_score?: number | null;
  article_6_score?: number | null;
  carbon_rights_score?: number | null;
  land_tenure_score?: number | null;
  community_alignment_score?: number | null;
  certification_risk_score?: number | null;
  risk_score?: number | null;
  policy_indicators?: JSONObject | null;
  evidence_maturity_level?: number | null;
  metadata?: JSONObject | null;
}

/** Persisted CRISP financial viability dimension detail. */
export interface CrispFinancialRisk {
  id: string;
  assessment_id: string;
  location_id: string;
  created_at?: string | null;
  updated_at?: string | null;
  break_even_year?: number | null;
  revenue_risk_factor?: number | null;
  cost_risk_factor?: number | null;
  market_price_risk?: number | null;
  liquidity_risk?: number | null;
  vintage_year?: number | null;
  financial_risk_factor?: number | null;
  risk_score?: number | null;
  financial_snapshot?: JSONObject | null;
  evidence_maturity_level?: number | null;
  metadata?: JSONObject | null;
}

/** Persisted CRISP implementation dimension detail. */
export interface CrispImplementationRisk {
  id: string;
  assessment_id: string;
  location_id: string;
  created_at?: string | null;
  updated_at?: string | null;
  track_record_score?: number | null;
  team_strength_score?: number | null;
  network_strength_score?: number | null;
  community_alignment_score?: number | null;
  transparency_score?: number | null;
  risk_score?: number | null;
  implementation_evidence?: JSONObject | null;
  evidence_maturity_level?: number | null;
  metadata?: JSONObject | null;
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

/** Stored market price and oracle consensus; it does not fetch or attest prices. */
export interface PriceObservation {
  id: string;
  price_date: string;
  crop_id?: string | null;
  commodity_code?: string | null;
  market_name?: string | null;
  price_per_unit?: number | null;
  unit?: string | null;
  currency?: string | null;
  source?: string | null;
  source_url?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  confidence?: number | null;
  deviation_pct?: number | null;
  source_count?: number | null;
  aggregation_method?: PriceAggregationMethod | null;
  source_metadata?: JSONObject | null;
  market_id?: string | null;
  location_id?: string | null;
  buyer_type?: string | null;
  quality_grade?: string | null;
  quantity_traded?: number | null;
  bid_price?: number | null;
  ask_price?: number | null;
  verified?: boolean | null;
  verified_by?: string | null;
  verified_at?: string | null;
  updated_at?: string | null;
}

/** Stored oracle feed and attestation reference; it does not submit attestations. */
export interface OraclePriceLog {
  id: string;
  commodity: string;
  price: number;
  price_timestamp: string;
  source: string;
  currency?: string | null;
  source_count?: number | null;
  confidence?: number | null;
  deviation_pct?: number | null;
  aggregation_method?: PriceAggregationMethod | null;
  attestation_uid?: string | null;
  attested_at?: string | null;
  chain?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
}

/** Stored actuation intent and result; it cannot approve, send, or execute commands. */
export interface ActuationLog {
  id: string;
  actuator_type: ActuatorType;
  actuator_command: string;
  command_payload: JSONObject;
  trigger_source: string;
  location_id?: string | null;
  sensor_alert_id?: string | null;
  actuator_topic?: string | null;
  trigger_alert_severity?: string | null;
  human_approval_required?: boolean | null;
  approved_by?: string | null;
  approved_at?: string | null;
  sent_at?: string | null;
  response_received_at?: string | null;
  response_payload?: JSONObject | null;
  status?: ActuationLogStatus | null;
  error_message?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  source_alert_event_id?: string | null;
}

/** Durable per-reading/rule processing receipt; it does not run anomaly detection. */
export interface SensorAnomalyEffect {
  source_reading_id: string;
  alert_rule_id: string;
  source_event_id: string;
  outcome: SensorAnomalyEffectOutcome;
  created_at: string;
  updated_at: string;
  sensor_alert_id?: string | null;
  location_id?: string | null;
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
  location_id?: string | null;
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

/** Stored Web3 protocol catalog entry; this record does not submit transactions. */
export interface Protocol {
  id: string;
  name: string;
  slug: string;
  chain: string;
  contract_address?: string | null;
  protocol_type?: string | null;
  category?: string | null;
  website?: string | null;
  description?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
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

/** Stored EAS schema catalog entry; it does not create or submit attestations. */
export interface AttestationSchema {
  id: string;
  schema_uid: string;
  name: string;
  chain: string;
  description?: string | null;
  schema_text?: string | null;
  resolver_address?: string | null;
  version?: number | null;
  active?: boolean | null;
  created_at?: string | null;
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
  created_by_worker_id?: string | null;
}

export interface ExportLog {
  id: string;
  user_id?: string | null;
  export_type: string;
  target_table?: string | null;
  filters?: JSONObject | null;
  row_count?: number | null;
  file_size_bytes?: number | null;
  file_url?: string | null;
  status?: ExportStatus | null;
  created_at?: string | null;
}

export interface ListOptions {
  [queryParameter: string]: unknown;
  /** Additional backend query parameters; standard list options take precedence. */
  extraParams?: Record<string, unknown>;
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

/** Stored cash-flow summary; this record does not calculate or reconcile balances. */
export interface CashFlowSnapshot {
  id: string;
  location_id: string;
  period_start: string;
  period_end: string;
  total_revenue?: number | null;
  capital_inflows?: number | null;
  grants_received?: number | null;
  total_inflows?: number | null;
  total_operating_expenses?: number | null;
  total_capex?: number | null;
  loan_repayments?: number | null;
  public_goods_allocation?: number | null;
  total_outflows?: number | null;
  net_cash_flow?: number | null;
  running_balance?: number | null;
  calculation_version?: string | null;
  calculated_at?: string | null;
  inputs?: JSONObject | null;
  created_by?: string | null;
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

/** Read model for a governed credit; lifecycle actions use reviewed services. */
export interface CarbonCredit {
  id: string;
  location_id: string;
  credit_code: string;
  vintage_year: number;
  methodology: string;
  initial_sequestration_tonnes: number;
  current_sequestration_tonnes: number;
  issuable_tonnes: number;
  farm_id?: string | null;
  methodology_version?: string | null;
  adjustment_margin_pct?: number | null;
  buffer_pool_pct?: number | null;
  retired_tonnes?: number | null;
  available_tonnes?: number | null;
  price_per_tonne_usd?: number | null;
  market_price_per_tonne_usd?: number | null;
  effective_price_per_tonne_usd?: number | null;
  total_value_usd?: number | null;
  climate_impact_summary_id?: string | null;
  evidence_maturity?: number | null;
  external_verifier?: string | null;
  methodology_ref?: string | null;
  attestation_uid?: string | null;
  attestation_schema_id?: string | null;
  attested_at?: string | null;
  token_chain?: string | null;
  token_contract?: string | null;
  token_id?: string | null;
  token_minted_at?: string | null;
  status?: CarbonCreditStatus | null;
  reviewer_id?: string | null;
  review_date?: string | null;
  review_notes?: string | null;
  metadata?: JSONObject | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: JSONObject | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  credit_class_id?: string | null;
  credit_batch_id?: string | null;
  expires_at?: string | null;
  reserved_tonnes?: number | null;
}

/** Append-oriented credit adjustment review record. */
export interface CreditAdjustment {
  id: string;
  credit_id: string;
  location_id: string;
  adjustment_type: CreditAdjustmentType;
  previous_sequestration_tonnes: number;
  new_sequestration_tonnes: number;
  delta_tonnes: number;
  delta_pct: number;
  trigger_source: CreditAdjustmentTriggerSource;
  within_margin: boolean;
  requires_review: boolean;
  trigger_record_id?: string | null;
  trigger_snapshot?: JSONObject | null;
  reviewer_id?: string | null;
  review_date?: string | null;
  review_result?: string | null;
  review_notes?: string | null;
  adjustment_attestation_uid?: string | null;
  adjustment_attested_at?: string | null;
  status?: CreditAdjustmentStatus | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  created_by?: string | null;
}

/** Read model for a retirement request and its separate review state. */
export interface CreditRetirement {
  id: string;
  credit_id: string;
  location_id: string;
  retirement_reason: string;
  retired_tonnes: number;
  beneficiary_name?: string | null;
  beneficiary_wallet?: string | null;
  retirement_statement?: string | null;
  retirement_value_usd?: number | null;
  evidence_cid?: string | null;
  evidence_hash?: string | null;
  retirement_attestation_uid?: string | null;
  retired_onchain_at?: string | null;
  retirement_tx_hash?: string | null;
  status?: CreditRetirementStatus | null;
  reviewer_id?: string | null;
  review_date?: string | null;
  review_notes?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  created_by?: string | null;
  expires_at?: string | null;
  idempotency_key?: string | null;
  confirmed_at?: string | null;
  cancelled_at?: string | null;
}

/** Read model for a credit transfer ledger entry. */
export interface CreditTransfer {
  id: string;
  credit_id: string;
  location_id: string;
  transfer_type: CreditTransferType;
  transferred_tonnes: number;
  transfer_value_usd?: number | null;
  price_per_tonne_usd?: number | null;
  from_wallet?: string | null;
  to_wallet?: string | null;
  from_entity?: string | null;
  to_entity?: string | null;
  revenue_event_id?: string | null;
  treasury_event_id?: string | null;
  evidence_cid?: string | null;
  evidence_hash?: string | null;
  tx_hash?: string | null;
  chain?: string | null;
  status?: CreditTransferStatus | null;
  reviewer_id?: string | null;
  review_date?: string | null;
  review_notes?: string | null;
  metadata?: JSONObject | null;
  created_at?: string | null;
  created_by?: string | null;
}
