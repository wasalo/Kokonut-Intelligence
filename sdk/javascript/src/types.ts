export interface Location {
  id: string;
  name: string;
  slug: string;
  description?: string;
  boundary?: Record<string, any>;
  baseline_revenue?: number;
  baseline_asset_value?: number;
  baseline_cash_flow?: number;
  baseline_cost?: number;
  baseline_assumptions?: Record<string, any>;
  baseline_source?: string;
  baseline_date?: string;
  status: 'active' | 'inactive' | 'archived';
  created_at: string;
  updated_at: string;
}

export interface Farm {
  id: string;
  location_id: string;
  name: string;
  slug: string;
  description?: string;
  farm_type: 'conventional' | 'organic' | 'syntropic' | 'agroforestry' | 'hybrid';
  total_area: number;
  area_unit: 'hectares' | 'acres' | 'm2';
  status: 'active' | 'inactive' | 'archived';
  created_at: string;
  updated_at: string;
}

export interface Plot {
  id: string;
  farm_id: string;
  name: string;
  slug: string;
  area: number;
  area_unit: 'hectares' | 'acres' | 'm2';
  soil_type?: string;
  water_source?: string;
  boundary?: Record<string, any>;
  status: 'active' | 'inactive' | 'archived';
  created_at: string;
  updated_at: string;
}

export interface CropCycle {
  id: string;
  plot_id: string;
  crop_id: string;
  cycle_name: string;
  planting_date: string;
  expected_harvest_date?: string;
  actual_harvest_date?: string;
  status: 'planned' | 'planted' | 'growing' | 'harvested' | 'completed' | 'cancelled';
  yield_target?: number;
  yield_actual?: number;
  yield_unit?: string;
  created_at: string;
  updated_at: string;
}

export interface HarvestEvent {
  id: string;
  crop_cycle_id: string;
  plot_id: string;
  location_id: string;
  harvest_date: string;
  quantity: number;
  unit: string;
  quality_grade?: string;
  destination?: string;
  loss_amount?: number;
  loss_unit?: string;
  loss_reason?: string;
  loss_estimated_value?: number;
  evidence_urls?: string[];
  notes?: string;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface SalesEvent {
  id: string;
  harvest_id?: string;
  crop_cycle_id?: string;
  location_id: string;
  partner_id?: string;
  sale_date: string;
  buyer?: string;
  buyer_type?: string;
  quantity: number;
  unit: string;
  price_per_unit?: number;
  total_amount: number;
  currency: string;
  payment_status: 'pending' | 'partial' | 'paid' | 'overdue' | 'cancelled';
  return_amount?: number;
  discount_amount?: number;
  net_amount?: number;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface ExpenseEvent {
  id: string;
  location_id: string;
  plot_id?: string;
  crop_cycle_id?: string;
  expense_date: string;
  category: string;
  subcategory?: string;
  description?: string;
  vendor?: string;
  amount: number;
  currency: string;
  is_capex?: boolean;
  allocation_method?: 'direct' | 'proportional' | 'equal' | 'area_based';
  evidence_urls?: string[];
  invoice_number?: string;
  notes?: string;
  status: 'draft' | 'submitted' | 'verified' | 'published' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface SensorReading {
  id: string;
  sensor_id: string;
  location_id?: string;
  plot_id?: string;
  sensor_type?: string;
  reading_date: string;
  reading_time?: string;
  value: number;
  unit: string;
  quality: 'good' | 'suspect' | 'missing' | 'estimated';
  metadata?: Record<string, any>;
  created_at: string;
}

export interface SensorType {
  id: string;
  name: string;
  unit: string;
  min_value?: number;
  max_value?: number;
  description?: string;
  created_at: string;
}

export interface SensorDevice {
  id: string;
  name: string;
  slug: string;
  sensor_type_id: string;
  location_id: string;
  plot_id?: string;
  manufacturer?: string;
  model?: string;
  serial_number?: string;
  protocol?: 'http' | 'mqtt' | 'csv' | 'manual';
  endpoint_url?: string;
  status: 'active' | 'inactive' | 'maintenance' | 'decommissioned';
  calibration_date?: string;
  calibration_interval_days?: number;
  installation_date?: string;
  latitude?: number;
  longitude?: number;
  elevation_m?: number;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AlertRule {
  id: string;
  name: string;
  sensor_type_id: string;
  metric: 'value' | 'rate_of_change' | 'gap' | 'min' | 'max';
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'eq' | 'neq' | 'outside_range';
  threshold_value: number;
  threshold_value_max?: number;
  severity: 'info' | 'warning' | 'critical';
  cooldown_minutes: number;
  enabled: boolean;
  auto_create_claim: boolean;
  claim_type?: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface SensorAlert {
  id: string;
  sensor_device_id: string;
  alert_rule_id: string;
  reading_id?: string;
  severity: 'info' | 'warning' | 'critical';
  status: 'open' | 'acknowledged' | 'resolved' | 'false_positive';
  message: string;
  reading_value?: number;
  threshold_value?: number;
  triggered_at: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  claim_id?: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface WalletProfile {
  id: string;
  address: string;
  chain: string;
  role: 'farm' | 'buyer' | 'investor' | 'verifier' | 'community' | 'treasury';
  owner_type?: string;
  owner_id?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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
