export interface Location {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  boundary?: Record<string, unknown> | null;
  center?: Record<string, unknown> | null;
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
  baseline_assumptions?: Record<string, unknown> | null;
  baseline_source?: string | null;
  baseline_date?: string | null;
  status?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface Farm {
  id: string;
  location_id: string;
  name: string;
  slug: string;
  description?: string | null;
  boundary?: Record<string, unknown> | null;
  center?: Record<string, unknown> | null;
  logo_url?: string | null;
  traditional_name?: string | null;
  languages?: string[] | null;
  global_standard_certifications?: string[] | null;
  economic_sectors?: string[] | null;
  credits_registries?: string[] | null;
  data_privacy_status?: string | null;
  data_privacy_standard?: string | null;
  data_privacy_criteria?: Record<string, unknown> | null;
  farm_type?: string | null;
  total_area?: number | null;
  area_unit?: string | null;
  status?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface Plot {
  id: string;
  farm_id: string;
  name: string;
  slug: string;
  description?: string | null;
  area?: number | null;
  area_unit?: string | null;
  boundary?: Record<string, unknown> | null;
  center?: Record<string, unknown> | null;
  soil_type?: string | null;
  water_source?: string | null;
  elevation_m?: number | null;
  slope_pct?: number | null;
  aspect?: string | null;
  status?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
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
  metadata?: Record<string, unknown> | null;
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
  status?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: Record<string, unknown> | null;
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
  payment_status?: string | null;
  payment_date?: string | null;
  payment_method?: string | null;
  invoice_number?: string | null;
  return_amount?: number | null;
  discount_amount?: number | null;
  net_amount?: number | null;
  evidence_urls?: string[] | null;
  evidence_hashes?: string[] | null;
  notes?: string | null;
  status?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: Record<string, unknown> | null;
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
  subcategory?: string | null;
  description?: string | null;
  vendor?: string | null;
  vendor_id?: string | null;
  currency?: string | null;
  is_capex?: boolean | null;
  allocation_method?: string | null;
  allocation_weight?: number | null;
  evidence_urls?: string[] | null;
  receipt_hash?: string | null;
  invoice_number?: string | null;
  notes?: string | null;
  status?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  rejection_reason?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  source_raw?: Record<string, unknown> | null;
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
  status?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  schema_version?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  created_at?: string | null;
  created_by?: string | null;
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
  status?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  created_at?: string | null;
  created_by?: string | null;
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
  status?: string | null;
  created_at?: string | null;
  created_by?: string | null;
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
  metadata?: Record<string, unknown> | null;
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
  status?: string | null;
  calibration_date?: string | null;
  calibration_interval_days?: number | null;
  installation_date?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  elevation_m?: number | null;
  metadata?: Record<string, unknown> | null;
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
  threshold_value_max?: number;
  severity?: 'info' | 'warning' | 'critical' | null;
  cooldown_minutes?: number | null;
  enabled?: boolean | null;
  auto_create_claim?: boolean | null;
  claim_type?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SensorAlert {
  id: string;
  sensor_device_id: string;
  alert_rule_id: string;
  reading_id?: string | null;
  severity: 'info' | 'warning' | 'critical';
  status?: 'open' | 'acknowledged' | 'resolved' | 'false_positive' | null;
  message: string;
  reading_value?: number | null;
  threshold_value?: number | null;
  triggered_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  resolved_at?: string | null;
  claim_id?: string | null;
  metadata?: Record<string, unknown> | null;
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
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AttestationRecord {
  id: string;
  schema_id?: string;
  attestation_uid?: string;
  subject_id?: string;
  subject_type: string;
  claim_data: Record<string, any>;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  tx_hash?: string;
  chain?: string;
  reviewer_id?: string;
  reviewed_at?: string;
  attested_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ReportSnapshot {
  id: string;
  report_type: string;
  entity_type?: string;
  entity_id?: string;
  report_data: Record<string, any>;
  snapshot_hash: string;
  generated_by: string;
  period_start?: string;
  period_end?: string;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  created_at: string;
}

export interface ExportLog {
  id: string;
  export_type: string;
  format: 'csv' | 'json' | 'xlsx' | 'pdf' | 'parquet';
  entity_type?: string;
  entity_ids?: string[];
  target_table?: string;
  filters?: Record<string, any>;
  file_path?: string;
  file_size?: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  requested_by: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
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
  gross_revenue?: number;
  returns_and_discounts?: number;
  net_revenue?: number;
  direct_crop_costs?: number;
  allocated_shared_costs?: number;
  total_costs?: number;
  noi?: number;
  operating_margin_pct?: number;
  loss_rate_pct?: number;
  calculation_version?: string;
  calculated_at?: string;
  inputs?: Record<string, any>;
  created_by?: string;
}
